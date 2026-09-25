"""
BoundaryLens - Floor Detection (ADDITIVE layer, v3 = real ML model).

Three sources, per building:

  OBSERVED    - a real OSM ``building:levels`` tag on THIS building. Used as-is
                (Tier-2, crowd-sourced - not municipal legal approval).
  PREDICTED   - the supervised model (scripts/train_floor_model.py, trained on
                ~12.7k real OSM labels across greater Bengaluru with a whole-cell
                spatial split) predicts a count, the footprint is
                in-distribution, and the calibrated P(within +/-1 floor) +
                predicted range clear one of the tiered gates. Always labelled
                ESTIMATED; HIGH / MEDIUM get floor-level IDs, LOW is shown for
                review only (no IDs).
  NOT_DETERMINABLE - no real tag and the model abstains (below the LOW gate,
                range too wide, out-of-distribution footprint, vegetation-
                contaminated, or no usable geometry). No floor count, no IDs.

``floor_confidence`` on a PREDICTED building is the model's **calibrated
empirical probability that the prediction is within +/-1 floor** (isotonic
regression on a held-out validation set) - a real number, not a legal certainty.
OBSERVED buildings have ``floor_confidence = null`` (a real tag, no model).

No synthetic data anywhere. Pure-Python here; the sklearn model is loaded and
passed in by the caller (Phase 12).
"""

from __future__ import annotations

import math

FLOOR_MODEL_VERSION = "boundarylens-floor/v3-ml"
FLOOR_HEIGHT_TYP_M = 3.2          # sanity cross-check only, never a predictor
OOD_FLOOR_COUNT = 40             # OSM labels exist up to ~59; treat very tall as OOD-ish

_VEG_CONTAMINATED = {"VEGETATION_DOMINANT"}


def _as_int_levels(v):
    try:
        f = float(str(v).split(";")[0].strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f < 1 or f > 120 or abs(f - round(f)) > 1e-6:
        return None
    return round(f)


def _proposed_floor_ids(building_id, linked_parcel_id, n_floors):
    """Deterministic proposed floor-level spatial IDs (NOT official ULPINs)."""
    if not n_floors or n_floors < 1:
        return []
    b_num = "".join(ch for ch in str(building_id or "") if ch.isdigit()) or "0"
    p_num = "".join(ch for ch in str(linked_parcel_id or "") if ch.isdigit())
    if not p_num:
        return []
    return [
        {
            "floor_index": i,
            "floor_name": "Ground Floor" if i == 1 else f"Floor {i - 1}",
            "proposed_floor_spatial_id": f"IN-KA-BLR-P{p_num}-B{b_num}-F{i}",
            "status": "PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE",
        }
        for i in range(1, n_floors + 1)
    ]


def _base(**kw):
    """Common shell; kw overrides."""
    est = kw.get("floor_count_estimated")
    conf = kw.get("floor_confidence")
    out = {
        "floor_detection_status": kw["status"],           # OBSERVED | PREDICTED | NOT_DETERMINABLE
        "floor_count_estimated": est,
        "floor_min": kw.get("floor_min"),
        "floor_max": kw.get("floor_max"),
        "floor_confidence": conf,                          # calibrated P(within +/-1) or None
        "floor_confidence_pct": None if conf is None else round(conf * 100),
        "floor_confidence_state": kw["state"],             # HIGH | MEDIUM | NOT_DETERMINABLE
        "floor_source": kw["source"],                      # REAL_OSM_BUILDING_LEVELS | ML_MODEL | NONE
        "floor_detection_method": kw["method"],
        "floor_model_version": FLOOR_MODEL_VERSION,
        "floor_detection_reason": kw["reason"],
        "floor_supporting_evidence": kw.get("supporting", []),
        "floor_missing_evidence": kw.get("missing", []),
        "floor_height_consistency": kw.get("height_consistency", "UNKNOWN"),
        "floor_vertical_context": kw.get("vertical_context", "OK"),
        "floor_ood_flag": bool(kw.get("ood", False)),
        "requires_human_verification": bool(kw.get("hv", kw["status"] != "OBSERVED")),
        "floor_label_source": kw.get("label_source"),
        "floor_label_type": kw.get("label_type"),
        "floor_label_provenance": kw.get("label_provenance", "n/a"),
        "floor_level_ids": _proposed_floor_ids(
            kw.get("building_id"), kw.get("linked_parcel_id"),
            est if (isinstance(est, int) and est >= 1
                    and kw["status"] != "NOT_DETERMINABLE"
                    and not kw.get("no_ids")) else 0,
        ),
        # ---- compatibility aliases for older readers ----
        "floor_evidence_status": {"OBSERVED": "REFERENCE", "PREDICTED": "PREDICTED",
                                  "NOT_DETERMINABLE": "NOT_DETERMINABLE"}[kw["status"]],
        "floor_count_min": kw.get("floor_min"),
        "floor_count_max": kw.get("floor_max"),
        "floor_count_confidence": kw["state"],
        "floor_prediction_score": None if conf is None else round(conf * 100),
        "floor_prediction_method": kw["method"],
        "floor_prediction_reason": kw["reason"],
        "floor_review_recommendation": ("HUMAN_VERIFICATION_REQUIRED"
                                        if kw.get("hv", kw["status"] != "OBSERVED")
                                        else "NONE"),
        "floor_evidence": kw["source"],
        "floor_height_assumption_m": None,
    }
    return out


def _not_determinable(building_id, linked_parcel_id, height_m, veg, why):
    veg = str(veg or "").upper()
    try:
        h = float(height_m)
        h_txt = f"{h:.1f} m" if math.isfinite(h) and h > 0 else "unavailable"
    except (TypeError, ValueError):
        h_txt = "unavailable"
    return _base(
        status="NOT_DETERMINABLE", state="NOT_DETERMINABLE", source="NONE",
        method="NONE",
        floor_count_estimated=None, floor_min=None, floor_max=None, floor_confidence=None,
        reason=(f"{why} Height evidence ({h_txt}) exists but is not a floor detection."),
        missing=[
            "A real floor label (municipal record / verified survey / OSM building:levels), or",
            "sub-metre imagery that resolves floors, or",
            "a model prediction that clears the calibrated confidence threshold",
        ],
        vertical_context="VEGETATION_CONTAMINATED_HEIGHT" if veg in _VEG_CONTAMINATED else "OK",
        hv=True, building_id=building_id, linked_parcel_id=linked_parcel_id,
    )


def batch_model_scores(model_bundle, feature_rows):
    """Vectorised model scoring for many buildings at once.

    ``feature_rows`` is a list of (key, feature_dict_or_None). Returns
    {key: {"point","spread","confidence","ood"}} for the rows that had features.
    """
    import numpy as np

    cols = model_bundle["feature_columns"]
    keys, mat = [], []
    for k, feat in feature_rows:
        if feat is None:
            continue
        keys.append(k)
        mat.append([float(feat[c]) for c in cols])
    if not mat:
        return {}
    x = np.asarray(mat, dtype=float)
    rf = model_bundle["rf"]
    tree_preds = np.stack([e.predict(x) for e in rf.estimators_], axis=0)  # (n_trees, n)
    point = model_bundle["model"].predict(x)
    spread = tree_preds.std(axis=0)
    ood_score = model_bundle["ood_model"].score_samples(x)
    ood = ood_score < model_bundle["ood_threshold"]
    cen = np.asarray(model_bundle["calibration"]["std_centres"], float)
    cov = np.asarray(model_bundle["calibration"]["within1_coverage"], float)
    conf = np.clip(np.interp(spread, cen, cov, left=cov[0], right=cov[-1]), 0.03, 0.97)
    return {
        k: {"point": float(point[i]), "spread": float(spread[i]),
            "confidence": float(conf[i]), "ood": bool(ood[i])}
        for i, k in enumerate(keys)
    }


def classify(
    *,
    building_id=None,
    linked_parcel_id=None,
    features=None,               # dict keyed by model_bundle["feature_columns"], or None
    real_osm_levels=None,
    real_osm_levels_verified=False,
    building_height_m=None,
    vegetation_pattern=None,
    model_bundle=None,
    model_score=None,            # pre-computed {"point","spread","confidence","ood"} (batch path)
):
    """Return the floor-detection dict for one building."""
    veg = str(vegetation_pattern or "").upper()
    veg_contam = veg in _VEG_CONTAMINATED

    # ---------------------------------------------------------------- OBSERVED
    levels = _as_int_levels(real_osm_levels) if real_osm_levels_verified else None
    if levels is not None:
        implied = None
        consistency = "UNKNOWN"
        try:
            h = float(building_height_m)
            if math.isfinite(h) and h > 2.5:
                implied = max(1, round(h / FLOOR_HEIGHT_TYP_M))
                consistency = "DIVERGENT" if abs(implied - levels) >= 3 else "CONSISTENT"
        except (TypeError, ValueError):
            pass
        ood = levels >= OOD_FLOOR_COUNT
        hv = ood or consistency == "DIVERGENT" or veg_contam
        supporting = ["Real OSM building:levels tag = " + str(levels),
                      "Building footprint linked to a cadastral parcel"]
        if consistency == "CONSISTENT":
            supporting.append(f"Derived height {building_height_m} m is consistent (~{implied} floors)")
        reason = ("Floor count is a real OpenStreetMap building:levels tag "
                  "(Tier-2, crowd-sourced - not an authoritative government record).")
        if veg_contam:
            reason += (" NDVI is vegetation-dominant here so the height context is uncertain; "
                       "the tag-based count still stands.")
        return _base(
            status="OBSERVED", state="HIGH" if not hv else "MEDIUM", source="REAL_OSM_BUILDING_LEVELS",
            method="OSM_BUILDING_LEVELS", floor_count_estimated=levels, floor_min=levels,
            floor_max=levels, floor_confidence=None,
            reason=reason, supporting=supporting,
            height_consistency=consistency,
            vertical_context="VEGETATION_CONTAMINATED_HEIGHT" if veg_contam else "OK",
            ood=ood, hv=hv,
            label_source="OSM_building:levels", label_type="STRUCTURED_TAG_TIER2",
            label_provenance="OpenStreetMap way tag building:levels (ODbL)",
            building_id=building_id, linked_parcel_id=linked_parcel_id,
        )

    # ---------------------------------------------------------------- model
    if model_score is not None:
        point = model_score["point"]
        spread = model_score["spread"]
        conf = model_score["confidence"]
        ood = model_score["ood"]
    elif model_bundle and features is not None:
        try:
            s = batch_model_scores(model_bundle, [("_", features)])["_"]
            point, spread, conf, ood = s["point"], s["spread"], s["confidence"], s["ood"]
        except Exception as exc:  # noqa: BLE001
            return _not_determinable(building_id, linked_parcel_id, building_height_m, veg,
                                     f"Floor model could not score this footprint ({exc}).")
    else:
        return _not_determinable(building_id, linked_parcel_id, building_height_m, veg,
                                 "No real floor label and the floor model is unavailable / "
                                 "no usable footprint geometry.")

    n = max(1, round(point))
    lo = max(1, math.floor(point - max(1.0, spread)))
    hi = max(n, math.ceil(point + max(1.0, spread)))
    rng = hi - lo

    a_high = model_bundle.get("accept_high", 0.70)
    a_med = model_bundle.get("accept_medium", 0.58)
    a_low = model_bundle.get("accept_low", 0.45)
    r_high = model_bundle.get("accept_range_high", 2)
    r_med = model_bundle.get("accept_range_medium", 3)
    r_low = model_bundle.get("accept_range_low", 4)

    if ood or n >= OOD_FLOOR_COUNT:
        return _not_determinable(
            building_id, linked_parcel_id, building_height_m, veg,
            "The footprint is outside the model's training distribution, so no floor "
            "count is asserted.")
    if veg_contam:
        return _not_determinable(
            building_id, linked_parcel_id, building_height_m, veg,
            "NDVI is vegetation-dominant over this footprint; the vertical evidence may be "
            "canopy, so the model prediction is withheld.")

    # Tiered acceptance on the CALIBRATED confidence + prediction range. All tiers
    # are labelled ESTIMATED and carry confidence + an expected range; LOW is
    # shown for review but generates NO floor-level IDs.
    if conf >= a_high and rng <= r_high:
        state = "HIGH"
    elif conf >= a_med and rng <= r_med:
        state = "MEDIUM"
    elif conf >= a_low and rng <= r_low:
        state = "LOW"
    else:
        why = (f"calibrated confidence {conf:.0%} within +/-1 floor (< {a_low:.0%})"
               if conf < a_low
               else f"predicted range {lo}-{hi} floors is too wide")
        return _not_determinable(
            building_id, linked_parcel_id, building_height_m, veg,
            f"The floor model abstains: {why}.")

    btype = ("residential" if features.get("type_residential")
             else "commercial" if features.get("type_commercial")
             else "civic" if features.get("type_civic")
             else "industrial" if features.get("type_industrial") else "other")
    supporting = [
        (f"Model ({model_bundle['chosen_model_name']}) trained on "
         f"{model_bundle['train_size']} real OSM building:levels labels (spatial split)"),
        "Footprint area / perimeter / shape descriptors",
        ("Real OSM height tag used as a feature" if features.get("has_height_tag")
         else "Coarse Copernicus GLO-30 DSM height feature" if features.get("has_dsm_height")
         else "Footprint shape only (no height feature)"),
        f"Building type: {btype}",
        f"Ensemble agreement -> calibrated P(within +/-1 floor) = {conf:.0%}",
    ]
    reason = (f"Model-estimated floor count: {n} floors (expected range {lo}-{hi}), "
              f"calibrated confidence {conf:.0%} within +/-1 floor. This is a model "
              "ESTIMATE, not an observed fact; human verification is recommended.")
    if state == "LOW":
        reason += " Confidence is LOW - shown for review only, no floor-level IDs generated."
    return _base(
        status="PREDICTED", state=state, source="ML_MODEL",
        method="ML_FOOTPRINT_TAG_DSM_MODEL",
        floor_count_estimated=n, floor_min=lo, floor_max=hi, floor_confidence=conf,
        reason=reason, supporting=supporting,
        vertical_context="OK", ood=False, hv=True,
        no_ids=(state == "LOW"),
        building_id=building_id, linked_parcel_id=linked_parcel_id,
    )


def method_manifest(model_bundle=None):
    m = {
        "model_version": FLOOR_MODEL_VERSION,
        "cnn_used": False,
        "cnn_not_used_reason": ("no sub-metre / floor-resolving imagery for these buildings; "
                                "a CNN cannot see floors in Sentinel-2 (10 m)"),
        "label_source": "OpenStreetMap building:levels (ODbL) - crowd-sourced Tier-2",
        "sources": {
            "OBSERVED": "real OSM building:levels tag on the building",
            "PREDICTED": ("supervised HistGradientBoosting / RandomForest on ~12.7k real OSM "
                          "labels across greater Bengaluru, whole-cell spatial split, "
                          "labelled ESTIMATED with calibrated confidence + range"),
            "NOT_DETERMINABLE": "no real tag and the model abstains / OOD / vegetation-contaminated",
        },
        "features": "footprint area, perimeter, compactness, rectangularity, elongation, "
                    "long/short side, vertex count, building type, name presence, OSM height "
                    "tag, coarse Copernicus GLO-30 DSM height",
        "confidence": ("floor_confidence = calibrated empirical P(prediction within +/-1 floor), "
                       "isotonic regression on a held-out validation set. Not a legal certainty."),
        "acceptance": ("tiered on calibrated confidence + predicted range, in-distribution only: "
                       "HIGH (>=accept_high, range<=+/-2) and MEDIUM (>=accept_medium, range<=+/-3) "
                       "get floor-level IDs; LOW (>=accept_low, range<=+/-4) is shown for review "
                       "with NO IDs; everything else NOT_DETERMINABLE."),
        "no_synthetic_data": "every label is a real OSM tag; no synthetic buildings / labels / "
                             "imagery / confidence values.",
    }
    if model_bundle:
        m["train_size"] = model_bundle.get("train_size")
        m["val_size"] = model_bundle.get("val_size")
        m["test_size"] = model_bundle.get("test_size")
        m["chosen_model"] = model_bundle.get("chosen_model_name")
        m["accept_high"] = model_bundle.get("accept_high")
        m["accept_medium"] = model_bundle.get("accept_medium")
        m["accept_low"] = model_bundle.get("accept_low")
        m["accept_range_high"] = model_bundle.get("accept_range_high")
        m["accept_range_medium"] = model_bundle.get("accept_range_medium")
        m["accept_range_low"] = model_bundle.get("accept_range_low")
        m["test_metrics"] = (model_bundle.get("metrics", {})
                             .get(model_bundle.get("chosen_model_name"), {}).get("test"))
        m["aoi_independent_eval"] = model_bundle.get("aoi_independent_eval")
    return m
