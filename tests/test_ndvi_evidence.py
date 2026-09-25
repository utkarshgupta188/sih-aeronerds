"""
Validation for the additive NDVI vegetation-evidence / building-height-confidence
layer (scripts/ndvi_evidence.py).

Covers the scenarios required by the task:
  - clearly built-up building
  - building surrounded by trees (bare roof, vegetated edge)
  - building footprint with partial vegetation overlap
  - vegetation-heavy area
  - NoData NDVI
  - mixed / edge pixels
  - unusually tall Copernicus-derived elevation
  - NDVI layer unavailable  (no fabricated confidence)
  - determinism + bounded output + preservation of existing fields
"""

import ndvi_evidence as ne
import numpy as np
import pytest


def _eval(values, n_intersecting=None, **kw):
    n_intersecting = len(values) if n_intersecting is None else n_intersecting
    stats = ne.footprint_ndvi_stats(values, n_intersecting)
    return stats, ne.evaluate_building(stats, **kw)


# --------------------------------------------------------------------------- #
# 1. Clearly built-up building                                               #
# --------------------------------------------------------------------------- #
def test_clearly_built_up_is_high_and_supported():
    values = [0.05, 0.08, 0.10, 0.06, 0.12, 0.09, 0.07, 0.11, 0.08]
    _stats, r = _eval(
        values,
        match_status_2d="CONTAINED",
        parcel_overlap_ratio=1.0,
        building_height_m=14.2,
        height_confidence="HIGH",
    )
    assert r["vegetation_evidence"] == "LOW_VEGETATION"
    assert r["building_height_confidence"] == "HIGH"
    assert r["vertical_evidence_status"] == "SUPPORTED"
    assert r["ndvi_review_recommendation"] == "NONE"
    assert 0.0 <= r["building_height_confidence_score"] <= 1.0
    assert r["building_height_confidence_score"] >= ne.SCORE_HIGH


# --------------------------------------------------------------------------- #
# 2. Building surrounded by trees - bare roof, a few vegetated edge pixels    #
#    A single/handful of edge pixels must NOT invalidate the whole building.  #
# --------------------------------------------------------------------------- #
def test_vegetated_edge_pixels_do_not_invalidate_building():
    # 20 bare roof pixels + 3 vegetated edge pixels
    values = [0.10] * 20 + [0.72, 0.68, 0.75]
    stats, r = _eval(
        values,
        match_status_2d="CONTAINED",
        parcel_overlap_ratio=1.0,
        building_height_m=12.0,
        height_confidence="MEDIUM",
    )
    assert stats["vegetation_fraction"] < 0.20
    assert r["vegetation_evidence"] in ("LOW_VEGETATION", "MIXED_VEGETATION")
    assert r["building_height_confidence"] != "LOW"
    assert r["vertical_evidence_status"] != "VEGETATION_POSSIBLE"


# --------------------------------------------------------------------------- #
# 3. Partial vegetation overlap (~40% of footprint vegetated)                 #
# --------------------------------------------------------------------------- #
def test_partial_vegetation_overlap_is_mixed_medium():
    values = [0.12] * 12 + [0.55, 0.6, 0.65, 0.58, 0.62, 0.5, 0.7, 0.66]  # 8/20 vegetated
    _stats, r = _eval(
        values,
        match_status_2d="MAJORITY",
        parcel_overlap_ratio=0.8,
        building_height_m=10.5,
        height_confidence="MEDIUM",
    )
    assert r["vegetation_evidence"] == "MIXED_VEGETATION"
    assert r["building_height_confidence"] == "MEDIUM"
    assert r["vertical_evidence_status"] == "PROVISIONAL"
    # Item 9: MIXED vertical confidence -> human verification required.
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


# --------------------------------------------------------------------------- #
# 4. Vegetation-heavy area (elevation is probably canopy, not a building)     #
# --------------------------------------------------------------------------- #
def test_vegetation_heavy_area_is_low_and_flags_review():
    values = [0.62, 0.7, 0.75, 0.68, 0.8, 0.72, 0.66, 0.78, 0.71, 0.69]
    _stats, r = _eval(
        values,
        match_status_2d="CONTAINED",
        parcel_overlap_ratio=1.0,
        building_height_m=14.2,
        height_confidence="MEDIUM",
    )
    assert r["vegetation_evidence"] == "STRONG_VEGETATION"
    assert r["building_height_confidence"] == "LOW"
    assert r["vertical_evidence_status"] == "VEGETATION_POSSIBLE"
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"
    assert 0.0 <= r["building_height_confidence_score"] <= 1.0


# --------------------------------------------------------------------------- #
# 5. NoData NDVI - nothing valid inside the footprint                        #
# --------------------------------------------------------------------------- #
def test_all_nodata_is_not_determinable_without_fabrication():
    stats = ne.footprint_ndvi_stats([], n_intersecting=25)
    r = ne.evaluate_building(
        stats,
        match_status_2d="CONTAINED",
        parcel_overlap_ratio=1.0,
        building_height_m=9.0,
    )
    assert stats["n_valid"] == 0
    assert stats["nodata_fraction"] == 1.0
    assert r["vegetation_evidence"] == "NOT_DETERMINABLE"
    assert r["building_height_confidence"] == "NOT_DETERMINABLE"
    assert r["vertical_evidence_status"] == "NOT_DETERMINABLE"
    assert r["building_height_confidence_score"] is None          # NOT fabricated
    assert r["building_height_confidence_score_100"] is None
    assert r["ndvi_data_quality_flag"] == "INSUFFICIENT_NDVI"
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


def test_mostly_nodata_over_gate_is_not_determinable():
    # 2 valid pixels, 30 intersecting -> nodata_fraction ~0.94
    _stats, r = _eval([0.1, 0.12], n_intersecting=30, match_status_2d="CONTAINED")
    assert r["building_height_confidence"] == "NOT_DETERMINABLE"
    assert r["building_height_confidence_score"] is None
    assert r["ndvi_data_quality_flag"] == "INSUFFICIENT_NDVI"


# --------------------------------------------------------------------------- #
# 6. Mixed / edge pixels - high internal NDVI variance                       #
# --------------------------------------------------------------------------- #
def test_mixed_edge_pixels_do_not_crash_and_lower_consistency():
    values = [0.05, 0.75, 0.08, 0.7, 0.1, 0.8, 0.06, 0.72, 0.09, 0.68]  # 50/50 split
    stats, r = _eval(
        values,
        match_status_2d="BOUNDARY_OVERLAP",
        parcel_overlap_ratio=0.45,
        building_height_m=8.0,
        height_confidence="MEDIUM",
    )
    assert stats["ndvi_iqr"] is not None and stats["ndvi_iqr"] > 0.3
    assert r["building_height_confidence_subscores"]["consistency"] < 0.3
    assert r["building_height_confidence"] in ("LOW", "MEDIUM")
    assert 0.0 <= r["building_height_confidence_score"] <= 1.0


# --------------------------------------------------------------------------- #
# 7. Unusually tall Copernicus-derived elevation                             #
# --------------------------------------------------------------------------- #
def test_unusually_tall_height_cannot_be_high_when_any_vegetation():
    # Bare-ish roof but with some vegetation signal + a 95 m derived height.
    values = [0.18, 0.22, 0.25, 0.2, 0.28, 0.24, 0.19, 0.26, 0.21, 0.3]
    _stats, r = _eval(
        values,
        match_status_2d="CONTAINED",
        parcel_overlap_ratio=1.0,
        building_height_m=95.0,
        height_confidence="MEDIUM",
    )
    assert r["vegetation_evidence"] != "LOW_VEGETATION"
    assert r["building_height_confidence"] != "HIGH"
    assert "unusually tall" in r["confidence_reason"]


def test_physically_implausible_height_weakens_elevation_subscore():
    values = [0.08] * 12
    _, r_ok = _eval(values, match_status_2d="CONTAINED", parcel_overlap_ratio=1.0,
                    building_height_m=15.0, height_confidence="MEDIUM")
    _, r_absurd = _eval(values, match_status_2d="CONTAINED", parcel_overlap_ratio=1.0,
                        building_height_m=400.0, height_confidence="MEDIUM")
    assert (r_absurd["building_height_confidence_subscores"]["elevation"]
            < r_ok["building_height_confidence_subscores"]["elevation"])


# --------------------------------------------------------------------------- #
# 8. NDVI layer unavailable - report the gap, never fabricate                #
# --------------------------------------------------------------------------- #
def test_ndvi_unavailable_produces_no_fabricated_confidence():
    r = ne.evaluate_building(
        {},
        match_status_2d="CONTAINED",
        parcel_overlap_ratio=1.0,
        building_height_m=14.2,
        ndvi_available=False,
        ndvi_unavailable_reason="STAC search returned no scenes",
    )
    assert r["vegetation_evidence"] == "NOT_COMPUTED"
    assert r["vertical_evidence_status"] == "NDVI_UNAVAILABLE"
    assert r["ndvi_data_quality_flag"] == "NDVI_LAYER_UNAVAILABLE"
    assert r["building_height_confidence_score"] is None
    assert r["building_height_confidence_score_100"] is None
    assert r["ndvi_value"] is None
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"
    assert "could not be computed" in r["confidence_reason"]


# --------------------------------------------------------------------------- #
# 9. Determinism + bounded output                                            #
# --------------------------------------------------------------------------- #
def test_determinism():
    values = [0.1, 0.4, 0.2, 0.6, 0.15, 0.55, 0.3]
    a = _eval(values, match_status_2d="MAJORITY", parcel_overlap_ratio=0.7,
              building_height_m=11.0)[1]
    b = _eval(values, match_status_2d="MAJORITY", parcel_overlap_ratio=0.7,
              building_height_m=11.0)[1]
    assert a == b


@pytest.mark.parametrize("seed", range(25))
def test_score_always_bounded(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(3, 60))
    values = list(rng.uniform(-0.2, 0.95, size=n))
    n_int = n + int(rng.integers(0, 20))
    ms = rng.choice(["CONTAINED", "MAJORITY", "BOUNDARY_OVERLAP", "NO_PARCEL", "UNKNOWN"])
    h = rng.choice([None, 3.5, 10.0, 45.0, 90.0, 300.0])
    _, r = _eval(values, n_intersecting=n_int, match_status_2d=ms,
                 parcel_overlap_ratio=float(rng.uniform(0, 1)),
                 building_height_m=h, height_confidence=rng.choice(["HIGH", "MEDIUM", "LOW"]))
    s = r["building_height_confidence_score"]
    if s is not None:
        assert 0.0 <= s <= 1.0
        assert 0 <= r["building_height_confidence_score_100"] <= 100
        for v in r["building_height_confidence_subscores"].values():
            assert 0.0 <= v <= 1.0
    assert r["building_height_confidence"] in ("HIGH", "MEDIUM", "LOW", "NOT_DETERMINABLE")
    assert r["vertical_evidence_status"] in (
        "SUPPORTED", "PROVISIONAL", "VEGETATION_POSSIBLE", "NOT_DETERMINABLE", "NDVI_UNAVAILABLE")


# --------------------------------------------------------------------------- #
# 10. Existing fields are preserved (additive merge only)                    #
# --------------------------------------------------------------------------- #
def test_merge_preserves_existing_properties():
    # The merge helper lives in the phase script; load it by file path to avoid
    # the leading-digit module-name problem.
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "scripts",
                        "11_ndvi_vegetation_evidence.py")
    spec = importlib.util.spec_from_file_location("phase11", path)
    phase11 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(phase11)

    original = {
        "id": "osm_way_123",
        "ground_elevation_m": 904.19,
        "building_height_m": 7.0,
        "match_status_2d": "CONTAINED",
        "final_verification_status": "VERIFIED",
        "height_source": "GOOGLE_OPEN_BUILDINGS_2.5D",
    }
    evidence = ne.evaluate_building(
        ne.footprint_ndvi_stats([0.08, 0.1, 0.09, 0.11, 0.07], 5),
        match_status_2d="CONTAINED", parcel_overlap_ratio=1.0, building_height_m=7.0,
    )
    merged = phase11.merge_evidence_into_properties(dict(original), evidence,
                                                   scene_meta=phase11.NDVI_UNAVAILABLE_META)
    for k, v in original.items():
        assert merged[k] == v, f"existing field {k} was modified"
    assert merged["ground_elevation_m"] == 904.19          # Copernicus value intact
    assert merged["building_height_m"] == 7.0
    assert merged["final_verification_status"] == "VERIFIED"  # existing gate untouched
    assert "vegetation_evidence" in merged
    assert "building_height_confidence" in merged
