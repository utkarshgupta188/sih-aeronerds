"""
Contract test: Phase 12 (v3) output <-> frontend floor panel / map layers.

Verifies the geojson the frontend reads carries the expected fields and the
"no hallucinated floors" invariant:
  OBSERVED / PREDICTED -> exactly floor_count_estimated proposed IDs (with parcel)
  NOT_DETERMINABLE     -> no count, no confidence, no IDs
Skipped unless Phase 12 has run.
"""

import json
import os

import pytest

_GEOJSON = os.path.join(os.path.dirname(__file__), "..", "frontend", "data", "buildings_3d.geojson")

FRONTEND_READS = [
    "id", "linked_parcel_id", "building_height_m", "ground_elevation_m",
    "floor_detection_status", "floor_count_estimated", "floor_min", "floor_max",
    "floor_confidence", "floor_confidence_pct", "floor_confidence_state", "floor_source",
    "floor_detection_method", "floor_detection_reason", "floor_supporting_evidence",
    "floor_missing_evidence", "floor_vertical_context", "floor_ood_flag",
    "requires_human_verification", "floor_level_ids",
]


def _load():
    if not os.path.exists(_GEOJSON):
        pytest.skip("frontend geojson missing (run the pipeline)")
    with open(_GEOJSON, encoding="utf-8") as fh:
        d = json.load(fh)
    feats = d.get("features", [])
    if not feats or "floor_detection_status" not in feats[0]["properties"]:
        pytest.skip("Phase 12 (v3) not run on this geojson")
    return feats


def test_frontend_field_contract():
    for f in _load():
        p = f["properties"]
        for k in FRONTEND_READS:
            assert k in p, f"{p.get('id')} missing {k}"


def test_status_invariants():
    seen = {"OBSERVED": 0, "PREDICTED": 0, "NOT_DETERMINABLE": 0}
    states = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "NOT_DETERMINABLE": 0}
    for f in _load():
        p = f["properties"]
        st = p["floor_detection_status"]
        state = p["floor_confidence_state"]
        assert st in seen
        seen[st] += 1
        states[state] = states.get(state, 0) + 1
        ids = p.get("floor_level_ids") or []
        if st == "NOT_DETERMINABLE":
            assert p["floor_count_estimated"] is None
            assert p["floor_confidence"] is None
            assert state == "NOT_DETERMINABLE"
            assert ids == [], f"{p['id']} NOT_DETERMINABLE with {len(ids)} IDs"
            assert p["requires_human_verification"] is True
        else:
            n = p["floor_count_estimated"]
            assert isinstance(n, int) and n >= 1
            assert p["floor_min"] <= n <= p["floor_max"]
            if st == "OBSERVED":
                assert p["floor_source"] == "REAL_OSM_BUILDING_LEVELS"
                assert p["floor_confidence"] is None       # a real tag, no model prob
                assert state in ("HIGH", "MEDIUM")
            else:  # PREDICTED
                assert p["floor_source"] == "ML_MODEL"
                assert isinstance(p["floor_confidence"], float)   # calibrated probability
                assert 0.0 < p["floor_confidence"] < 1.0
                assert state in ("HIGH", "MEDIUM", "LOW")
                assert p["requires_human_verification"] is True   # every ML tier verifies
            # LOW-confidence ML predictions are shown but get NO floor-level IDs
            expect_ids = p.get("linked_parcel_id") and not (st == "PREDICTED" and state == "LOW")
            if expect_ids:
                assert len(ids) == n
                assert all(x["status"] == "PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE" for x in ids)
            elif st == "PREDICTED" and state == "LOW":
                assert ids == [], f"{p['id']} LOW-confidence prediction has {len(ids)} IDs"
    # every state genuinely occurs -> a healthy OBSERVED / PREDICTED / ND mixture
    assert seen["OBSERVED"] >= 1 and seen["PREDICTED"] >= 1 and seen["NOT_DETERMINABLE"] >= 1
    assert states["MEDIUM"] >= 1 and states["LOW"] >= 1


def test_floor_ids_unique_and_deterministic_format():
    for f in _load():
        ids = [x["proposed_floor_spatial_id"] for x in (f["properties"].get("floor_level_ids") or [])]
        assert len(ids) == len(set(ids))
        for i, sid in enumerate(ids, start=1):
            assert sid.startswith("IN-KA-BLR-P") and sid.endswith(f"-F{i}"), sid


def test_no_fabricated_confidence_percentage_string():
    for f in _load():
        p = f["properties"]
        # OBSERVED / NOT_DETERMINABLE carry no numeric confidence
        if p["floor_detection_status"] != "PREDICTED":
            assert p.get("floor_confidence") is None
            assert p.get("floor_prediction_score") is None


def test_vegetation_dominant_never_yields_a_prediction():
    for f in _load():
        p = f["properties"]
        if p.get("vegetation_pattern") == "VEGETATION_DOMINANT" and p["floor_detection_status"] == "PREDICTED":
            raise AssertionError(f"{p['id']}: predicted despite vegetation-dominant NDVI")
