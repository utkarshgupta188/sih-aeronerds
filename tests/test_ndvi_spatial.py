"""
Validation for the spatially-resolved NDVI evaluation (``evaluate_building_spatial``).

Core principle under test:
    Vegetation NEAR a building (edge / ring) must NOT by itself lower
    building-height confidence. Only vegetation dominating the building SURFACE
    (core / interior) does. Genuinely unresolvable cases return
    NOT_DETERMINABLE / RESOLUTION_LIMITED - never a fabricated classification.
"""

import ndvi_evidence as ne
import numpy as np
import pytest

PX = 100.0  # one 10 m NDVI pixel, m^2


def _zone(values, extra_nodata=0):
    return ne.footprint_ndvi_stats(list(values), len(list(values)) + extra_nodata)


def _zones(core=None, interior=None, edge=None, ring=None, fp_area=600.0):
    empty = ne.footprint_ndvi_stats([], 0)
    return {
        "core": _zone(core) if core is not None else empty,
        "interior": _zone(interior) if interior is not None else empty,
        "edge": _zone(edge) if edge is not None else empty,
        "ring": _zone(ring) if ring is not None else empty,
        "footprint_area_m2": fp_area,
        "pixel_area_m2": PX,
    }


LOW = [0.08, 0.10, 0.09, 0.11, 0.07, 0.12, 0.10, 0.09]
MIXED = [0.10, 0.12, 0.33, 0.30, 0.11, 0.28, 0.35, 0.14]
HIGH = [0.62, 0.70, 0.68, 0.75, 0.66, 0.72, 0.71, 0.69]


def _ev(zones, **kw):
    kw.setdefault("match_status_2d", "CONTAINED")
    kw.setdefault("parcel_overlap_ratio", 1.0)
    kw.setdefault("building_height_m", 12.0)
    kw.setdefault("height_confidence", "MEDIUM")
    return ne.evaluate_building_spatial(zones, **kw)


# --------------------------------------------------------------------------- #
# 1. THE REGRESSION PATTERN: real building surrounded by trees                #
#    core LOW, interior LOW, edge HIGH, ring HIGH                             #
# --------------------------------------------------------------------------- #
def test_building_surrounded_by_trees_is_not_vegetation_possible():
    z = _zones(core=LOW, interior=LOW, edge=HIGH, ring=HIGH, fp_area=800.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "SURROUNDING_VEGETATION"
    assert r["vegetation_evidence_label"] == "Surrounding vegetation"
    assert r["building_height_confidence"] in ("HIGH", "MEDIUM")
    assert r["vertical_evidence_status"] in ("SUPPORTED", "PROVISIONAL")
    assert r["vertical_evidence_status"] != "VEGETATION_POSSIBLE"
    assert "outside the building footprint" in r["confidence_reason"]


def test_building_with_trees_touching_boundary_only():
    z = _zones(core=LOW, interior=LOW, edge=HIGH, ring=MIXED, fp_area=700.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "SURROUNDING_VEGETATION"
    assert r["building_height_confidence"] != "LOW"


def test_screenshot_pattern_no_core_fully_vegetated_footprint_is_not_vegetation_possible():
    # The reported regression: a real ~mid-size building with no resolvable core,
    # whose entire 10 m footprint sample reads vegetated, ringed by trees.
    # Flat NDVI -> STRONG_VEGETATION -> LOW -> "VEGETATION POSSIBLE".
    # Spatial -> must NOT be VEGETATION_POSSIBLE unless vegetation *uniformly*
    # dominates (vf >= 0.85); otherwise MIXED -> PROVISIONAL + human verification.
    partial = [0.45, 0.5, 0.42, 0.55, 0.3, 0.25, 0.6, 0.48]  # veg-fraction ~0.6-0.75
    z = _zones(core=None, interior=partial, edge=HIGH, ring=HIGH, fp_area=650.0)
    r = _ev(z, building_height_m=14.0, height_confidence="MEDIUM")
    assert r["vegetation_pattern"] in ("MIXED_VEGETATION", "EDGE_VEGETATION")
    assert r["vertical_evidence_status"] != "VEGETATION_POSSIBLE"
    assert r["building_height_confidence"] in ("MEDIUM", "NOT_DETERMINABLE")
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


def test_clean_building_no_vegetation_anywhere_is_high():
    z = _zones(core=LOW, interior=LOW, edge=LOW, ring=LOW, fp_area=900.0)
    r = _ev(z, height_confidence="HIGH")
    assert r["vegetation_pattern"] == "LOW_VEGETATION"
    assert r["building_height_confidence"] == "HIGH"
    assert r["vertical_evidence_status"] == "SUPPORTED"
    assert r["ndvi_review_recommendation"] == "NONE"


# --------------------------------------------------------------------------- #
# 2. Edge vegetation - core clearer than interior                            #
# --------------------------------------------------------------------------- #
def test_edge_vegetation_is_mixed_not_low():
    z = _zones(core=LOW, interior=MIXED, edge=HIGH, ring=HIGH, fp_area=700.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "EDGE_VEGETATION"
    assert r["building_height_confidence"] == "MEDIUM"
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


# --------------------------------------------------------------------------- #
# 3. Internal vegetation - inside footprint but not around it                 #
# --------------------------------------------------------------------------- #
def test_internal_vegetation_not_auto_tree():
    z = _zones(core=HIGH, interior=HIGH, edge=LOW, ring=LOW, fp_area=1200.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "INTERNAL_VEGETATION"
    assert r["building_height_confidence"] != "LOW"  # courtyard / green roof, not a tree
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


def test_internal_mixed_vegetation_with_clear_surroundings():
    z = _zones(core=LOW, interior=MIXED, edge=LOW, ring=LOW, fp_area=800.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "INTERNAL_VEGETATION"
    assert r["building_height_confidence"] in ("MEDIUM", "LOW")


# --------------------------------------------------------------------------- #
# 4. Vegetation dominant - genuine contamination stays LOW                    #
# --------------------------------------------------------------------------- #
def test_vegetation_dominant_everywhere_is_low():
    z = _zones(core=HIGH, interior=HIGH, edge=HIGH, ring=HIGH, fp_area=900.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "VEGETATION_DOMINANT"
    assert r["building_height_confidence"] == "LOW"
    assert r["vertical_evidence_status"] == "VEGETATION_POSSIBLE"
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


def test_vegetation_dominant_score_bounded():
    z = _zones(core=HIGH, interior=HIGH, edge=HIGH, ring=HIGH)
    r = _ev(z)
    assert 0.0 <= r["building_height_confidence_score"] <= 1.0


# --------------------------------------------------------------------------- #
# 5. Small building below NDVI resolution -> RESOLUTION_LIMITED               #
# --------------------------------------------------------------------------- #
def test_small_building_no_core_is_resolution_limited():
    # footprint ~1 pixel, only 2 interior valid pixels, no core
    z = _zones(core=None, interior=[0.55, 0.60], edge=HIGH, ring=HIGH, fp_area=120.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "RESOLUTION_LIMITED"
    assert r["building_height_confidence"] == "NOT_DETERMINABLE"
    assert r["vertical_evidence_status"] == "NOT_DETERMINABLE"
    assert r["building_height_confidence_score"] is None          # NOT fabricated
    assert r["ndvi_data_quality_flag"] == "RESOLUTION_LIMITED"
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


def test_tiny_building_uniform_dense_canopy_is_not_asserted_as_canopy():
    # Sub-pixel footprint (~1 px), no core: even if every touched pixel is dense
    # vegetation we cannot see a roof, so we must NOT assert VEGETATION_DOMINANT
    # ("elevation is canopy"). It is mixed / unresolvable -> reviewer decides.
    dense = [0.75, 0.78, 0.80, 0.77, 0.79]
    z = _zones(core=None, interior=dense, edge=dense, ring=dense, fp_area=110.0)
    r = _ev(z)
    assert r["vegetation_pattern"] in ("MIXED_VEGETATION", "RESOLUTION_LIMITED")
    assert r["building_height_confidence"] != "LOW"
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


def test_large_footprint_mostly_roof_is_not_vegetation_dominant():
    # Regression: a big building whose thin eroded core clips overhanging trees
    # (core HIGH) but whose full footprint is mostly bare roof must NOT be LOW.
    roof_heavy = [0.10, 0.12, 0.15, 0.09, 0.13, 0.11, 0.55, 0.6, 0.5, 0.58]  # veg-frac 0.4
    z = _zones(core=[0.5, 0.52, 0.48, 0.51], interior=roof_heavy,
               edge=[0.4, 0.45, 0.5], ring=HIGH, fp_area=2500.0)
    r = _ev(z, building_height_m=14.0)
    assert r["vegetation_pattern"] == "MIXED_VEGETATION"
    assert r["building_height_confidence"] in ("MEDIUM", "NOT_DETERMINABLE")
    assert r["vertical_evidence_status"] != "VEGETATION_POSSIBLE"


def test_larger_building_without_core_still_evaluated():
    # 4-pixel footprint, no eroded core, interior LOW, ring HIGH -> surrounding
    z = _zones(core=None, interior=LOW, edge=HIGH, ring=HIGH, fp_area=420.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "SURROUNDING_VEGETATION"
    assert r["building_height_confidence"] != "LOW"


# --------------------------------------------------------------------------- #
# 6. NoData / insufficient                                                    #
# --------------------------------------------------------------------------- #
def test_no_valid_interior_pixels_is_not_determinable():
    z = _zones(core=None, interior=None, edge=HIGH, ring=HIGH, fp_area=500.0)
    r = _ev(z)
    assert r["vegetation_pattern"] == "NOT_DETERMINABLE"
    assert r["building_height_confidence"] == "NOT_DETERMINABLE"
    assert r["building_height_confidence_score"] is None
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


def test_mostly_nodata_interior_is_not_determinable():
    z = _zones(core=None, interior=[0.1, 0.12], ring=LOW, fp_area=500.0)
    z["interior"] = ne.footprint_ndvi_stats([0.1, 0.12], 30)  # nodata_fraction ~0.93
    r = _ev(z)
    assert r["building_height_confidence"] == "NOT_DETERMINABLE"
    assert r["building_height_confidence_score"] is None


def test_ndvi_unavailable_no_fabrication():
    r = ne.evaluate_building_spatial(
        {}, ndvi_available=False, ndvi_unavailable_reason="STAC empty",
        building_height_m=14.2,
    )
    assert r["vegetation_pattern"] == "NOT_COMPUTED"
    assert r["vertical_evidence_status"] == "NDVI_UNAVAILABLE"
    assert r["ndvi_data_quality_flag"] == "NDVI_LAYER_UNAVAILABLE"
    assert r["building_height_confidence_score"] is None
    assert r["ndvi_value"] is None
    assert r["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED"


# --------------------------------------------------------------------------- #
# 7. Tall Copernicus height                                                   #
# --------------------------------------------------------------------------- #
def test_tall_height_with_surrounding_vegetation_not_downgraded():
    # tall building genuinely surrounded by trees: core LOW -> stays supported.
    z = _zones(core=LOW, interior=LOW, edge=HIGH, ring=HIGH, fp_area=1500.0)
    r = _ev(z, building_height_m=95.0, height_confidence="MEDIUM")
    assert r["vegetation_pattern"] == "SURROUNDING_VEGETATION"
    assert r["building_height_confidence"] != "LOW"
    assert "tall + vegetation nearby" not in r["confidence_reason"].lower()


def test_tall_height_with_vegetated_surface_is_downgraded():
    z = _zones(core=MIXED, interior=MIXED, edge=HIGH, ring=HIGH, fp_area=1500.0)
    r_norm = _ev(_zones(core=MIXED, interior=MIXED, edge=HIGH, ring=HIGH, fp_area=1500.0),
                 building_height_m=12.0)
    r_tall = _ev(z, building_height_m=95.0)
    # tall + ambiguous surface -> cannot be better than the normal-height case
    order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NOT_DETERMINABLE": 0}
    assert order[r_tall["building_height_confidence"]] <= order[r_norm["building_height_confidence"]]
    assert "unusually tall" in r_tall["confidence_reason"]


# --------------------------------------------------------------------------- #
# 8. High NDVI inside but clearly built-up footprint (large, roof visible)    #
# --------------------------------------------------------------------------- #
def test_high_interior_but_clear_core_and_surroundings():
    z = _zones(core=LOW, interior=MIXED, edge=LOW, ring=LOW, fp_area=2000.0)
    r = _ev(z)
    assert r["vegetation_pattern"] in ("INTERNAL_VEGETATION", "MIXED_VEGETATION", "LOW_VEGETATION")
    assert r["building_height_confidence"] != "LOW"


# --------------------------------------------------------------------------- #
# 9. Determinism + bounded output + field preservation                       #
# --------------------------------------------------------------------------- #
def test_spatial_determinism():
    z = _zones(core=LOW, interior=MIXED, edge=HIGH, ring=HIGH)
    assert _ev(z) == _ev(_zones(core=LOW, interior=MIXED, edge=HIGH, ring=HIGH))


@pytest.mark.parametrize("seed", range(30))
def test_spatial_score_always_bounded(seed):
    rng = np.random.default_rng(seed)

    def rz(n):
        return list(rng.uniform(-0.1, 0.95, size=int(rng.integers(0, n))))

    z = {
        "core": _zone(rz(12)),
        "interior": _zone(rz(30), extra_nodata=int(rng.integers(0, 20))),
        "edge": _zone(rz(15)),
        "ring": _zone(rz(40)),
        "footprint_area_m2": float(rng.uniform(60, 4000)),
        "pixel_area_m2": PX,
    }
    r = ne.evaluate_building_spatial(
        z, match_status_2d=rng.choice(["CONTAINED", "MAJORITY", "BOUNDARY_OVERLAP", "NO_PARCEL"]),
        parcel_overlap_ratio=float(rng.uniform(0, 1)),
        building_height_m=rng.choice([None, 3.5, 12.0, 45.0, 90.0, 300.0]),
        height_confidence=rng.choice(["HIGH", "MEDIUM", "LOW"]),
    )
    s = r["building_height_confidence_score"]
    if s is not None:
        assert 0.0 <= s <= 1.0
        assert 0 <= r["building_height_confidence_score_100"] <= 100
        for v in r["building_height_confidence_subscores"].values():
            assert 0.0 <= v <= 1.0
    assert r["building_height_confidence"] in ("HIGH", "MEDIUM", "LOW", "NOT_DETERMINABLE")
    assert r["vertical_evidence_status"] in (
        "SUPPORTED", "PROVISIONAL", "VEGETATION_POSSIBLE", "NOT_DETERMINABLE", "NDVI_UNAVAILABLE")
    assert r["vegetation_pattern"] in (
        "LOW_VEGETATION", "SURROUNDING_VEGETATION", "EDGE_VEGETATION", "INTERNAL_VEGETATION",
        "MIXED_VEGETATION", "VEGETATION_DOMINANT", "RESOLUTION_LIMITED", "NODATA",
        "NOT_DETERMINABLE", "NOT_COMPUTED")


def test_spatial_result_has_zone_levels_and_medians():
    z = _zones(core=LOW, interior=MIXED, edge=HIGH, ring=HIGH)
    r = _ev(z)
    assert set(r["ndvi_zone_levels"]) == {"core", "interior", "edge", "ring"}
    assert r["ndvi_zone_levels"]["core"] == "LOW"
    assert r["ndvi_zone_levels"]["ring"] == "HIGH"
    assert r["ndvi_core_median"] is not None
    assert r["ndvi_ring_median"] is not None


def test_flat_evaluate_building_still_unchanged():
    # The additive spatial path must not have altered the original flat path.
    stats = ne.footprint_ndvi_stats([0.05, 0.08, 0.1, 0.06, 0.12, 0.09], 6)
    r = ne.evaluate_building(stats, match_status_2d="CONTAINED",
                             parcel_overlap_ratio=1.0, building_height_m=14.2,
                             height_confidence="HIGH")
    assert r["vegetation_evidence"] == "LOW_VEGETATION"
    assert r["building_height_confidence"] == "HIGH"
    assert "vegetation_pattern" not in r
