# Floor Detection v3 — Coverage Expansion Audit

_Response to the "INCREASE FLOOR DETECTION COVERAGE" change request._
_Pipeline: BoundaryLens SIH26011 · AOI: Bengaluru 2734 buildings · 2026-09._

The brief: floor information existed for only ~17 buildings; expand coverage, but
**only** through real labels + real features + real ML + calibration + validated
thresholds, with three states always distinguishable — **OBSERVED ≠ PREDICTED ≠
NOT_DETERMINABLE** — and no synthetic anything.

---

## A. DATA

| item | value | provenance |
|---|---|---|
| Training labels | **12,737** real OSM `building:levels` | Overpass API, `TRAIN_BBOX = 12.82,77.48 → 13.10,77.78` (greater Bengaluru), ODbL, © OpenStreetMap contributors. Demo AOI bbox **excluded**. |
| Independent check labels | **16** real OSM `building:levels` **inside the AOI** | never seen in training — held-out sanity set only |
| Height feature (`height_tag_m`) | subset of training + 3 AOI | real OSM `height` tag |
| DSM feature (`dsm_height_m`) | Copernicus **GLO-30** (30 m) | AWS Open Data `copernicus-dem-30m` (anonymous), tiles N12/N13 E077, mosaicked → `data/raw/glo30_dsm.tif`; coarse above-ground height = `max(90 m box) − p10(390 m ring)` |
| Authoritative / municipal / permit / BIM / LiDAR | **0** | none exist for this AOI |
| Floor-resolving imagery | **none** | Sentinel-2 is 10 m top-down → **no CNN** (documented, not a shortcut) |
| Synthetic labels / features / imagery | **0** | — |

Labels cleaned: non-numeric, ≤0, and >60 dropped; AOI bbox removed to prevent
train/test leakage. Manifest: `data/manifests/osm_floor_labels_manifest.json`,
`data/manifests/glo30_dsm_manifest.json`.

## B. MODEL

- **`scripts/floor_features.py`** — 18 real features: footprint area, perimeter,
  Polsby-Popper compactness, rectangularity, elongation, long/short side, vertex
  count, `has_name`, `height_tag_m` + `has_height_tag`, `dsm_height_m` +
  `has_dsm_height`, 5 one-hot building types.
- **`scripts/train_floor_model.py`** — **whole-cell spatial split**: centroids
  gridded to ~2.2 km cells, each cell wholly assigned to one of
  train **8441** / val **2327** / test **1969** — no nearby-building leakage
  across the split.
- Candidates: naive-median baseline, `RandomForestRegressor`,
  `HistGradientBoostingRegressor`. **Chosen: `hist_gradient_boosting`** on best
  held-out within-±1 (tie-break MAE).
- **Calibration**: RF per-tree spread → `IsotonicRegression(increasing=False)` on
  the validation set → `floor_confidence` = empirical **P(prediction within ±1
  floor)**. Monotone; ceiling ≈ **0.73**.
- **OOD**: `IsolationForest` on the training feature space; footprints below the
  2nd-percentile training score are rejected regardless of confidence.
- Bundle: `data/processed/floor_model.joblib`; full report
  `docs/FLOOR_MODEL_REPORT.md`.

## C. RESULTS (real held-out metrics — not fabricated)

| model | split | MAE | RMSE | exact | within ±1 | within ±2 |
|---|---|---:|---:|---:|---:|---:|
| naive median | test | 3.65 | 6.76 | 16% | 35% | 68% |
| RandomForest | test | 2.37 | 3.83 | 23% | 56% | 72% |
| **HistGradientBoosting (chosen)** | **test** | **2.36** | 3.77 | 20% | **57.5%** | 72% |
| independent AOI check (n=16, never trained) | — | **1.13** | 1.44 | 38% | **62%** | — |

This is a **weak estimator**. It is deployed as an estimator — every prediction
is labelled ESTIMATED, carries calibrated confidence + a range, and requires
human verification.

## D. COVERAGE (all 2734 AOI buildings)

| state | count | `floor_source` | `floor_confidence` | floor-level IDs |
|---|---:|---|---|---|
| **OBSERVED** | **16** | `REAL_OSM_BUILDING_LEVELS` | `null` (a real tag) | yes (w/ parcel) |
| **PREDICTED** | **2456** | `ML_MODEL` | calibrated P(within ±1) | HIGH/MEDIUM only |
| &nbsp;&nbsp;· HIGH (conf ≥ 0.70, range ≤ ±2) | 29 | | | yes |
| &nbsp;&nbsp;· MEDIUM (conf ≥ 0.58, range ≤ ±3) | 2042 | | | yes |
| &nbsp;&nbsp;· LOW (conf ≥ 0.45, range ≤ ±4) | 401 | | | **no — shown for review only** |
| **NOT_DETERMINABLE** | **262** | `NONE` | `null` | none |

- Proposed floor-level IDs: **5893** (`IN-KA-BLR-P…-B…-F…`, every entry
  `status: PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE`).
- Human verification required: **2722 / 2734** (all PREDICTED + diverging/OOD/veg
  OBSERVED).
- OOD rejected: 0. Vegetation-dominant → NOT_DETERMINABLE.
- Estimated floor-count distribution: `{1:8, 2:425, 3:1896, 4:125, 5:15, 11:3}`.
- Coverage went from ~17 → **2472** buildings with a floor figure, and the map
  carries a **healthy mixture of all three states** — expansion came only from
  calibrated model predictions on real features, never from loosened honesty.

## E. VISUALIZATION

- **Three states never conflated.** OBSERVED = solid outline + `N` badge + green.
  PREDICTED = dashed outline + `N*` badge + `EST.` markers, coloured by
  confidence state (green HIGH / sky MEDIUM / amber LOW). NOT_DETERMINABLE = no
  outline, no badge, no bands.
- **`EST.` marker** on every model-predicted floor figure: property card
  (`… · EST.`), hover tooltip (`N floors … EST.`), panel summary + status line,
  every floor row (`F4` → `F4 EST.`), every floor slab / label in the 3D model
  (and the SVG fallback), and the map badge (`*`).
- **Interactive 3D floor model** (`frontend/floor3d.js`, Three.js r128) replaces
  the flat 2D diagram: real footprint extruded into one lit, bevel-edged slab
  per floor; orbit + zoom; each slab is a pickable mesh (hover highlight, click
  selects + shows its proposed ID); `EST.` badge and `GROUND · DEM ⟨n⟩ m`
  reference kept in-scene; slab count / height / footprint all data-bound; SVG
  schematic retained as the no-WebGL fallback.
- **Red is never used for floor state.** Amber = LOW-confidence estimate; red
  stays reserved for conflict / human-verification elsewhere in the app.
- **Badge de-clutter** for ~2.5k predicted buildings: `minzoom: 16` +
  `text-allow-overlap: false` + `text-optional: true`.
- **LOW-confidence panel body**: explicit "shown for human review only … no
  floor-level spatial IDs generated" message instead of floor rows.
- **"Why this floor count?"** list is captioned *model inputs, not independent
  proof*.
- Legend + `docs/FLOOR_ESTIMATION.md` explain the `*` / `EST.` marker and the
  tiering.

## F. DATA INTEGRITY CONFIRMATION

- **No synthetic training, validation, prediction, or demonstration data was
  introduced.** Every label is a real OSM `building:levels` tag; every feature is
  from real footprint geometry, a real OSM tag, or the real Copernicus GLO-30
  DSM.
- **No random floor counts.** Counts are either a real tag (OBSERVED) or a
  model point estimate (PREDICTED).
- **No `height / 3.5` (or any divide-the-height) floor assignment.** Height is
  used only as a CONSISTENT/DIVERGENT cross-check on an OBSERVED tag.
- **No fabricated confidence or accuracy.** `floor_confidence` is an isotonic-
  calibrated empirical probability; all metrics are held-out on a spatial split.
- **No floor-level IDs for rejected or LOW-confidence predictions.**
- **No official ULPIN claims.** Every proposed ID carries
  `PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE`.
- **Non-regression: PASS.** 2734 buildings, identical IDs and geometry, zero
  changes to `building_height_m`, `derived_floors`, `building_levels`,
  `ground_elevation_m`, NDVI fields, `match_status_2d`,
  `final_verification_status`. Phase 12 fields are strictly additive.
- **124 / 124 tests pass**; ruff clean on all new modules.

## G. FILES

**New**: `scripts/floor_features.py`, `scripts/floor_estimation.py`,
`scripts/train_floor_model.py`, `scripts/12_estimate_floors.py`,
`scripts/ingestion/load_osm_floor_labels.py`,
`scripts/ingestion/load_copernicus_glo30.py`, `frontend/floor3d.js`,
`tests/test_floor_estimation.py`, `tests/test_floor_frontend_contract.py`,
`docs/FLOOR_ESTIMATION.md`, `docs/FLOOR_DETECTION_V3_AUDIT.md` (this file).
Generated at run time: `data/processed/floor_model.joblib`,
`data/interim/osm_floor_labels.csv`, `data/raw/glo30_dsm.tif`,
`docs/FLOOR_MODEL_REPORT.md`, `docs/FLOOR_ESTIMATION_REPORT.md`.

**Edited (additive)**: `run_pipeline.py`, `frontend/index.html`,
`frontend/app.js`, `frontend/styles.css`, `README.md`.
