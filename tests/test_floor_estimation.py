"""
Validation for the floor-detection layer (scripts/floor_estimation.py, v3 = ML).

All inputs are MOCKED numeric values used only to exercise code paths - NOT real
buildings, NOT real floor counts, NOT training/validation data, NOT performance
evidence. The real model is trained by scripts/train_floor_model.py on real OSM
labels; here we hand the classifier pre-computed ``model_score`` dicts so the
acceptance / rejection logic can be tested without the sklearn artifact.

Core rules under test:
  OBSERVED        <- real OSM building:levels tag on the building.
  PREDICTED       <- model score clears the calibrated-confidence + narrow-range
                     bar, is in-distribution, and is not just the base-rate mode.
  NOT_DETERMINABLE <- everything else. No floor count, no floor-level IDs.
  floor_confidence is a real calibrated probability for PREDICTED, None otherwise.
"""

import floor_estimation as fe
import pytest

BUNDLE = {
    "accept_high": 0.70, "accept_medium": 0.58, "accept_low": 0.45,
    "accept_range_high": 2, "accept_range_medium": 3, "accept_range_low": 4,
    "training_mode_floor": 2, "chosen_model_name": "hist_gradient_boosting", "train_size": 8441,
}
FEAT_NO_HT = {"has_height_tag": 0, "has_dsm_height": 1, "type_residential": 1,
              "type_commercial": 0, "type_civic": 0, "type_industrial": 0, "type_other": 0}
FEAT_HT = dict(FEAT_NO_HT, has_height_tag=1)


def _c(**kw):
    kw.setdefault("building_id", "osm_way_1")
    kw.setdefault("linked_parcel_id", "cadastral_parcel_9")
    kw.setdefault("model_bundle", BUNDLE)
    return fe.classify(**kw)


def _score(point, spread=0.6, confidence=0.75, ood=False):
    return {"point": point, "spread": spread, "confidence": confidence, "ood": ood}


# --------------------------------------------------------------------------- #
# OBSERVED - real OSM building:levels tag                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("levels", [1, 2, 3, 4, 5])
def test_real_osm_levels_are_observed(levels):
    r = _c(real_osm_levels=float(levels), real_osm_levels_verified=True,
           building_height_m=levels * 3.2)
    assert r["floor_detection_status"] == "OBSERVED"
    assert r["floor_source"] == "REAL_OSM_BUILDING_LEVELS"
    assert r["floor_count_estimated"] == levels == r["floor_min"] == r["floor_max"]
    assert r["floor_confidence"] is None            # a real tag, not a model probability
    assert r["floor_confidence_state"] == "HIGH"
    assert r["requires_human_verification"] is False
    assert len(r["floor_level_ids"]) == levels
    assert all(x["status"] == "PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE" for x in r["floor_level_ids"])


def test_levels_not_verified_is_not_observed():
    r = _c(real_osm_levels=4.0, real_osm_levels_verified=False, building_height_m=13.0)
    assert r["floor_detection_status"] == "NOT_DETERMINABLE"


def test_observed_with_diverging_height_needs_verification():
    r = _c(real_osm_levels=11.0, real_osm_levels_verified=True, building_height_m=7.0)
    assert r["floor_detection_status"] == "OBSERVED"
    assert r["floor_count_estimated"] == 11
    assert r["floor_height_consistency"] == "DIVERGENT"
    assert r["floor_confidence_state"] == "MEDIUM"
    assert r["requires_human_verification"] is True


def test_observed_with_vegetation_dominant_flags_context():
    r = _c(real_osm_levels=4.0, real_osm_levels_verified=True, building_height_m=13.0,
           vegetation_pattern="VEGETATION_DOMINANT")
    assert r["floor_detection_status"] == "OBSERVED"      # tag independent of height
    assert r["floor_count_estimated"] == 4
    assert r["floor_vertical_context"] == "VEGETATION_CONTAMINATED_HEIGHT"
    assert r["requires_human_verification"] is True


# --------------------------------------------------------------------------- #
# PREDICTED - model score clears the bar                                      #
# --------------------------------------------------------------------------- #
def test_predicted_high_when_very_confident_and_tight():
    r = _c(features=FEAT_NO_HT, model_score=_score(5.0, spread=0.4, confidence=0.72))
    assert r["floor_detection_status"] == "PREDICTED"
    assert r["floor_source"] == "ML_MODEL"
    assert r["floor_count_estimated"] == 5
    assert r["floor_min"] <= 5 <= r["floor_max"]
    assert (r["floor_max"] - r["floor_min"]) <= BUNDLE["accept_range_high"]
    assert r["floor_confidence"] == pytest.approx(0.72)   # real calibrated probability
    assert r["floor_confidence_pct"] == 72
    assert r["floor_confidence_state"] == "HIGH"
    assert r["requires_human_verification"] is True       # ML predictions always human-verify
    assert len(r["floor_level_ids"]) == 5
    assert any("model" in s.lower() for s in r["floor_supporting_evidence"])
    assert "ESTIMATE" in r["floor_detection_reason"]


def test_predicted_medium_when_above_base_rate():
    r = _c(features=FEAT_NO_HT, model_score=_score(3.0, spread=1.0, confidence=0.63))
    assert r["floor_detection_status"] == "PREDICTED"
    assert r["floor_confidence_state"] == "MEDIUM"
    assert r["floor_level_ids"]                            # MEDIUM still gets IDs
    assert r["floor_confidence"] == pytest.approx(0.63)


def test_predicted_low_is_shown_but_gets_no_ids():
    r = _c(features=FEAT_NO_HT, model_score=_score(4.0, spread=1.6, confidence=0.50))
    assert r["floor_detection_status"] == "PREDICTED"
    assert r["floor_confidence_state"] == "LOW"
    assert r["floor_count_estimated"] == 4
    assert r["floor_level_ids"] == []                      # no IDs for LOW
    assert "no floor-level IDs" in r["floor_detection_reason"]
    assert r["requires_human_verification"] is True


def test_predicted_rejected_below_low_threshold():
    r = _c(features=FEAT_NO_HT, model_score=_score(4.0, confidence=0.40))
    assert r["floor_detection_status"] == "NOT_DETERMINABLE"
    assert r["floor_count_estimated"] is None
    assert r["floor_confidence"] is None
    assert r["floor_level_ids"] == []
    assert "abstains" in r["floor_detection_reason"]


def test_predicted_rejected_when_range_too_wide():
    r = _c(features=FEAT_NO_HT, model_score=_score(6.0, spread=3.2, confidence=0.9))
    assert r["floor_detection_status"] == "NOT_DETERMINABLE"
    assert "too wide" in r["floor_detection_reason"]


def test_predicted_rejected_out_of_distribution():
    r = _c(features=FEAT_NO_HT, model_score=_score(4.0, confidence=0.9, ood=True))
    assert r["floor_detection_status"] == "NOT_DETERMINABLE"
    assert "training distribution" in r["floor_detection_reason"]


def test_predicted_rejected_vegetation_dominant():
    r = _c(features=FEAT_NO_HT, model_score=_score(5.0, confidence=0.9),
           vegetation_pattern="VEGETATION_DOMINANT")
    assert r["floor_detection_status"] == "NOT_DETERMINABLE"
    assert r["floor_vertical_context"] == "VEGETATION_CONTAMINATED_HEIGHT"


def test_no_model_and_no_features_is_not_determinable():
    r = fe.classify(building_id="b", linked_parcel_id="p", model_bundle=None)
    assert r["floor_detection_status"] == "NOT_DETERMINABLE"
    assert r["floor_count_estimated"] is None
    assert r["floor_missing_evidence"]


# --------------------------------------------------------------------------- #
# Proposed floor-level IDs                                                    #
# --------------------------------------------------------------------------- #
def test_ids_deterministic_and_labelled():
    r = _c(building_id="osm_way_347483369", linked_parcel_id="cadastral_parcel_22048",
           real_osm_levels=4.0, real_osm_levels_verified=True, building_height_m=13.0)
    ids = [x["proposed_floor_spatial_id"] for x in r["floor_level_ids"]]
    assert ids == [f"IN-KA-BLR-P22048-B347483369-F{i}" for i in (1, 2, 3, 4)]
    assert len(ids) == len(set(ids))


def test_no_parcel_no_ids():
    r = _c(linked_parcel_id=None, real_osm_levels=3.0, real_osm_levels_verified=True,
           building_height_m=10.0)
    assert r["floor_count_estimated"] == 3
    assert r["floor_level_ids"] == []


def test_not_determinable_never_has_ids():
    r = _c(features=FEAT_NO_HT, model_score=_score(4.0, confidence=0.4))
    assert r["floor_level_ids"] == []


def test_determinism():
    a = _c(features=FEAT_NO_HT, model_score=_score(5.0, 0.5, 0.72))
    b = _c(features=FEAT_NO_HT, model_score=_score(5.0, 0.5, 0.72))
    assert a == b


def test_no_fabricated_confidence_number_on_observed_or_nd():
    obs = _c(real_osm_levels=3.0, real_osm_levels_verified=True, building_height_m=9.6)
    nd = _c(features=FEAT_NO_HT, model_score=_score(4.0, confidence=0.3))
    assert obs["floor_confidence"] is None and obs["floor_prediction_score"] is None
    assert nd["floor_confidence"] is None and nd["floor_prediction_score"] is None


def test_method_manifest():
    m = fe.method_manifest(BUNDLE)
    assert m["cnn_used"] is False
    assert "no synthetic" in m["no_synthetic_data"].lower()
    assert m["train_size"] == 8441


def test_phase12_merge_preserves_existing_fields():
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "12_estimate_floors.py")
    spec = importlib.util.spec_from_file_location("phase12", path)
    phase12 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(phase12)

    original = {"id": "osm_way_5", "building_height_m": 14.0, "derived_floors": 4,
                "building_levels": None, "ground_elevation_m": 900.0,
                "match_status_2d": "CONTAINED", "final_verification_status": "VERIFIED"}
    floor = fe.classify(building_id="osm_way_5", linked_parcel_id="cadastral_parcel_2",
                        model_bundle=None)
    merged = phase12.merge_floor_fields(dict(original), floor)
    for k, v in original.items():
        assert merged[k] == v, f"existing field {k} was modified"
    assert merged["floor_detection_status"] == "NOT_DETERMINABLE"
    assert "floor_count_estimated" in merged
