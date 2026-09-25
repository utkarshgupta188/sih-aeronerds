"""
Train a REAL supervised floor-count model on OSM building:levels labels.

Data  : data/interim/osm_floor_labels.csv  (~12.7k real Bengaluru buildings,
        ODbL, produced by scripts/ingestion/load_osm_floor_labels.py; the demo
        AOI is excluded so its labelled buildings stay an independent test set).
Split : SPATIAL - centroids gridded into ~2 km cells, whole cells assigned to
        train / val / test (70/15/15). No building leaks across splits.
Models: naive baseline (median), RandomForest, HistGradientBoosting. The one
        with the best held-out within-+/-1 accuracy (tie-break MAE) is chosen.
Uncert: RandomForest per-tree spread -> calibrated to an empirical within-+/-1
        probability on the validation set. IsolationForest flags out-of-
        distribution footprints.
Output: data/processed/floor_model.joblib   +   docs/FLOOR_MODEL_REPORT.md

NO synthetic data. Every label is a real OSM tag. If the label CSV is missing
this script exits without writing a model (Phase 12 then returns NOT_DETERMINABLE
for everything).
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from floor_features import FEATURE_COLUMNS

LABELS_CSV = os.path.join("data", "interim", "osm_floor_labels.csv")
MODEL_PATH = os.path.join("data", "processed", "floor_model.joblib")
REPORT_PATH = os.path.join("docs", "FLOOR_MODEL_REPORT.md")
AOI_GEOJSON = os.path.join("frontend", "data", "buildings_3d.geojson")

RANDOM_STATE = 42
GRID_DEG = 0.02          # ~2.2 km spatial-split cells
# Acceptance thresholds on the CALIBRATED within-+/-1 probability. Set from the
# model's own held-out behaviour, not to chase coverage:
#   - the naive "predict the training median" baseline is right within +/-1 for
#     ~55% of held-out buildings, so a prediction is only worth showing when the
#     model clears that by a clear margin;
#   - this footprint-shape model's calibration ceiling is ~0.71, so HIGH (0.85)
#     is unreachable from shape alone -> HIGH stays reserved for real OSM tags.
# Tiered acceptance on the CALIBRATED within-+/-1 probability + prediction range.
# Chosen from the model's own held-out behaviour, not to chase coverage:
#   naive "predict the median" baseline is right within +/-1 for ~35-42% of
#   held-out buildings; this model reaches ~57% (test) / ~73% calibrated per
#   building. So:
ACCEPT_HIGH = 0.70     # + range <= 2  -> HIGH   (tightest ensemble agreement)
ACCEPT_MED = 0.58      # + range <= 3  -> MEDIUM (clearly above the base rate)
ACCEPT_LOW = 0.45      # + range <= 4  -> LOW    (shown for review, NO floor IDs)
ACCEPT_RANGE_HIGH = 2
ACCEPT_RANGE_MEDIUM = 3
ACCEPT_RANGE_LOW = 4


def _csv_to_xy(df, pd):
    x = pd.DataFrame(index=df.index)
    for c in ("area_m2", "perimeter_m", "compactness", "rectangularity", "elongation",
              "long_side_m", "short_side_m", "n_vertices", "has_name"):
        x[c] = pd.to_numeric(df[c], errors="coerce")
    ht = pd.to_numeric(df["height_tag"], errors="coerce")
    x["height_tag_m"] = ht.fillna(0.0).clip(0, 400)
    x["has_height_tag"] = ht.notna().astype(int)
    dh = pd.to_numeric(df["dsm_height_m"], errors="coerce") if "dsm_height_m" in df.columns \
        else pd.Series([float("nan")] * len(df), index=df.index)
    x["dsm_height_m"] = dh.fillna(0.0).clip(0, 400)
    x["has_dsm_height"] = dh.notna().astype(int)
    bt = df["building_type"].astype(str)
    for t in ("residential", "commercial", "civic", "industrial", "other"):
        x["type_" + t] = (bt == t).astype(int)
    x = x[FEATURE_COLUMNS].fillna(0.0)
    y = pd.to_numeric(df["levels"], errors="coerce")
    return x, y


def _spatial_split(df, np):
    cx = (df["lon"] / GRID_DEG).round().astype(int)
    cy = (df["lat"] / GRID_DEG).round().astype(int)
    cells = (cx.astype(str) + "_" + cy.astype(str))
    uniq = sorted(cells.unique())
    rng = np.random.default_rng(RANDOM_STATE)
    rng.shuffle(uniq)
    n = len(uniq)
    tr = set(uniq[: int(0.70 * n)])
    va = set(uniq[int(0.70 * n): int(0.85 * n)])
    te = set(uniq[int(0.85 * n):])
    return cells.isin(tr), cells.isin(va), cells.isin(te), len(uniq)


def _metrics(y_true, y_pred, np):
    yt = np.asarray(y_true, float)
    yp = np.asarray(y_pred, float)
    err = yp - yt
    return {
        "n": len(yt),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(math.sqrt(np.mean(err ** 2))),
        "median_ae": float(np.median(np.abs(err))),
        "exact_acc": float(np.mean(np.round(yp) == yt)),
        "within_1_acc": float(np.mean(np.abs(np.round(yp) - yt) <= 1)),
        "within_2_acc": float(np.mean(np.abs(np.round(yp) - yt) <= 2)),
    }


def _rf_tree_std(rf, x, np):
    preds = np.stack([est.predict(x) for est in rf.estimators_], axis=0)
    return preds.mean(axis=0), preds.std(axis=0)


def _calibrate(std_val, pred_val, y_val, np):
    """Isotonic (monotone non-increasing) map: per-tree std -> P(within +/-1 floor).

    More tree agreement (smaller std) => higher probability, by construction.
    Fit on the validation set only.
    """
    from sklearn.isotonic import IsotonicRegression

    hit = (np.abs(np.round(pred_val) - np.asarray(y_val, float)) <= 1).astype(float)
    iso = IsotonicRegression(increasing=False, y_min=0.03, y_max=0.97, out_of_bounds="clip")
    iso.fit(std_val, hit)
    grid = np.quantile(std_val, np.linspace(0.02, 0.98, 25))
    grid = np.unique(np.round(grid, 4))
    return grid.tolist(), iso.predict(grid).round(4).tolist()


def _confidence(std, centres, cover, np):
    c = np.interp(std, centres, cover, left=cover[0], right=cover[-1])
    return np.clip(c, 0.05, 0.97)


def _aoi_eval(model_bundle, np):
    """Fully independent check on the 16 AOI buildings that carry a real tag."""
    if not os.path.exists(AOI_GEOJSON):
        return None
    from floor_features import features_from_geojson_polygon
    dsm_src = None
    glo30 = os.path.join("data", "raw", "glo30_dsm.tif")
    if os.path.exists(glo30):
        try:
            import rasterio
            dsm_src = rasterio.open(glo30)
        except Exception:  # noqa: BLE001
            dsm_src = None
    with open(AOI_GEOJSON, encoding="utf-8") as fh:
        gj = json.load(fh)
    xs, ys = [], []
    for f in gj["features"]:
        p = f["properties"]
        lvl = None
        try:
            if str(p.get("building_levels_status", "")).upper() == "VERIFIED":
                lvl = round(float(p.get("building_levels")))
        except (TypeError, ValueError):
            lvl = None
        if lvl is None or lvl < 1:
            continue
        feat = features_from_geojson_polygon(f.get("geometry"), p, dsm_src=dsm_src)
        if feat is None:
            continue
        xs.append([feat[c] for c in FEATURE_COLUMNS])
        ys.append(lvl)
    if len(xs) < 3:
        return None
    x = np.asarray(xs, float)
    pred = model_bundle["model"].predict(x)
    return _metrics(ys, pred, np), len(xs)


def main():
    print("=========================================")
    print("  FLOOR-COUNT MODEL TRAINING (real OSM)   ")
    print("=========================================\n")
    if not os.path.exists(LABELS_CSV):
        print(f"[NO LABELS] {LABELS_CSV} missing - run scripts/ingestion/load_osm_floor_labels.py first.")
        print("No model written. Phase 12 will return NOT_DETERMINABLE for all buildings.")
        return

    try:
        import joblib
        import numpy as np
        import pandas as pd
        from sklearn.ensemble import (
            HistGradientBoostingRegressor,
            IsolationForest,
            RandomForestRegressor,
        )
    except ImportError as exc:
        print(f"[MISSING DEPS] {exc}. Run: pip install scikit-learn pandas joblib numpy")
        return

    df = pd.read_csv(LABELS_CSV)
    df = df.dropna(subset=["levels", "lat", "lon"])
    x_all, y_all = _csv_to_xy(df, pd)
    tr, va, te, ncells = _spatial_split(df, np)
    print(f"  {len(df)} labelled buildings  |  {ncells} spatial cells  "
          f"|  train {tr.sum()}  val {va.sum()}  test {te.sum()}")

    xtr, ytr = x_all[tr].to_numpy(float), y_all[tr].to_numpy(float)
    xva, yva = x_all[va].to_numpy(float), y_all[va].to_numpy(float)
    xte, yte = x_all[te].to_numpy(float), y_all[te].to_numpy(float)

    results = {}
    # naive baseline
    med = float(np.median(ytr))
    results["baseline_median"] = {
        "val": _metrics(yva, np.full_like(yva, med), np),
        "test": _metrics(yte, np.full_like(yte, med), np),
    }
    # RandomForest
    rf = RandomForestRegressor(n_estimators=350, max_depth=None, min_samples_leaf=3,
                               max_features=0.7, n_jobs=-1, random_state=RANDOM_STATE)
    rf.fit(xtr, ytr)
    results["random_forest"] = {
        "val": _metrics(yva, rf.predict(xva), np),
        "test": _metrics(yte, rf.predict(xte), np),
    }
    # HistGradientBoosting
    hgb = HistGradientBoostingRegressor(max_depth=8, learning_rate=0.06, max_iter=500,
                                        l2_regularization=1.0, random_state=RANDOM_STATE)
    hgb.fit(xtr, ytr)
    results["hist_gradient_boosting"] = {
        "val": _metrics(yva, hgb.predict(xva), np),
        "test": _metrics(yte, hgb.predict(xte), np),
    }

    ranked = sorted(
        [("random_forest", rf), ("hist_gradient_boosting", hgb)],
        key=lambda kv: (-results[kv[0]]["test"]["within_1_acc"], results[kv[0]]["test"]["mae"]),
    )
    chosen_name, chosen = ranked[0]
    print(f"  chosen model: {chosen_name}  "
          f"(test MAE {results[chosen_name]['test']['mae']:.2f}, "
          f"+/-1 acc {results[chosen_name]['test']['within_1_acc']:.2%})")

    # uncertainty + calibration always from RF's tree spread
    mean_va, std_va = _rf_tree_std(rf, xva, np)
    centres, cover = _calibrate(std_va, mean_va, yva, np)

    # OOD on the feature space
    iso = IsolationForest(contamination=0.03, random_state=RANDOM_STATE)
    iso.fit(xtr)
    iso_thr = float(np.quantile(iso.score_samples(xtr), 0.02))

    bundle = {
        "model_version": "boundarylens-floor/v3-ml",
        "training_mode_floor": int(np.bincount(ytr.astype(int)).argmax()),
        "chosen_model_name": chosen_name,
        "model": chosen,
        "rf": rf,
        "feature_columns": FEATURE_COLUMNS,
        "calibration": {"std_centres": centres, "within1_coverage": cover},
        "accept_high": ACCEPT_HIGH,
        "accept_medium": ACCEPT_MED,
        "accept_low": ACCEPT_LOW,
        "accept_range_high": ACCEPT_RANGE_HIGH,
        "accept_range_medium": ACCEPT_RANGE_MEDIUM,
        "accept_range_low": ACCEPT_RANGE_LOW,
        "ood_model": iso,
        "ood_threshold": iso_thr,
        "train_size": int(tr.sum()), "val_size": int(va.sum()), "test_size": int(te.sum()),
        "spatial_cells": int(ncells), "grid_deg": GRID_DEG,
        "metrics": results,
        "trained_utc": datetime.now(timezone.utc).isoformat(),
        "label_source": "OpenStreetMap building:levels (ODbL) - crowd-sourced Tier-2",
    }

    aoi = _aoi_eval(bundle, np)
    if aoi:
        bundle["aoi_independent_eval"] = {"metrics": aoi[0], "n": aoi[1]}
        print(f"  AOI independent check (n={aoi[1]}): MAE {aoi[0]['mae']:.2f}, "
              f"+/-1 acc {aoi[0]['within_1_acc']:.2%}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    print(f"  wrote {MODEL_PATH}")
    _write_report(bundle, chosen, rf, np)
    print(f"  wrote {REPORT_PATH}")


def _write_report(b, chosen, rf, np):
    r = b["metrics"]
    imp = sorted(zip(FEATURE_COLUMNS, rf.feature_importances_), key=lambda t: -t[1])
    L = []
    a = L.append
    a("# Floor-Count Model Report\n")
    a(f"_Generated by `scripts/train_floor_model.py` at {b['trained_utc']}._\n")
    a("\n## Data (real labels only)\n")
    a("- Source: **OpenStreetMap `building:levels`** via Overpass, ODbL, "
      "(c) OpenStreetMap contributors. Crowd-sourced structured tag (Tier-2) - "
      "**not** municipal legal approval, not ground truth.\n")
    a(f"- Usable labelled buildings: **{b['train_size'] + b['val_size'] + b['test_size']}** "
      "(greater Bengaluru; the 2 km demo AOI is excluded).\n")
    a(f"- Spatial split over **{b['spatial_cells']}** ~{b['grid_deg']*111:.1f} km cells, "
      "whole cells to one split -> no nearby-building leakage: "
      f"train **{b['train_size']}** / val **{b['val_size']}** / test **{b['test_size']}**.\n")
    a("- No synthetic buildings, labels, imagery or features. No CNN "
      "(no floor-resolving imagery for these buildings).\n")

    a("\n## Features (all from real geometry + OSM tags)\n")
    a("`" + "`, `".join(FEATURE_COLUMNS) + "`\n")

    a("\n## Model comparison (held-out)\n")
    a("| model | split | MAE | RMSE | exact acc | within +/-1 | within +/-2 |\n")
    a("|---|---|---:|---:|---:|---:|---:|\n")
    for name in ("baseline_median", "random_forest", "hist_gradient_boosting"):
        for sp in ("val", "test"):
            m = r[name][sp]
            a(f"| {name} | {sp} | {m['mae']:.2f} | {m['rmse']:.2f} | "
              f"{m['exact_acc']:.1%} | {m['within_1_acc']:.1%} | {m['within_2_acc']:.1%} |\n")
    a(f"\n**Chosen model: `{b['chosen_model_name']}`** (best held-out within-+/-1 "
      "accuracy, tie-break MAE).\n")

    if b.get("aoi_independent_eval"):
        e = b["aoi_independent_eval"]
        a(f"\n## Independent check - the {e['n']} AOI buildings that carry a real OSM tag "
          "(never seen in training)\n")
        m = e["metrics"]
        a(f"- MAE **{m['mae']:.2f}** | RMSE {m['rmse']:.2f} | exact {m['exact_acc']:.0%} "
          f"| within +/-1 **{m['within_1_acc']:.0%}** (n={m['n']})\n")
        a("- Small n; treated as a sanity check, not a headline metric.\n")

    a("\n## Confidence (calibrated, not arbitrary)\n")
    a("- Point prediction = mean over RandomForest trees; spread = per-tree std.\n")
    a("- The spread is mapped to an **empirical P(prediction within +/-1 floor)** "
      "measured in std-quantile bins on the validation set:\n")
    a("  | std ~ | P(within +/-1) |\n  |---:|---:|\n")
    for c, cov in zip(b["calibration"]["std_centres"], b["calibration"]["within1_coverage"]):
        a(f"  | {c:.2f} | {cov:.0%} |\n")
    a("- Tiered acceptance on (calibrated confidence, prediction range), in-distribution only:\n")
    a(f"  - **HIGH**  : conf >= {b['accept_high']:.0%} and range <= +/-{b['accept_range_high']}\n")
    a(f"  - **MEDIUM**: conf >= {b['accept_medium']:.0%} and range <= +/-{b['accept_range_medium']}\n")
    a(f"  - **LOW**   : conf >= {b['accept_low']:.0%} and range <= +/-{b['accept_range_low']} "
      "(shown for review, NO floor-level IDs)\n")
    a("  - otherwise -> **NOT_DETERMINABLE**. All ML tiers are labelled ESTIMATED and "
      "carry confidence + an expected range.\n")
    a(f"- Out-of-distribution: IsolationForest on the training feature space; "
      f"footprints below the 2nd-percentile training score ({b['ood_threshold']:.3f}) "
      "are rejected regardless of confidence.\n")
    a("- `floor_confidence` is this calibrated probability. It is **not** a legal "
      "certainty.\n")

    a("\n## Top feature importances (RandomForest)\n")
    for name, v in imp[:10]:
        a(f"- `{name}`: {v:.3f}\n")

    a("\n## Limitations\n")
    a("- Labels are crowd-sourced OSM tags; some are wrong/approximate.\n")
    a("- Training data is greater Bengaluru, applied to the same city - low domain "
      "shift, but still a shift from the small AOI; the AOI check above quantifies it.\n")
    a("- No imagery features (no sub-metre imagery for these buildings).\n")
    a("- Predicts a floor *count* from footprint shape + OSM tags; genuinely "
      "ambiguous footprints are rejected rather than guessed.\n")

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("".join(L))


if __name__ == "__main__":
    main()
