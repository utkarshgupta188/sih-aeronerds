"""Tests for authentication, role-based access control and citizen data scope.

The important property under test is the *negative* one: a citizen must not
be able to read a record that is not linked to their account, and a citizen
must not be able to reach adjudication or export endpoints. Positive-path
tests alone would pass against a system with no authorisation at all.
"""

import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

REGISTRAR = ("registrar", "Demo@Registrar1")
PLANNER = ("planner", "Demo@Planner1")
SDM = ("sdm", "Demo@SDM1")
CITIZEN = ("citizen", "Demo@Citizen1")
CITIZEN2 = ("citizen2", "Demo@Citizen2")


@pytest.fixture(scope="module")
def client():
    from backend.main import app

    return TestClient(app)


def login(client, creds):
    resp = client.post("/api/auth/login", json={"username": creds[0], "password": creds[1]})
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# password hashing + tokens (unit level)
# --------------------------------------------------------------------------
def test_password_hash_is_salted_and_verifies():
    from backend.security import hash_password, verify_password

    a = hash_password("correct horse battery staple")
    b = hash_password("correct horse battery staple")
    assert a != b, "identical passwords must not produce identical hashes (no salt)"
    assert verify_password("correct horse battery staple", a)
    assert verify_password("correct horse battery staple", b)
    assert not verify_password("wrong password", a)


def test_password_hash_never_contains_plaintext():
    from backend.security import hash_password

    stored = hash_password("SuperSecret123")
    assert "SuperSecret123" not in stored
    assert stored.startswith("pbkdf2_sha256$")


def test_token_tamper_and_expiry_are_rejected():
    import time

    from backend.security import new_session_id, sign_token, verify_token

    secret = "unit-test-secret"
    token, _ = sign_token("sid-1", "u-1", secret)
    assert verify_token(token, secret) is not None

    # wrong secret must fail
    assert verify_token(token, "another-secret") is None

    # flipped signature must fail
    bad = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert verify_token(bad, secret) is None

    # expired token must fail
    expired, _ = sign_token("sid-1", "u-1", secret, expires_in=-1)
    assert verify_token(expired, secret) is None

    # just-expired boundary
    ok, _ = sign_token("s", "u", secret, expires_in=10, now=time.time() - 20)
    assert verify_token(ok, secret) is None


# --------------------------------------------------------------------------
# login
# --------------------------------------------------------------------------
def test_login_succeeds_for_each_seeded_role(client):
    for creds in (REGISTRAR, PLANNER, SDM, CITIZEN, CITIZEN2):
        body = login(client, creds)
        assert body["user"]["role_id"] in {"registrar", "planner", "sdm", "citizen"}
        assert body["access_token"]


def test_login_rejects_bad_password(client):
    resp = client.post("/api/auth/login", json={"username": "registrar", "password": "wrong"})
    assert resp.status_code == 401


def test_login_rejects_unknown_user_with_same_message(client):
    bad_user = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    bad_pass = client.post("/api/auth/login", json={"username": "registrar", "password": "x"})
    assert bad_user.status_code == bad_pass.status_code == 401
    assert bad_user.json()["detail"] == bad_pass.json()["detail"]


def test_protected_routes_require_a_token(client):
    for path in (
        "/api/auth/me",
        "/api/records/portfolio",
        "/api/records/regions",
    ):
        assert client.get(path).status_code == 401, path


def test_forged_token_is_rejected(client):
    resp = client.get("/api/auth/me", headers=auth_header("not.a.real.token"))
    assert resp.status_code == 401


# --------------------------------------------------------------------------
# role identity
# --------------------------------------------------------------------------
def test_registrar_can_adjudicate_planner_cannot(client):
    reg = login(client, REGISTRAR)["access_token"]
    resp = client.post(
        "/api/review/decision",
        headers=auth_header(reg),
        json={
            "region": "bhopal",
            "building_id": "osm_way_413845798",
            "decision": "APPROVE",
        },
    )
    assert resp.status_code == 200

    for creds in (PLANNER, SDM, CITIZEN, CITIZEN2):
        token = login(client, creds)["access_token"]
        resp = client.post(
            "/api/review/decision",
            headers=auth_header(token),
            json={
                "region": "bhopal",
                "building_id": "osm_way_413845798",
                "decision": "APPROVE",
            },
        )
        assert resp.status_code == 403, creds[0]


def test_only_registrar_and_planner_may_export(client):
    for creds, expected in ((REGISTRAR, 200), (PLANNER, 200), (SDM, 403), (CITIZEN, 403)):
        token = login(client, creds)["access_token"]
        resp = client.get("/api/exports/manifest?region=bhopal", headers=auth_header(token))
        assert resp.status_code == expected, creds[0]


def test_only_registrar_reads_audit_log(client):
    reg = login(client, REGISTRAR)["access_token"]
    assert client.get("/api/audit/log", headers=auth_header(reg)).status_code == 200
    for creds in (PLANNER, SDM, CITIZEN):
        token = login(client, creds)["access_token"]
        assert client.get("/api/audit/log", headers=auth_header(token)).status_code == 403


def test_sdm_can_adjudicate_grievances_but_not_verification(client):
    sdm = login(client, SDM)["access_token"]
    citizen = login(client, CITIZEN)["access_token"]

    payload = {
        "region": "bhopal",
        "building_id": "osm_way_413845798",
        "category": "MUTATION_OR_SURVEY",
        "subject": "Boundary not matching field survey",
        "narrative": "Field survey indicates a different boundary than the mapped parcel.",
    }
    assert client.post("/api/grievances", headers=auth_header(sdm), json=payload).status_code == 201

    # An SDM must not gain registrar powers from grievance jurisdiction.
    resp = client.post(
        "/api/review/decision",
        headers=auth_header(sdm),
        json={"region": "bhopal", "building_id": "osm_way_413845798", "decision": "APPROVE"},
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------
# citizen data scope -- the core requirement
# --------------------------------------------------------------------------
def test_citizen_portfolio_returns_only_own_records(client):
    token = login(client, CITIZEN)["access_token"]
    body = client.get("/api/records/portfolio", headers=auth_header(token)).json()
    assert body["scope"] == "OWN_LINKS_ONLY"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["building_id"] == "osm_way_413845798"


def test_citizen_cannot_read_another_citizens_record(client):
    """citizen2 owns osm_way_375220424; citizen must not see it."""
    token = login(client, CITIZEN)["access_token"]
    resp = client.get(
        "/api/records/building/osm_way_375220424?region=bhopal", headers=auth_header(token)
    )
    assert resp.status_code == 403
    assert "not linked to your account" in resp.json()["detail"]


def test_citizen_cannot_read_unlinked_record_by_id(client):
    token = login(client, CITIZEN)["access_token"]
    resp = client.get(
        "/api/records/building/osm_way_413845767?region=bhopal", headers=auth_header(token)
    )
    assert resp.status_code == 403


def test_citizen_can_read_own_record(client):
    token = login(client, CITIZEN)["access_token"]
    resp = client.get(
        "/api/records/building/osm_way_413845798?region=bhopal", headers=auth_header(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["building_id"] == "osm_way_413845798"
    # non-official linkage must be declared
    assert body["linkage_status"] == "PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE"


def test_citizen_response_redacts_model_internals(client):
    from backend.rbac import CITIZEN_REDACTED_FIELDS

    token = login(client, CITIZEN)["access_token"]
    body = client.get(
        "/api/records/building/osm_way_413845798?region=bhopal", headers=auth_header(token)
    ).json()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in CITIZEN_REDACTED_FIELDS, f"leaked internal field: {key}"
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(body)


def test_authority_sees_model_internals_that_citizen_does_not(client):
    reg = login(client, REGISTRAR)["access_token"]
    gov = client.get(
        "/api/records/building/osm_way_413845798?region=bhopal", headers=auth_header(reg)
    ).json()
    assert "ai_anomaly_score" in gov["provenance"]

    cit = login(client, CITIZEN)["access_token"]
    view = client.get(
        "/api/records/building/osm_way_413845798?region=bhopal", headers=auth_header(cit)
    ).json()
    assert "ai_anomaly_score" not in view["provenance"]


def test_citizen_cannot_read_unauthorised_region(client):
    token = login(client, CITIZEN)["access_token"]
    resp = client.get(
        "/api/records/building/osm_way_413845798?region=coimbatore", headers=auth_header(token)
    )
    assert resp.status_code == 403


def test_citizen_regions_are_limited_to_linked_region(client):
    token = login(client, CITIZEN)["access_token"]
    regions = client.get("/api/records/regions", headers=auth_header(token)).json()["regions"]
    assert regions == ["bhopal"]


def test_authority_sees_all_available_regions(client):
    token = login(client, REGISTRAR)["access_token"]
    regions = client.get("/api/records/regions", headers=auth_header(token)).json()["regions"]
    assert "bhopal" in regions
    assert "coimbatore" in regions


def test_citizen_cannot_read_parcel_not_linked_to_them(client):
    token = login(client, CITIZEN)["access_token"]
    resp = client.get("/api/records/parcel/bhopal_ward_34?region=bhopal", headers=auth_header(token))
    assert resp.status_code == 403


def test_citizen_can_read_own_parcel(client):
    from backend.records import get_building

    props = get_building("bhopal", "osm_way_413845798")["properties"]
    parcel_id = props["linked_parcel_id"]
    token = login(client, CITIZEN)["access_token"]
    resp = client.get(f"/api/records/parcel/{parcel_id}?region=bhopal", headers=auth_header(token))
    assert resp.status_code == 200


def test_citizen_can_file_grievance_only_on_own_record(client):
    token = login(client, CITIZEN)["access_token"]
    ok = client.post(
        "/api/grievances",
        headers=auth_header(token),
        json={
            "region": "bhopal",
            "building_id": "osm_way_413845798",
            "category": "MUTATION_OR_SURVEY",
            "subject": "Floor count differs from sanctioned plan",
            "narrative": "Sanctioned plan shows 2 floors; portal shows a different count.",
        },
    )
    assert ok.status_code == 201

    denied = client.post(
        "/api/grievances",
        headers=auth_header(token),
        json={
            "region": "bhopal",
            "building_id": "osm_way_375220424",
            "category": "MUTATION_OR_SURVEY",
            "subject": "Not my property",
            "narrative": "Attempting to file against an unlinked record.",
        },
    )
    assert denied.status_code == 403


def test_planner_may_not_file_grievance(client):
    token = login(client, PLANNER)["access_token"]
    resp = client.post(
        "/api/grievances",
        headers=auth_header(token),
        json={
            "region": "bhopal",
            "building_id": "osm_way_413845798",
            "category": "MUTATION_OR_SURVEY",
            "subject": "Should be rejected",
            "narrative": "Planner seat has no grievance capability.",
        },
    )
    assert resp.status_code == 403


def test_citizen_only_sees_own_grievances(client):
    token = login(client, CITIZEN)["access_token"]
    body = client.get("/api/grievances", headers=auth_header(token)).json()
    mine = client.get("/api/auth/me", headers=auth_header(token)).json()
    assert all(g["user_id"] == mine["id"] for g in body["items"])


# --------------------------------------------------------------------------
# session lifecycle
# --------------------------------------------------------------------------
def test_logout_invalidates_the_token(client):
    body = login(client, PLANNER)
    headers = auth_header(body["access_token"])
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_whoami_matches_login_role(client):
    body = login(client, SDM)
    me = client.get("/api/auth/me", headers=auth_header(body["access_token"])).json()
    assert me["role_id"] == body["user"]["role_id"] == "sdm"
    assert me["role_badge"] == "SDM"


def test_role_catalogue_exposes_four_seats(client):
    roles = client.get("/api/meta/roles").json()["roles"]
    assert {r["id"] for r in roles} == {"registrar", "planner", "sdm", "citizen"}


def test_no_authority_capability_is_granted_to_citizen():
    from backend.rbac import AUTHORITY_ONLY_CAPABILITIES, capabilities_for

    citizen_caps = capabilities_for("citizen")
    assert not (citizen_caps & AUTHORITY_ONLY_CAPABILITIES)


def test_legacy_admin_role_maps_to_registrar():
    from backend.rbac import normalise_role

    assert normalise_role("admin") == "registrar"
    assert normalise_role("nonsense") == "registrar"


def test_unknown_building_returns_404_for_authority(client):
    token = login(client, REGISTRAR)["access_token"]
    resp = client.get(
        "/api/records/building/does_not_exist?region=bhopal", headers=auth_header(token)
    )
    assert resp.status_code == 404
