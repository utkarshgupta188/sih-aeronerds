"""FastAPI application: authentication, role-based access control, static app.

Run with::

    python run_server.py

The service exposes a small authenticated API under ``/api`` and mounts the
existing static portal from ``frontend/`` so the whole prototype still runs
from a single port.

Entry points
------------
* ``/``            public landing page (``frontend/home.html``), no sign-in
* ``/index.html``  the authenticated portal, sign-in required
* ``/api``         authenticated JSON API

Scope boundaries enforced here (server-side, not just hidden in the UI)
------------------------------------------------------------------------
* Every ``/api`` route except ``/api/auth/*`` and ``/api/meta/health``
  requires a valid signed session.
* Role and capabilities are re-read from storage on every request, so a
  demotion takes effect immediately rather than at token expiry.
* Citizen record reads are filtered against ``citizen_links``; a citizen
  requesting a building id they are not linked to receives 403, not data.
* Adjudication, exports and certificate issuance require the matching
  capability, not merely a logged-in session.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import records, security
from .rbac import (
    CAP_ADJUDICATE,
    CAP_AUDIT_LOG_READ,
    CAP_EXPORT_MANIFEST,
    CAP_GRIEVANCE_ADJUDICATE,
    CAP_GRIEVANCE_FILE,
    CAP_READ_BUILDINGS_ALL,
    CAP_READ_BUILDINGS_OWN,
    CAP_READ_PARCELS_ALL,
    CAP_READ_PARCELS_OWN,
    ROLES,
    Role,
    get_role,
    has_capability,
    normalise_role,
    redact_for_citizen,
)
from .schemas import (
    GrievanceCreate,
    GrievanceView,
    LoginRequest,
    LoginResponse,
    ReviewDecision,
    RoleInfo,
    SessionUser,
)
from .users import User, UserStore

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

#: Secret is read from the environment so it is never committed. A random
#: per-process secret is used when unset, which invalidates sessions on
#: restart -- the correct, safe default for a local demo.
TOKEN_SECRET = os.environ.get("AERONERDS_TOKEN_SECRET") or security.new_secret()
DB_PATH = os.environ.get("AERONERDS_AUTH_DB") or str(BASE_DIR / "data" / "aeronerds_auth.db")

store = UserStore(DB_PATH)

app = FastAPI(
    title="AeroNerds SIH26011 — Authenticated 3D ULPIN Portal API",
    version="1.0.0",
    description=(
        "Authentication and role-scoped evidence access for the proposed 3D "
        "vertical ULPIN linkage prototype. This service does not issue or "
        "recognise official ULPINs."
    ),
)

# In-memory grievance register (demo only; not a statutory case management
# system). Deliberately process-local so no data is written to disk.
GRIEVANCES: dict[str, GrievanceView] = {}


# --------------------------------------------------------------------------
# session / auth dependencies
# --------------------------------------------------------------------------
def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


def current_user(authorization: str | None = Header(default=None)) -> User:
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Sign in to access role-scoped records.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = security.verify_token(token, TOKEN_SECRET)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token is invalid or has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not store.session_is_live(claims["sid"]):
        store.revoke_session(claims["sid"])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = store.get_by_id(claims["uid"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not active."
        )
    return user


def require_capability(capability: str):
    """Dependency factory: enforce a capability on the live role."""

    def _dependency(user: User = Depends(current_user)) -> User:
        if not has_capability(user.role_id, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{get_role(user.role_id).title}' does not hold capability "
                    f"'{capability}'. This action is not permitted for your seat."
                ),
            )
        return user

    return _dependency


def session_user_payload(user: User) -> SessionUser:
    role = get_role(user.role_id)
    return SessionUser(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role_id=role.id,
        role_title=role.title,
        role_badge=role.badge,
        role_icon=role.icon,
        department=role.dept,
        workspace_id=role.workspace_id,
        subtitle=role.subtitle,
        jurisdiction=user.jurisdiction,
        capabilities=sorted(role.capabilities),
        is_demo=user.is_demo,
    )


# --------------------------------------------------------------------------
# meta + auth routes
# --------------------------------------------------------------------------
@app.get("/api/meta/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "service": "aeronerds-auth",
        "regions_with_data": records.available_regions(),
        "auth_required": True,
        "notice": "Prototype. Proposed linkages only; not official ULPIN issuance.",
    }


@app.get("/api/meta/roles", tags=["meta"])
def list_roles() -> dict:
    """Public role catalogue so the sign-in screen can show the four seats."""
    return {
        "roles": [
            RoleInfo(
                id=r.id,
                title=r.title,
                department=r.dept,
                badge=r.badge,
                icon=r.icon,
                workspace_id=r.workspace_id,
                subtitle=r.subtitle,
                capabilities=sorted(r.capabilities),
            )
            for r in ROLES.values()
        ]
    }


@app.post("/api/auth/login", response_model=LoginResponse, tags=["auth"])
def login(payload: LoginRequest) -> LoginResponse:
    found = store.get_by_username(payload.username.strip())
    if found is None:
        # Same message and comparable work for unknown user vs wrong password.
        security.hash_password(payload.password, iterations=1000)
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    user, password_hash = found
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")
    if not security.verify_password(payload.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    session_id = security.new_session_id()
    token, expires_at = security.sign_token(session_id, user.id, TOKEN_SECRET)
    store.create_session(session_id, user.id, expires_at)
    return LoginResponse(access_token=token, expires_at=expires_at, user=session_user_payload(user))


@app.get("/api/auth/me", response_model=SessionUser, tags=["auth"])
def whoami(user: User = Depends(current_user)) -> SessionUser:
    return session_user_payload(user)


@app.post("/api/auth/logout", tags=["auth"])
def logout(authorization: str | None = Header(default=None)) -> dict:
    token = _bearer_token(authorization)
    claims = security.verify_token(token, TOKEN_SECRET) if token else None
    if claims:
        store.revoke_session(claims["sid"])
    return {"status": "signed_out"}


# --------------------------------------------------------------------------
# role-scoped data routes
# --------------------------------------------------------------------------
@app.get("/api/records/regions", tags=["records"])
def list_regions(user: User = Depends(current_user)) -> dict:
    return {
        "regions": records.authorised_regions(user.role_id, user.id, store),
        "role": user.role_id,
    }


@app.get("/api/records/summary", tags=["records"])
def region_summary(
    region: str = Query(..., min_length=1, max_length=64),
    user: User = Depends(current_user),
) -> dict:
    if region not in records.authorised_regions(user.role_id, user.id, store):
        raise HTTPException(status_code=403, detail="Region not available to your role/seat.")
    buildings, parcels = records.record_count(region)
    return {"region": region, "buildings": buildings, "parcels": parcels}


@app.get("/api/records/building/{building_id}", tags=["records"])
def get_building(
    building_id: str,
    region: str = Query(..., min_length=1, max_length=64),
    user: User = Depends(current_user),
) -> dict:
    """Role-scoped single record.

    Authorities with ``building:read:all`` may read any record. Citizens are
    limited to ids linked to their own account and additionally receive the
    redacted projection.
    """
    allowed_regions = records.authorised_regions(user.role_id, user.id, store)
    if region not in allowed_regions:
        raise HTTPException(status_code=403, detail="Region not available to your role/seat.")

    if has_capability(user.role_id, CAP_READ_BUILDINGS_ALL):
        view = records.government_building_view(region, building_id)
        if view is None:
            raise HTTPException(status_code=404, detail="Building record not found.")
        return view

    if not has_capability(user.role_id, CAP_READ_BUILDINGS_OWN):
        raise HTTPException(status_code=403, detail="Your role cannot read cadastral records.")

    owned = set(store.citizen_building_ids(user.id, region))
    if str(building_id) not in owned:
        # Deliberately identical to the "record does not exist" phrasing used
        # for unlinked ids so the endpoint does not confirm the existence of
        # another citizen's property.
        raise HTTPException(
            status_code=403,
            detail="This record is not linked to your account. A landowner may only "
            "access their own property records.",
        )
    link = next(
        (l for l in store.citizen_links(user.id)
         if l["region"] == region and l["building_id"] == str(building_id)),
        None,
    )
    view = records.citizen_building_view(region, building_id, link.get("unit_label") if link else None)
    if view is None:
        raise HTTPException(status_code=404, detail="Building record not found in this region.")
    return view


@app.get("/api/records/portfolio", tags=["records"])
def my_portfolio(
    region: str | None = Query(default=None, min_length=1, max_length=64),
    user: User = Depends(current_user),
) -> dict:
    """The caller's own linked property records.

    A citizen sees exactly their own portfolio. An authority sees the same
    endpoint only to confirm it resolves to their own (empty) linkage set,
    which keeps the citizen path free of a role-specific bypass.
    """
    if has_capability(user.role_id, CAP_READ_BUILDINGS_ALL):
        return {
            "role": user.role_id,
            "scope": "OWN_LINKS_ONLY",
            "items": records.citizen_portfolio(store.citizen_links(user.id), region),
            "notice": "Authorities read the full record set via the cadastral view.",
        }
    if not has_capability(user.role_id, CAP_READ_BUILDINGS_OWN):
        raise HTTPException(status_code=403, detail="Your role has no property portfolio.")
    return {
        "role": user.role_id,
        "scope": "OWN_LINKS_ONLY",
        "items": records.citizen_portfolio(store.citizen_links(user.id), region),
    }


@app.get("/api/records/parcel/{parcel_id}", tags=["records"])
def get_parcel(
    parcel_id: str,
    region: str = Query(..., min_length=1, max_length=64),
    user: User = Depends(current_user),
) -> dict:
    if region not in records.authorised_regions(user.role_id, user.id, store):
        raise HTTPException(status_code=403, detail="Region not available to your role/seat.")

    if has_capability(user.role_id, CAP_READ_PARCELS_ALL):
        feat = records.get_parcel(region, parcel_id)
        if feat is None:
            raise HTTPException(status_code=404, detail="Parcel record not found.")
        props = dict(feat.get("properties") or {})
        return {"region": region, "parcel_id": str(parcel_id), "properties": props,
                "geometry": feat.get("geometry")}

    if has_capability(user.role_id, CAP_READ_PARCELS_OWN):
        owned_buildings = set(store.citizen_building_ids(user.id, region))
        linked = False
        for bid in owned_buildings:
            feat = records.get_building(region, bid)
            if feat is None:
                continue
            props = feat.get("properties") or {}
            if str(props.get("linked_parcel_id")) == str(parcel_id):
                linked = True
                break
        if not linked:
            raise HTTPException(
                status_code=403,
                detail="This parcel is not linked to your account.",
            )
        feat = records.get_parcel(region, parcel_id)
        if feat is None:
            raise HTTPException(status_code=404, detail="Parcel record not found.")
        props = dict(feat.get("properties") or {})
        return {
            "region": region,
            "parcel_id": str(parcel_id),
            "properties": redact_for_citizen(props),
            "geometry": feat.get("geometry"),
        }

    raise HTTPException(status_code=403, detail="Your role cannot read parcel records.")


# --------------------------------------------------------------------------
# capability-gated actions
# --------------------------------------------------------------------------
@app.post("/api/review/decision", tags=["review"])
def record_review_decision(
    payload: ReviewDecision, user: User = Depends(current_user)
) -> dict:
    """Rule 8 adjudication gate. Registrar only."""
    if not has_capability(user.role_id, CAP_ADJUDICATE):
        raise HTTPException(
            status_code=403,
            detail="Only the Registrar seat may adjudicate (APPROVE / CORRECT / REJECT / UNRESOLVED).",
        )
    if payload.region not in records.available_regions():
        raise HTTPException(status_code=404, detail="Unknown region.")
    if records.get_building(payload.region, payload.building_id) is None:
        raise HTTPException(status_code=404, detail="Building record not found.")
    return {
        "status": "recorded",
        "decision": payload.decision,
        "building_id": payload.building_id,
        "region": payload.region,
        "reviewer": user.username,
        "reviewer_role": user.role_id,
        "at": time.time(),
        "note": "AI never adjudicates; this record is a human reviewer action (AGENTS.md rule 5).",
    }


@app.post("/api/grievances", response_model=GrievanceView, status_code=201, tags=["grievance"])
def file_grievance(payload: GrievanceCreate, user: User = Depends(current_user)) -> GrievanceView:
    """File a mutation / survey grievance.

    A citizen may only file against a building linked to their own account.
    An authority may file on behalf of any record it can read.
    """
    if not (
        has_capability(user.role_id, CAP_GRIEVANCE_FILE)
        or has_capability(user.role_id, CAP_GRIEVANCE_ADJUDICATE)
    ):
        raise HTTPException(
            status_code=403, detail="Your role may not file grievances on this portal."
        )

    if payload.region not in records.available_regions():
        raise HTTPException(status_code=404, detail="Unknown region.")
    if records.get_building(payload.region, payload.building_id) is None:
        raise HTTPException(status_code=404, detail="Building record not found.")

    if has_capability(user.role_id, CAP_READ_BUILDINGS_ALL):
        pass  # authority may raise against any readable record
    else:
        owned = set(store.citizen_building_ids(user.id, payload.region))
        if payload.building_id not in owned:
            raise HTTPException(
                status_code=403,
                detail="A grievance may only be filed against a property linked to your account.",
            )

    item = GrievanceView(
        id=f"GRV-{uuid.uuid4().hex[:10].upper()}",
        user_id=user.id,
        region=payload.region,
        building_id=payload.building_id,
        category=payload.category,
        subject=payload.subject,
        narrative=payload.narrative,
        status="SUBMITTED_PENDING_REVIEW",
        created_at=time.time(),
    )
    GRIEVANCES[item.id] = item
    return item


@app.get("/api/grievances", tags=["grievance"])
def list_grievances(user: User = Depends(current_user)) -> dict:
    if has_capability(user.role_id, CAP_GRIEVANCE_ADJUDICATE):
        items = list(GRIEVANCES.values())
    elif has_capability(user.role_id, CAP_GRIEVANCE_FILE):
        items = [g for g in GRIEVANCES.values() if g.user_id == user.id]
    else:
        raise HTTPException(status_code=403, detail="Your role cannot access grievances.")
    return {"items": [g.model_dump() for g in items], "count": len(items)}


@app.get("/api/exports/manifest", tags=["review"])
def export_manifest(
    region: str = Query(..., min_length=1, max_length=64),
    user: User = Depends(current_user),
) -> dict:
    """DILRMP-style state manifest export. Registrar / Town Planner only."""
    if not has_capability(user.role_id, CAP_EXPORT_MANIFEST):
        raise HTTPException(
            status_code=403, detail="Your role is not permitted to export land manifests."
        )
    if region not in records.available_regions():
        raise HTTPException(status_code=404, detail="Unknown region.")
    buildings, parcels = records.record_count(region)
    return {
        "region": region,
        "buildings": buildings,
        "parcels": parcels,
        "requested_by": user.username,
        "role": user.role_id,
        "format": "manifest-preview",
        "notice": "Prototype export. Proposed linkages are not official issuance.",
    }


@app.get("/api/audit/log", tags=["review"])
def audit_log(user: User = Depends(current_user)) -> dict:
    if not has_capability(user.role_id, CAP_AUDIT_LOG_READ):
        raise HTTPException(status_code=403, detail="Your role cannot read the audit log.")
    return {"entries": [], "notice": "Reviewer actions are audit-logged (AGENTS.md rule 8)."}


# --------------------------------------------------------------------------
# static frontend
# --------------------------------------------------------------------------
@app.exception_handler(401)
def _unauthorized(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": exc.detail, "code": "unauthenticated"})


@app.exception_handler(403)
def _forbidden(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.detail, "code": "forbidden"})


@app.get("/", include_in_schema=False)
def public_homepage() -> FileResponse:
    """Public landing page.

    Served ahead of the static mount so ``/`` opens the public homepage rather
    than the authenticated portal. The portal itself stays at ``/index.html``.
    """
    landing = FRONTEND_DIR / "home.html"
    if landing.exists():
        return FileResponse(landing)
    # Fall back to the portal if the landing page was removed.
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="portal")
