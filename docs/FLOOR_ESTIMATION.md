# Floor Detection (Phase 12, additive) — v3 ML

## WHY

BoundaryLens links `Parcel → Building → Height`. To support a **proposed
floor-level spatial linkage** it needs a floor count per building — from a real
observed tag *or* a real, trained, spatially-validated model — clearly marked as
one or the other, never presented as an authoritative plan.

Three states, always distinguishable in the data and the UI:

| state | meaning | floor count | floor IDs |
|---|---|---|---|
| **OBSERVED** | real OSM `building:levels` tag on this building | the tag value | yes (with parcel) |
| **PREDICTED** | ML estimate that cleared a calibrated-confidence gate; labelled **ESTIMATED / EST.** | model point estimate + range | HIGH/MEDIUM only |
| **NOT_DETERMINABLE** | no tag and the model abstained | none | none |

## STEP 1 — Data audit (all real sources; done before any model)

| source | value | usable as a floor label? |
|---|---|---|
| buildings in the demo AOI | **2734** | — |
| real OSM `building:levels` **in the AOI** | **16** | yes — held-out **independent check set**, never trained on |
| real OSM `building:levels` in **greater Bengaluru** (~30×30 km, AOI excluded) | **12,737** via Overpass, ODbL | **yes — the training set** |
| OSM `height` tags | a subset of the training set + 3 in AOI | feature only (`height_tag_m`) |
| Copernicus **GLO-30 DSM** (30 m) | coarse above-ground height per footprint | feature only (`dsm_height_m`), weak |
| authoritative / municipal / permit / BIM / LiDAR | **0** | — |
| imagery | Sentinel-2 **10 m top-down** | **no** — cannot resolve floors → no CNN |
| `building_height_m` | Google Open Buildings 2.5D, bucketed upstream to `{7, 10.5, 14} m` | **no** — not real per-building height; used only as an OBSERVED cross-check |

## STEP 3–6 / 15 / 19 / 31–32 — Model (real, trained, spatially validated)

**No CNN** — there is no sub-metre / floor-resolving imagery for these buildings.
Instead a **tabular supervised model on real geometry + OSM tags + coarse DSM**:

- `scripts/ingestion/load_osm_floor_labels.py` — pulls the **12,737** greater-
  Bengaluru `building:levels` labels via Overpass (AOI excluded → the 16 AOI
  labels stay an independent check set), computes footprint-geometry features,
  and samples the GLO-30 DSM height per building.
- `scripts/ingestion/load_copernicus_glo30.py` — fetches the GLO-30 DSM tiles
  (AWS Open Data, anonymous) and mosaics them to `data/raw/glo30_dsm.tif`.
- `scripts/floor_features.py` — the shared 18-column feature vector
  (`FEATURE_COLUMNS`): `area_m2, perimeter_m, compactness, rectangularity,
  elongation, long_side_m, short_side_m, n_vertices, has_name, height_tag_m,
  has_height_tag, dsm_height_m, has_dsm_height, type_{residential, commercial,
  civic, industrial, other}`.
- `scripts/train_floor_model.py` — **spatial split**: centroids are gridded into
  ~2.2 km cells and whole cells are assigned to train/val/test
  (**8441 / 2327 / 1969**) so nearby buildings never straddle the split. Models
  compared: naive-median baseline, RandomForest, HistGradientBoosting.

### Real held-out metrics (`docs/FLOOR_MODEL_REPORT.md`)

| model | split | MAE | RMSE | exact | within ±1 | within ±2 |
|---|---|---:|---:|---:|---:|---:|
| naive median | test | 3.65 | 6.76 | 16% | 35% | 68% |
| RandomForest | test | 2.37 | 3.83 | 23% | 56% | 72% |
| **HistGradientBoosting (chosen)** | **test** | **2.36** | 3.77 | 20% | **57.5%** | 72% |
| independent AOI check (n=16, never trained) | — | **1.13** | 1.44 | 38% | **62%** | — |

Chosen on best held-out within-±1 (tie-break MAE). The footprint-shape signal is
genuinely weak — this is an *estimator*, not a measurement.

### Calibrated confidence

RandomForest per-tree **spread** → `IsotonicRegression(increasing=False)` on the
validation set → `floor_confidence` = empirical **P(prediction within ±1 floor)**.
Monotone by construction; ceiling ≈ **0.73** for this feature set.

### Tiered acceptance (in-distribution only)

A prediction is only shown when it is **not** out-of-distribution
(`IsolationForest`, 2nd-percentile training score) and **not**
NDVI-vegetation-contaminated. Then, on `(calibrated confidence, predicted range)`:

| tier | gate | floor-level IDs? |
|---|---|---|
| **HIGH** | conf ≥ 0.70 and range ≤ ±2 | yes |
| **MEDIUM** | conf ≥ 0.58 and range ≤ ±3 | yes |
| **LOW** | conf ≥ 0.45 and range ≤ ±4 | **no** — shown for review only |
| **NOT_DETERMINABLE** | anything below LOW, or range too wide, or OOD, or veg-contaminated | no |

Every ML tier is labelled **ESTIMATED**, carries `floor_confidence` +
`floor_min…floor_max`, and sets `requires_human_verification = true`.

`floor_confidence_state` HIGH is essentially unreachable from shape alone, so a
real OSM tag reports state **HIGH**; a tag whose height cross-check diverges, or
that is OOD / vegetation-flagged, reports **MEDIUM**.

## Sources & result

| Status | `floor_source` | `floor_confidence` | Count |
|---|---|---|---:|
| **OBSERVED** | `REAL_OSM_BUILDING_LEVELS` | `null` (a real tag, not a probability) | **16** |
| **PREDICTED** | `ML_MODEL` | calibrated P(within ±1) | **2456** (29 HIGH · 2042 MEDIUM · 401 LOW) |
| **NOT_DETERMINABLE** | `NONE` | `null` | **262** |

Result on 2734: **16 OBSERVED · 2456 PREDICTED · 262 NOT_DETERMINABLE** ·
**5893** proposed floor-level IDs · human verification **2722/2734** ·
estimated floor-count distribution `{1:8, 2:425, 3:1896, 4:125, 5:15, 11:3}`.

> Coverage is expanded **only** through real labels + real features + real ML +
> calibration + validated thresholds. The LOW tier is visible for review but
> generates **no** proposed IDs, so an uncertain estimate never turns into a
> linkage. Nothing here is synthetic and no confidence number is invented.

Height is used **only** as a `CONSISTENT / DIVERGENT` cross-check on an OBSERVED
tag (2.8–3.7 m/floor band); it is never divided to produce a count.

## STEP 10 / 28 — NDVI integration

A PREDICTED / OBSERVED floor count is independent of the Copernicus height, so
surrounding / edge / mixed vegetation does **not** change it. When
`vegetation_pattern == VEGETATION_DOMINANT` the model **abstains**
(`NOT_DETERMINABLE`, `floor_vertical_context = VEGETATION_CONTAMINATED_HEIGHT`);
an OBSERVED tag stands but is routed to human verification with the same context
flag. Vegetation is never used to call a building a tree.

## STEP 17 / 27 — Out-of-distribution

`floor_ood_flag = true` + human verification when a footprint scores below the
2nd-percentile `IsolationForest` training score, or a count reaches
`OOD_FLOOR_COUNT = 40`. NOT_DETERMINABLE buildings are already outside anything
the system supports.

## STEP 9 / 16 / 24 — Fields added per building (nothing overwritten)

```
floor_detection_status        (OBSERVED | PREDICTED | NOT_DETERMINABLE)
floor_count_estimated / floor_min / floor_max   (ints or null)
floor_confidence              (calibrated float for PREDICTED, null otherwise)
floor_confidence_pct          (int 0-100 for PREDICTED, null otherwise)
floor_confidence_state        (HIGH | MEDIUM | LOW | NOT_DETERMINABLE)
floor_source                  (REAL_OSM_BUILDING_LEVELS | ML_MODEL | NONE)
floor_detection_method        (ML_FOOTPRINT_TAG_DSM_MODEL | OSM_BUILDING_LEVELS | NONE)
floor_detection_reason        (string)
floor_supporting_evidence     ([str]  - "why this floor count?" = model inputs, not proof)
floor_missing_evidence        ([str]  - what a NOT_DETERMINABLE building would need)
floor_height_consistency      (CONSISTENT | DIVERGENT | UNKNOWN)
floor_vertical_context        (OK | VEGETATION_CONTAMINATED_HEIGHT)
floor_ood_flag                (bool)
requires_human_verification   (bool; always true for PREDICTED)
floor_model_version           ("boundarylens-floor/v3-ml")
floor_label_source / floor_label_type / floor_label_provenance
floor_level_ids               (proposed floor-level IDs; [] unless OBSERVED/PREDICTED-HIGH/MEDIUM + parcel)
# compatibility aliases kept for older readers: floor_evidence_status,
# floor_count_min/max, floor_count_confidence, floor_prediction_score,
# floor_prediction_method, floor_prediction_reason, floor_review_recommendation,
# floor_evidence
```

`building_height_m`, `derived_floors`, `building_levels`, `ground_elevation_m`,
all NDVI fields, `match_status_2d`, `final_verification_status` are **read-only**
inputs to this phase. The ledger gets an additive
`evidence_lineage.floor_estimation` sub-key.

## STEP 14 — Proposed floor-level spatial IDs

`IN-KA-BLR-P<parcel digits>-B<building digits>-F<n>`, generated **only for an
OBSERVED building, or a PREDICTED building at HIGH / MEDIUM confidence, that has a
linked parcel**. Every entry carries
`status: PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE`. **Not an official ULPIN.**
LOW-confidence predictions and NOT_DETERMINABLE → zero IDs.

## STEP 11–13 / 21–25 — Frontend (Floor Detection & 3D Inspection)

- **Sidebar coverage counter** (`#floor-coverage`, real numbers from the loaded
  geojson): *Observed · real OSM tag* / *Predicted · ML model* (with a
  `high · medium · low` sub-line) / *Not determinable*, and a note that LOW
  estimates get no IDs and every ML estimate is flagged for verification.
- **Property card**: *Floor Estimate* with a ` · EST.` suffix for PREDICTED,
  *Prediction Confidence* (`NN% within ±1 · STATE`, or `Real OSM tag`),
  *Evidence* (`OBSERVED / PREDICTED / NOT_DETERMINABLE · method`),
  *Human Verification: REQUIRED* when applicable, and a **View Floor Levels**
  button.
- **Hover tooltip** (high-contrast dark card): OBSERVED → `N floors` +
  `Real OSM building:levels tag`; PREDICTED → `N floors (min–max)` **EST.** +
  `NN% within ±1 · STATE` + `ML estimate (footprint shape + OSM tags + coarse
  DSM)`; else `NOT DETERMINABLE` + reason.
- **`#toggle-floors` map control** (off by default): footprint **outline**
  coloured by `floor_confidence_state` — green HIGH, sky MEDIUM, amber LOW, grey
  otherwise — **solid** for OBSERVED, **dashed** for an ML estimate; a
  floor-count **badge** at zoom ≥ 16 with `text-allow-overlap: false` (so ~2.5k
  buildings don't clutter), rendered `N` for OBSERVED and `N*` for an estimate.
  **Red is never used here** — red is reserved for conflict / verification.
  `FLOOR DETECTION` legend block explains the `*` / `EST.` marker.
- **Floor panel** (`#floor-panel`) — building-first:
  1. header + building/parcel + a solid **✕** close (also **Esc**, also click on
     empty map). Switching buildings re-renders in place.
  2. an **interactive 3D building model** (`frontend/floor3d.js`, Three.js r128):
     one lit, bevel-edged slab per floor, extruded from the building's **real
     footprint** and sized to the derived height. Drag to orbit, scroll / pinch
     to zoom (pointer events contained to the canvas — the panel still scrolls).
     Each slab is a pickable mesh: hover highlights it, click selects it and
     shows its label + proposed ID in an in-scene tooltip. Floor labels
     (`GND EST.`, `F1 EST.`…), an `EST.` badge, and a `GROUND · DEM ⟨n⟩ m`
     reference stay visible in the scene. Slab / edge colour follows the
     confidence state. Falls back to the flat SVG schematic if WebGL / Three.js
     is unavailable.
  3. summary: source chip (`OBSERVED · REAL OSM TAG` / `MODEL-ESTIMATED · ML
     PREDICTION`), *Observed / Estimated Floors* (with **EST.** + range), model
     confidence % + state chip, *Status*, OOD / vegetation / HV notes,
     a LOW-confidence "no IDs" note, and a **"Why this floor count?"** list
     (explicitly captioned *model inputs, not independent proof*).
  4. **Show Entire Building** + **Explode** + **↻ Rotate** + **Reset** buttons —
     wired to both the map bands and the 3D panel model.
  5. one **floor row** per level: name (+ **EST.** for predicted), an
     `OBSERVED` / `PREDICTED · EST.` tag, the proposed spatial ID with a **copy**
     button, and a `model estimate NN% · STATE` meta line. Click a row, a 3D
     slab, or an SVG band → that floor highlights everywhere at once.
  6. **LOW-confidence body**: instead of floor rows, a panel explaining the
     estimate is shown for review only and **no floor-level IDs are generated**.
  7. footer: `⚠ PROPOSED FLOOR-LEVEL SPATIAL LINKAGE — NOT AN OFFICIAL ULPIN`.
- **3D presentation** (two, kept in sync): the panel's own Three.js model
  (above), and on the main map a faint full-height ghost of the real footprint
  plus stacked cyan floor bands (`base = (n-1)·h/floors … n·h/floors`); *Explode*
  separates both, *Reset* / *Show Entire Building* restore. Real geometry is
  never modified; helper layers and the WebGL context are disposed on close /
  building switch.
- **NOT_DETERMINABLE state** (`FLOOR DETECTION UNAVAILABLE`): reason, height /
  vertical-evidence / source / status rows, vegetation-contamination note where
  relevant, a *what would be required* list, and a **Human Verification** button
  (logs to the audit log). **No floor rows, no SVG bands, no IDs.**

## Limitations

- The footprint-shape + sparse-tag + coarse-DSM model is a **weak estimator**
  (test within-±1 ≈ 57%, calibrated ceiling ≈ 0.73). Predictions are shown as
  **ESTIMATED** with confidence + range + mandatory human verification, and the
  LOW tier produces no linkage.
- OBSERVED counts are crowd-sourced OSM tags (Tier-2), not authoritative.
- The derived height (`{7, 10.5, 14} m` Google 2.5D) and GLO-30 DSM (30 m) are
  too coarse for a strong per-building check on tall buildings.
- No imagery-based floor detection — Sentinel-2 cannot resolve floors.
- **No synthetic training / validation / prediction / demo data, no fabricated
  confidence, no `height / 3.5` floor assignment, no model-generated labels.**
  Unit tests use mocked numeric inputs only.

## Files

**New**: `scripts/floor_features.py`, `scripts/floor_estimation.py`,
`scripts/train_floor_model.py`, `scripts/12_estimate_floors.py`,
`scripts/ingestion/load_osm_floor_labels.py`,
`scripts/ingestion/load_copernicus_glo30.py`,
`frontend/floor3d.js` (Three.js floor-panel 3D model),
`tests/test_floor_estimation.py`, `tests/test_floor_frontend_contract.py`,
`docs/FLOOR_ESTIMATION.md` (this file); generated at run time:
`data/processed/floor_model.joblib`, `docs/FLOOR_MODEL_REPORT.md`,
`docs/FLOOR_ESTIMATION_REPORT.md`, `data/interim/osm_floor_labels.csv`,
`data/raw/glo30_dsm.tif`.

**Edited (additive)**: `run_pipeline.py` (+4 phase entries),
`frontend/index.html` (+`#floor-panel`, +`#floor-coverage`, +`#floor-legend`,
+Three.js r128 + `floor3d.js`, cache-busters), `frontend/app.js` (+floor
rendering / panel / 3D-model bridge / map helpers), `frontend/styles.css`
(+`#floor-panel` / `.f3d-*` / coverage / tooltip styles), `README.md`.
