"""End-to-end smoke test against a running AeroNerds server.

Verifies the access model over real HTTP rather than trusting the unit tests:
unauthenticated reads are refused, a citizen can only reach their own records,
and each authority capability is allowed or denied exactly as the matrix says.

    python scripts/smoke_test.py                      # http://localhost:8000
    python scripts/smoke_test.py https://my.host      # a deployed instance

Exits non-zero if any expectation fails, so it can gate a deploy.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

DEMO = {
    "citizen": ("citizen", "Demo@Citizen1"),
    "citizen2": ("citizen2", "Demo@Citizen2"),
    "planner": ("planner", "Demo@Planner1"),
    "registrar": ("registrar", "Demo@Registrar1"),
    "sdm": ("sdm", "Demo@SDM1"),
}


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def _call(self, method, path, token=None, body=None):
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw or b"null")
            except json.JSONDecodeError:
                return e.code, raw.decode("utf-8", "replace")

    def get(self, path, token=None):
        return self._call("GET", path, token)

    def post(self, path, token=None, body=None):
        return self._call("POST", path, token, body if body is not None else {})

    def login(self, username, password):
        status, data = self.post("/api/auth/login", body={"username": username, "password": password})
        if status != 200:
            raise RuntimeError(f"login failed for {username}: {status} {data}")
        return data["access_token"], data["user"]

    def portfolio(self, token):
        status, data = self.get("/api/records/portfolio", token)
        if status != 200:
            raise RuntimeError(f"portfolio failed: {status} {data}")
        return data["items"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://localhost:8000")
    args = ap.parse_args()
    c = Client(args.base)

    results: list[tuple[str, bool, str]] = []

    def check(label, expected, actual, note=""):
        ok = expected == actual
        results.append((label, ok, note or f"expected {expected}, got {actual}"))
        return ok

    # ---- reachable? ----
    try:
        status, health = c.get("/api/meta/health")
    except Exception as exc:  # noqa: BLE001
        print(f"{RED}cannot reach {args.base}: {exc}{RESET}")
        print(f"  start it with: python run_server.py")
        return 2
    if status != 200:
        print(f"{RED}health endpoint returned {status}{RESET}")
        return 2

    print(f"{GREEN}server reachable{RESET}  {args.base}")
    print(f"  regions with data: {len(health.get('regions_with_data', []))}  {health.get('regions_with_data', [])}")

    # ---- public homepage needs no session, portal does not leak data ----
    try:
        with urllib.request.urlopen(f"{args.base}/", timeout=20) as r:
            home = r.read().decode("utf-8", "replace")
        check("GET / is the public homepage", True, "AeroNerds 3D Cadastre" in home or "AeroNerds" in home)
        check("GET / does not expose the portal", True, "auth-gate" not in home)
    except urllib.error.HTTPError as e:
        check("GET / reachable", 200, e.code)

    # ---- unauthenticated ----
    check("no token -> portfolio denied", 401, c.get("/api/records/portfolio")[0])
    check("no token -> all regions denied", 401, c.get("/api/records/regions")[0])
    check("no token -> roles catalogue is public", 200, c.get("/api/meta/roles")[0])
    check("no token -> health is public", 200, c.get("/api/meta/health")[0])
    check("bad password rejected", 401, c.post("/api/auth/login", body={"username": "citizen", "password": "wrong"})[0])
    check("unknown user rejected", 401, c.post("/api/auth/login", body={"username": "nobody", "password": "x"})[0])
    # 422 is correct for a blank password: the schema rejects it before the
    # credential check, so no account is probed with an empty secret. A short
    # non-empty password reaches the credential check and is refused there.
    check("empty password rejected by schema", 422, c.post("/api/auth/login", body={"username": "citizen", "password": ""})[0])
    check("short password rejected at credential check", 401, c.post("/api/auth/login", body={"username": "citizen", "password": "a"})[0])

    # ---- sign in ----
    tokens, users = {}, {}
    for seat, (u, p) in DEMO.items():
        tokens[seat], users[seat] = c.login(u, p)

    check("4 distinct roles provisioned", 4, len({users[s]["role_id"] for s in ("citizen", "planner", "registrar", "sdm")}))
    check("registrar role id", "registrar", users["registrar"]["role_id"])
    check("citizen gets only own-record caps", {"building:read:own", "parcel:read:own", "certificate:view:own", "grievance:file"}, set(users["citizen"]["capabilities"]))
    check("registrar has no own-only caps", True, not any(c.endswith(":own") for c in users["registrar"]["capabilities"]))

    # ---- citizen scoping ----
    own1 = c.portfolio(tokens["citizen"])
    own2 = c.portfolio(tokens["citizen2"])
    check("citizen portfolio is scoped", 1, len(own1))
    check("citizens do not share records", True, own1[0]["building_id"] != own2[0]["building_id"])

    r1, b1 = own1[0]["region"], own1[0]["building_id"]
    r2, b2 = own2[0]["region"], own2[0]["building_id"]

    check("citizen reads own record", 200, c.get(f"/api/records/building/{b1}?region={r1}", tokens["citizen"])[0])
    check("citizen blocked from other citizen's record", 403, c.get(f"/api/records/building/{b2}?region={r2}", tokens["citizen"])[0])
    check("citizen blocked from own id in wrong region", 403, c.get(f"/api/records/building/{b1}?region=bengaluru", tokens["citizen"])[0])
    # 403 rather than 404 for an unlinked id, on purpose: a citizen must not be
    # able to probe which building ids exist in the corpus.
    check("citizen cannot probe an unlinked id", 403, c.get(f"/api/records/building/osm_way_999999999?region={r1}", tokens["citizen"])[0])

    # ---- authority reach ----
    check("registrar reads any record", 200, c.get(f"/api/records/building/{b2}?region={r2}", tokens["registrar"])[0])
    check("planner reads any record", 200, c.get(f"/api/records/building/{b2}?region={r2}", tokens["planner"])[0])
    check("sdm reads any record", 200, c.get(f"/api/records/building/{b2}?region={r2}", tokens["sdm"])[0])

    # ---- adjudication ----
    check("registrar may adjudicate", 200, c.post("/api/review/decision", tokens["registrar"], {"building_id": b1, "region": r1, "decision": "APPROVE"})[0])
    check("citizen may not adjudicate", 403, c.post("/api/review/decision", tokens["citizen"], {"building_id": b1, "region": r1, "decision": "APPROVE"})[0])
    check("planner may not adjudicate", 403, c.post("/api/review/decision", tokens["planner"], {"building_id": b1, "region": r1, "decision": "APPROVE"})[0])
    check("sdm may not adjudicate", 403, c.post("/api/review/decision", tokens["sdm"], {"building_id": b1, "region": r1, "decision": "APPROVE"})[0])
    check("bogus decision rejected", 422, c.post("/api/review/decision", tokens["registrar"], {"building_id": b1, "region": r1, "decision": "SHIP_IT"})[0])

    # ---- exports ----
    check("registrar may export manifest", 200, c.get(f"/api/exports/manifest?region={r1}", tokens["registrar"])[0])
    check("planner may export manifest", 200, c.get(f"/api/exports/manifest?region={r1}", tokens["planner"])[0])
    check("sdm may not export manifest", 403, c.get(f"/api/exports/manifest?region={r1}", tokens["sdm"])[0])
    check("citizen may not export manifest", 403, c.get(f"/api/exports/manifest?region={r1}", tokens["citizen"])[0])

    # ---- audit ----
    check("registrar may read audit log", 200, c.get("/api/audit/log", tokens["registrar"])[0])
    check("citizen may not read audit log", 403, c.get("/api/audit/log", tokens["citizen"])[0])
    check("planner may not read audit log", 403, c.get("/api/audit/log", tokens["planner"])[0])

    # ---- grievances ----
    check(
        "citizen may file a grievance",
        201,
        c.post("/api/grievances", tokens["citizen"], {
            "region": r1, "building_id": b1, "category": "FLOOR_COUNT",
            "subject": "Floor 4 not shown", "narrative": "Smoke test submission.",
        })[0],
    )
    check(
        "grievance for a record the citizen does not own is refused",
        403,
        c.post("/api/grievances", tokens["citizen"], {
            "region": r2, "building_id": b2, "category": "FLOOR_COUNT",
            "subject": "not mine", "narrative": "Should be refused.",
        })[0],
    )
    check("sdm may read grievances", 200, c.get("/api/grievances", tokens["sdm"])[0])
    check("citizen may read own grievances", 200, c.get("/api/grievances", tokens["citizen"])[0])

    # ---- citizen payload must not leak internals ----
    status, view = c.get(f"/api/records/building/{b1}?region={r1}", tokens["citizen"])
    blob = json.dumps(view)
    check("citizen payload hides anomaly score", True, "ai_anomaly_score" not in blob)
    check("citizen payload hides model internals", True, "parcel_overlap_ratio" not in blob)
    check("citizen payload keeps verification status", True, "verification_status" in blob or "status" in blob)

    # ---- logout invalidates the session ----
    check("logout succeeds", 200, c.post("/api/auth/logout", tokens["planner"])[0])
    check("token is dead after logout", 401, c.get("/api/records/portfolio", tokens["planner"])[0])

    # ---- report ----
    passed = sum(1 for _, ok, _ in results if ok)
    failed = [(lbl, note) for lbl, ok, note in results if not ok]
    print()
    for lbl, ok, note in results:
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        line = f"  [{mark}] {lbl}"
        if not ok:
            line += f"  ({note})"
        print(line)

    print()
    if failed:
        print(f"{RED}{len(failed)} of {len(results)} checks FAILED{RESET}")
        return 1
    print(f"{GREEN}all {passed} checks passed{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
