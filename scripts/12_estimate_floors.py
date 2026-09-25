"""
Phase 12 (ADDITIVE) - Floor Detection: OBSERVED / PREDICTED / NOT_DETERMINABLE.

Runs AFTER Phase 11 (NDVI). For each AOI building:
  * if it carries a real OSM building:levels tag  -> OBSERVED (use the tag)
  * else, score its footprint with the trained model (data/processed/floor_model.joblib
    from scripts/train_floor_model.py) -> PREDICTED when the calibrated confidence
    clears the threshold and the footprint is in-distribution
  * else -> NOT_DETERMINABLE (no floor count, no floor-level IDs)

Reads geometry / tags only. building_height_m, derived_floors, building_levels,
ground_elevation_m, NDVI fields, match_status_2d, final_verification_status are
never written.  No synthetic data.
"""

import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import floor_estimation as fe
from floor_features import FEATURE_COLUMNS, features_from_geojson_polygon

IN_PRIMARY = os.path.join("data", "processed", "buildings_ndvi_evidence.geojson")
IN_FALLBACK = os.path.join("frontend", "data", "buildings_3d.geojson")
OUT_PATH = os.path.join("data", "processed", "buildings_floor_estimated.geojson")
FRONTEND_PATH = os.path.join("frontend", "data", "buildings_3d.geojson")
LEDGER_PATH = os.path.join("data", "processed", "evidence_fusion_ledger.json")
REPORT_PATH = os.path.join("docs", "FLOOR_ESTIMATION_REPORT.md")
MODEL_PATH = os.path.join("data", "processed", "floor_model.joblib")

_ADDITIVE_KEYS = {
    "floor_detection_status", "floor_count_estimated", "floor_min", "floor_max",
    "floor_confidence", "floor_confidence_pct", "floor_confidence_state", "floor_source",
    "floor_detection_method", "floor_model_version", "floor_detection_reason",
    "floor_supporting_evidence", "floor_missing_evidence", "floor_height_consistency",
    "floor_vertical_context", "floor_ood_flag", "requires_human_verification",
    "floor_label_source", "floor_label_type", "floor_label_provenance", "floor_level_ids",
    # aliases
    "floor_evidence_status", "floor_count_min", "floor_count_max", "floor_count_confidence",
    "floor_prediction_score", "floor_prediction_method", "floor_prediction_reason",
    "floor_review_recommendation", "floor_evidence", "floor_height_assumption_m",
}

_PROTECTED = [
    "id", "source", "building_type", "name", "building_levels", "building_levels_status",
    "height_m", "crs", "linked_parcel_id", "parcel_overlap_ratio", "match_status_2d",
    "ground_elevation_m", "building_height_m", "building_height_status", "derived_floors",
    "height_source", "height_confidence", "ai_anomaly_flag", "ai_anomaly_score",
    "ai_status", "final_verification_status",
    "vegetation_evidence", "vegetation_pattern", "vertical_evidence_status",
    "building_height_confidence", "ndvi_median", "ndvi_review_recommendation",
]


def _load(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return None


def merge_floor_fields(props, floor):
    for k, v in floor.items():
        if k in _ADDITIVE_KEYS:
            props[k] = v
    return props


def _load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        import joblib
        return joblib.load(MODEL_PATH)
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] could not load floor model ({exc}); PREDICTED disabled.")
        return None


def coverage(features):
    st = Counter(f["properties"].get("floor_detection_status") for f in features)
    cs = Counter(f["properties"].get("floor_confidence_state") for f in features)
    src = Counter(f["properties"].get("floor_source") for f in features)
    review = sum(1 for f in features if f["properties"].get("requires_human_verification"))
    ood = sum(1 for f in features if f["properties"].get("floor_ood_flag"))
    fc = Counter(f["properties"].get("floor_count_estimated") for f in features
                 if isinstance(f["properties"].get("floor_count_estimated"), int))
    ids = sum(len(f["properties"].get("floor_level_ids") or []) for f in features)
    confs = [f["properties"]["floor_confidence"] for f in features
             if isinstance(f["properties"].get("floor_confidence"), float)]
    return {
        "status": dict(st), "confidence_state": dict(cs), "source": dict(src),
        "human_verification": review, "ood": ood, "proposed_floor_ids": ids,
        "floor_count_distribution": dict(sorted(fc.items())),
        "predicted_conf_mean": round(sum(confs) / len(confs), 3) if confs else None,
        "predicted_n": len(confs),
    }


def _update_ledger(features, mm):
    ledger = _load(LEDGER_PATH) or {}
    for f in features:
        p = f["properties"]
        b_id = str(p.get("id", "UNKNOWN"))
        entry = ledger.setdefault(b_id, {"building_id": b_id, "evidence_lineage": {}})
        lineage = entry.setdefault("evidence_lineage", {})
        lineage["floor_estimation"] = {
            "floor_detection_status": p.get("floor_detection_status"),
            "floor_count_estimated": p.get("floor_count_estimated"),
            "floor_min": p.get("floor_min"), "floor_max": p.get("floor_max"),
            "floor_confidence": p.get("floor_confidence"),
            "floor_confidence_state": p.get("floor_confidence_state"),
            "floor_source": p.get("floor_source"),
            "method": p.get("floor_detection_method"),
            "model_version": p.get("floor_model_version"),
            "reason": p.get("floor_detection_reason"),
            "supporting_evidence": p.get("floor_supporting_evidence"),
            "height_consistency": p.get("floor_height_consistency"),
            "vertical_context": p.get("floor_vertical_context"),
            "ood_flag": p.get("floor_ood_flag"),
            "requires_human_verification": p.get("requires_human_verification"),
            "proposed_floor_level_ids": [fl["proposed_floor_spatial_id"]
                                        for fl in (p.get("floor_level_ids") or [])],
            "model": {
                "chosen": mm.get("chosen_model"), "train_size": mm.get("train_size"),
                "val_size": mm.get("val_size"), "test_size": mm.get("test_size"),
                "test_metrics": mm.get("test_metrics"),
                "label_source": mm.get("label_source"),
            },
            "provenance": "DERIVED_FLOOR_DETECTION_OSM_LABEL_PLUS_ML",
            "note": ("Additive. OBSERVED = real OSM building:levels tag; PREDICTED = supervised "
                     "model on real OSM labels (calibrated confidence); everything else "
                     "NOT_DETERMINABLE. building_height_m / derived_floors / building_levels "
                     "preserved unchanged. Proposed floor-level IDs are "
                     "PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE - not official ULPINs. No synthetic data."),
        }
    with open(LEDGER_PATH, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)


def _write_report(features, mm, model_ok):
    total = len(features)
    cov = coverage(features)
    L = []
    a = L.append
    a("# Phase 12: Floor Detection Report\n")
    a(f"_Generated by `scripts/12_estimate_floors.py` at {datetime.now(timezone.utc).isoformat()}._\n")

    a("\n## Sources\n")
    a("| status | meaning |\n|---|---|\n")
    for k, v in mm["sources"].items():
        a(f"| `{k}` | {v} |\n")
    a(f"\n- CNN not used: {mm['cnn_not_used_reason']}.\n")
    a(f"- Label source: **{mm['label_source']}**.\n")
    a(f"- Features: {mm['features']}.\n")
    a(f"- Confidence: {mm['confidence']}\n")
    a(f"- Acceptance: {mm['acceptance']}\n")

    if model_ok:
        a("\n## Model (see `docs/FLOOR_MODEL_REPORT.md` for the full comparison)\n")
        a(f"- chosen: **{mm.get('chosen_model')}**; "
          f"train **{mm.get('train_size')}** / val **{mm.get('val_size')}** / "
          f"test **{mm.get('test_size')}** (spatial split, greater Bengaluru, AOI excluded).\n")
        tm = mm.get("test_metrics") or {}
        if tm:
            a(f"- held-out **test**: MAE **{tm['mae']:.2f}** | RMSE {tm['rmse']:.2f} | "
              f"exact {tm['exact_acc']:.0%} | within +/-1 **{tm['within_1_acc']:.0%}** | "
              f"within +/-2 {tm['within_2_acc']:.0%}.\n")
        ae = mm.get("aoi_independent_eval")
        if ae:
            m = ae["metrics"]
            a(f"- independent AOI check (n={ae['n']}, never trained): MAE {m['mae']:.2f}, "
              f"within +/-1 {m['within_1_acc']:.0%}.\n")
        a(f"- tiered acceptance on calibrated P(within +/-1): HIGH >= "
          f"{mm.get('accept_high'):.0%} & range <= +/-{mm.get('accept_range_high')}; "
          f"MEDIUM >= {mm.get('accept_medium'):.0%} & range <= "
          f"+/-{mm.get('accept_range_medium')}; LOW >= {mm.get('accept_low'):.0%} & "
          f"range <= +/-{mm.get('accept_range_low')} (shown for review, NO floor-level "
          "IDs); otherwise NOT_DETERMINABLE. Every ML tier is labelled ESTIMATED and "
          "carries confidence + an expected range. HIGH from footprint shape alone is "
          "rare - a real OSM tag is what usually reads HIGH.\n")
    else:
        a("\n## Model: NOT AVAILABLE\n")
        a("> `data/processed/floor_model.joblib` is missing. Run "
          "`scripts/ingestion/load_osm_floor_labels.py` then `scripts/train_floor_model.py`. "
          "Without it every unlabelled building is NOT_DETERMINABLE.\n")

    a("\n## Results (all 2734 buildings)\n")
    a(f"- detection status: `{cov['status']}`\n")
    a(f"- source: `{cov['source']}`\n")
    a(f"- confidence state: `{cov['confidence_state']}`\n")
    a(f"- PREDICTED buildings: **{cov['predicted_n']}**, mean calibrated confidence "
      f"**{cov['predicted_conf_mean']}**\n")
    a(f"- human verification required: **{cov['human_verification']} / {total}**\n")
    a(f"- out-of-distribution rejected: **{cov['ood']}**\n")
    a(f"- proposed floor-level IDs generated: **{cov['proposed_floor_ids']}**\n")

    a("\n### Floor-count distribution (OBSERVED + PREDICTED)\n")
    a("| floors | buildings |\n|---:|---:|\n")
    for k, v in cov["floor_count_distribution"].items():
        a(f"| {k} | {v} |\n")
    nd = cov["status"].get("NOT_DETERMINABLE", 0)
    a(f"| _not determinable_ | {nd} |\n")

    a("\n## Non-regression\n")
    a("`building_height_m`, `derived_floors`, `building_levels`, `ground_elevation_m`, "
      "NDVI fields, `match_status_2d`, `final_verification_status` are read-only here.\n")
    a("\n## Data integrity\n")
    a("- **No synthetic training, validation, prediction or demonstration data.** "
      "Every label is a real OSM `building:levels` tag; every feature comes from real "
      "footprint geometry or real OSM tags; confidence is a calibrated empirical "
      "probability. Proposed IDs are `PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE`, never "
      "an official ULPIN.\n")

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("".join(L))


def _non_regression(before_props, features):
    changed = Counter()
    for f in features:
        p = f["properties"]
        b = before_props.get(str(p.get("id")))
        if not b:
            continue
        for k in _PROTECTED:
            if b.get(k) != p.get(k):
                changed[k] += 1
    return changed


def main():
    print("=========================================")
    print("  PHASE 12: FLOOR DETECTION (OSM + ML)    ")
    print("=========================================\n")

    in_path = IN_PRIMARY if os.path.exists(IN_PRIMARY) else IN_FALLBACK
    data = _load(in_path)
    if not data or "features" not in data:
        print(f"Error: no buildings found ({IN_PRIMARY} / {IN_FALLBACK}). Run phases 1-11 first.")
        return
    features = data["features"]
    total = len(features)
    print(f"Loaded {total} buildings from {in_path}.")
    before_props = {str(f["properties"].get("id")): dict(f["properties"]) for f in features}

    model_bundle = _load_model()
    model_ok = model_bundle is not None
    print(f"Floor model: {'loaded (' + str(model_bundle.get('chosen_model_name')) + ')' if model_ok else 'NOT AVAILABLE -> unlabelled buildings will be NOT_DETERMINABLE'}")
    mm = fe.method_manifest(model_bundle)

    # 1) features for every building (real footprint geometry + OSM tags + GLO-30 DSM height)
    dsm_src = None
    glo30 = os.path.join("data", "raw", "glo30_dsm.tif")
    if os.path.exists(glo30):
        try:
            import rasterio
            dsm_src = rasterio.open(glo30)
            print(f"  DSM height feature: {glo30}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] could not open GLO-30 DSM ({exc}); scoring without dsm_height_m")
    feats = {}
    for f in features:
        p = f["properties"]
        feat = features_from_geojson_polygon(f.get("geometry"), p, dsm_src=dsm_src)
        if feat is not None:
            feats[str(p.get("id"))] = {c: feat[c] for c in FEATURE_COLUMNS}
    if dsm_src is not None:
        dsm_src.close()
    n_feat_ok = len(feats)

    # 2) one vectorised model pass over all scorable footprints
    scores = {}
    if model_ok and feats:
        scores = fe.batch_model_scores(model_bundle, list(feats.items()))

    # 3) per-building classification (OBSERVED tag wins; else the model score)
    for f in features:
        p = f["properties"]
        bid = str(p.get("id"))
        floor = fe.classify(
            building_id=p.get("id"),
            linked_parcel_id=p.get("linked_parcel_id"),
            features=feats.get(bid),
            model_score=scores.get(bid),
            real_osm_levels=p.get("building_levels"),
            real_osm_levels_verified=str(p.get("building_levels_status", "")).upper() == "VERIFIED",
            building_height_m=p.get("building_height_m"),
            vegetation_pattern=p.get("vegetation_pattern"),
            model_bundle=model_bundle,
        )
        merge_floor_fields(p, floor)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    shutil.copy(OUT_PATH, FRONTEND_PATH)
    _update_ledger(features, mm)
    _write_report(features, mm, model_ok)

    changed = _non_regression(before_props, features)
    cov = coverage(features)
    print("\nFloor detection complete.")
    print(f"  footprints scorable by the model: {n_feat_ok}/{total}")
    print(f"  detection status : {cov['status']}")
    print(f"  source           : {cov['source']}")
    print(f"  confidence state : {cov['confidence_state']}")
    print(f"  PREDICTED        : {cov['predicted_n']} (mean conf {cov['predicted_conf_mean']})")
    print(f"  floor-count dist : {cov['floor_count_distribution']}")
    print(f"  proposed IDs     : {cov['proposed_floor_ids']}")
    print(f"  human verification: {cov['human_verification']} / {total}")
    print(f"  NON-REGRESSION   : {'PASS - no protected field changed' if not changed else 'FAIL ' + str(dict(changed))}")
    print(f"  Report   : {REPORT_PATH}   (+ docs/FLOOR_MODEL_REPORT.md)")


if __name__ == "__main__":
    main()
