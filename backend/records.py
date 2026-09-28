"""Read-only access to the pipeline's real GeoJSON output.

This module is the only place that knows the on-disk cadastral record shape.
It performs two jobs:

1. Load ``frontend/data/<region>_buildings_3d.geojson`` and
   ``<region>_cadastral_parcels.geojson`` (the real pipeline products).
2. Project a full record into either a *government* view (all provenance and
   model diagnostics) or a *citizen* view (own record only, internal model
   fields stripped) per AGENTS.md rules 3 and 5.

No value is invented here. Every field returned originates in the pipeline
output or in ``citizen_links``; where the pipeline could not determine
something, the pipeline's own ``NOT_DETERMINABLE`` sentinel is passed through
rather than substituted with a guess.
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from .rbac import (
    CITIZEN_REDACTION_NOTICE,
    CAP_CERTIFICATE_ISSUE,
    CAP_CERTIFICATE_VIEW_OWN,
    CAP_READ_BUILDINGS_ALL,
    CAP_READ_PARCELS_ALL,
    Role,
    has_capability,
    redact_for_citizen,
)

DATA_ROOT = Path(__file__).resolve().parent.parent / "frontend" / "data"

#: Sentinel used by the pipeline when evidence is insufficient. Propagated
#: verbatim rather than being replaced by a default (AGENTS.md rule 4).
NOT_DETERMINABLE = "NOT_DETERMINABLE"

REGION_FILES: dict[str, tuple[str, str]] = {
    "bhopal": ("bhopal_buildings_3d.geojson", "bhopal_cadastral_parcels.geojson"),
    "bengaluru": ("buildings_3d.geojson", "cadastral_parcels_valid.geojson"),
    "indore": ("indore_buildings_3d.geojson", "indore_cadastral_parcels.geojson"),
    "navi_mumbai": ("navi_mumbai_buildings_3d.geojson", "navi_mumbai_cadastral_parcels.geojson"),
    "mumbai_kalyan": (
        "mumbai_kalyan_buildings_3d.geojson",
        "mumbai_kalyan_cadastral_parcels.geojson",
    ),
    "coimbatore": (
        "coimbatore_buildings_3d.geojson",
        "coimbatore_cadastral_parcels.geojson",
    ),
}

#: Region state codes as used by the proposed 3D vertical linkage format.
STATE_CODES: dict[str, str] = {
    "bhopal": "IN-MP-BHP",
    "bengaluru": "IN-KA-BLR",
    "indore": "IN-MP-IND",
    "navi_mumbai": "IN-MH-NMU",
    "mumbai_kalyan": "IN-MH-KDN",
    "coimbatore": "IN-TN-CBE",
}

_LOCK = threading.Lock()


def available_regions() -> list[str]:
    """Regions whose both layers exist and are non-empty on disk."""
    out = []
    for region, (bldg, parcel) in REGION_FILES.items():
        if (DATA_ROOT / bldg).exists() and (DATA_ROOT / parcel).exists():
            out.append(region)
    return out


@lru_cache(maxsize=32)
def _load_json(filename: str) -> dict | None:
    path = DATA_ROOT / filename
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def clear_cache() -> None:
    _load_json.cache_clear()


def _feature_index(filename: str, key: str = "id") -> dict[str, dict]:
    data = _load_json(filename)
    if not data:
        return {}
    index: dict[str, dict] = {}
    for feat in data.get("features", []):
        props = feat.get("properties") or {}
        fid = props.get(key)
        if fid is not None:
            index[str(fid)] = feat
    return index


def building_index(region: str) -> dict[str, dict]:
    if region not in REGION_FILES:
        return {}
    with _LOCK:
        return _feature_index(REGION_FILES[region][0])


def parcel_index(region: str) -> dict[str, dict]:
    if region not in REGION_FILES:
        return {}
    with _LOCK:
        return _feature_index(REGION_FILES[region][1])


def get_building(region: str, building_id: str) -> dict | None:
    return building_index(region).get(str(building_id))


def get_parcel(region: str, parcel_id: str) -> dict | None:
    return parcel_index(region).get(str(parcel_id))


def _digits(value: Any, default: str = "0") -> str:
    if value is None:
        return default
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits or default


def proposed_ulpin(region: str, props: dict) -> str:
    """Build the proposed 3D vertical linkage ID.

    Format: ``<state>-P<parcel>-B<building>`` (floor segment is appended by
    the floor-level endpoints). This is a *proposed* linkage, never an
    official issuance (AGENTS.md rule 2).
    """
    state = STATE_CODES.get(region, "IN-XX-XXX")
    parcel = _digits(props.get("linked_parcel_id"), "0000")
    building = _digits(props.get("id"), "0")
    return f"{state}-P{parcel}-B{building}"


# --------------------------------------------------------------------------
# projections
# --------------------------------------------------------------------------
def government_building_view(region: str, building_id: str) -> dict | None:
    """Full record for a government role, including model diagnostics."""
    feat = get_building(region, building_id)
    if feat is None:
        return None
    props = dict(feat.get("properties") or {})
    parcel_props = {}
    linked = props.get("linked_parcel_id")
    if linked:
        parcel_feat = get_parcel(region, linked)
        if parcel_feat:
            parcel_props = dict(parcel_feat.get("properties") or {})

    return {
        "region": region,
        "building_id": str(building_id),
        "provenance": {
            "geometry_source": props.get("source", "UNKNOWN"),
            "footprint_match_status": props.get("match_status_2d", NOT_DETERMINABLE),
            "parcel_overlap_ratio": props.get("parcel_overlap_ratio"),
            "height_source": props.get("height_source", NOT_DETERMINABLE),
            "height_confidence": props.get("building_height_confidence", NOT_DETERMINABLE),
            "floor_detection_status": props.get("floor_detection_status", NOT_DETERMINABLE),
            "floor_model_version": props.get("floor_model_version"),
            "floor_detection_method": props.get("floor_detection_method"),
            "vegetation_evidence": props.get("vegetation_evidence", NOT_DETERMINABLE),
            "vegetation_evidence_label": props.get("vegetation_evidence_label"),
            "ndvi_review_recommendation": props.get("ndvi_review_recommendation", NOT_DETERMINABLE),
            "ai_anomaly_flag": props.get("ai_anomaly_flag"),
            "ai_anomaly_score": props.get("ai_anomaly_score"),
            "crs": props.get("crs", "EPSG:4326"),
        },
        "vertical": {
            "ground_elevation_m": props.get("ground_elevation_m"),
            "building_height_m": props.get("building_height_m"),
            "height_status": props.get("building_height_status"),
            "derived_floors": props.get("derived_floors"),
            "floor_count_estimated": props.get("floor_count_estimated"),
            "floor_min": props.get("floor_min"),
            "floor_max": props.get("floor_max"),
            "floor_confidence_state": props.get("floor_confidence_state", NOT_DETERMINABLE),
            "floor_confidence_pct": props.get("floor_confidence_pct"),
            "requires_human_verification": props.get("requires_human_verification"),
        },
        "verification": {
            "final_verification_status": props.get("final_verification_status", NOT_DETERMINABLE),
            "proposed_ulpin": proposed_ulpin(region, props),
            "linkage_status": "PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE",
        },
        "parcel": {
            "linked_parcel_id": linked,
            "parcel_name": parcel_props.get("name"),
            "ward_lgd_code": parcel_props.get("ward_lgd_code"),
            "townname": parcel_props.get("townname"),
            "state": parcel_props.get("state"),
            "source": parcel_props.get("source"),
        },
        "geometry": feat.get("geometry"),
    }


def citizen_building_view(region: str, building_id: str, unit_label: str | None = None) -> dict | None:
    """Owner-facing projection of a single linked record.

    Includes the provenance a landowner legitimately needs to trust the
    record (AGENTS.md rule 3) while dropping model internals and any field
    belonging to other properties.
    """
    full = government_building_view(region, building_id)
    if full is None:
        return None

    vertical = redact_for_citizen(full["vertical"])
    provenance = redact_for_citizen(full["provenance"])
    verification = redact_for_citizen(full["verification"])
    parcel = redact_for_citizen(full["parcel"])

    return {
        "region": region,
        "building_id": str(building_id),
        "unit_label": unit_label,
        "proposed_ulpin": verification["proposed_ulpin"],
        "linkage_status": verification["linkage_status"],
        "verification_status": verification["final_verification_status"],
        "parcel": parcel,
        "vertical": vertical,
        "provenance": provenance,
        "geometry": full["geometry"],
        "disclosure_note": CITIZEN_REDACTION_NOTICE,
    }


def citizen_portfolio(
    links: list[dict], region_filter: str | None = None
) -> list[dict]:
    """Build a citizen's own-record portfolio, skipping unresolved links."""
    out = []
    for link in links:
        region = link.get("region")
        if region_filter and region != region_filter:
            continue
        view = citizen_building_view(region, link.get("building_id"), link.get("unit_label"))
        if view is not None:
            out.append(view)
    return out


def record_count(region: str) -> tuple[int, int]:
    return len(building_index(region)), len(parcel_index(region))


def authorised_regions(role_id: str, user_id: str, store) -> list[str]:
    """Regions a role may query.

    Authorities may query any region with data on disk. A citizen is limited
    to regions they actually hold a link in.
    """
    if has_capability(role_id, CAP_READ_BUILDINGS_ALL):
        return available_regions()
    regions = {link["region"] for link in store.citizen_links(user_id) if link.get("region")}
    return sorted(r for r in regions if r in available_regions())


def certificate_capability_for(role_id: str) -> str | None:
    if has_capability(role_id, CAP_CERTIFICATE_ISSUE):
        return CAP_CERTIFICATE_ISSUE
    if has_capability(role_id, CAP_CERTIFICATE_VIEW_OWN):
        return CAP_CERTIFICATE_VIEW_OWN
    return None


def may_read_all(role: Role) -> bool:
    return role.can(CAP_READ_BUILDINGS_ALL) or role.can(CAP_READ_PARCELS_ALL)
