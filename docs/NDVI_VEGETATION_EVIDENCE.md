# NDVI Vegetation Evidence & Building-Height Confidence (Phase 11, additive)

## WHY

Copernicus GLO-30 gives a **surface** elevation. Inside a building footprint the
elevated surface may be a **roof** or a **tree canopy**, and the DEM cannot tell
them apart. A tall canopy over (or beside) a footprint can therefore inflate the
elevation-derived building height.

## WHAT

An **independent vegetation-evidence layer** built from NDVI
(`NDVI = (B08 - B04) / (B08 + B04)`) computed from a single low-cloud Sentinel-2
L2A scene over **exactly the project's configured AOI**. For every building it
adds a bounded **building-height confidence** block. Nothing existing is changed.

## WHAT IT SOLVES

It reduces the risk of reading tree-canopy elevation as building height: where a
footprint shows strong vegetation response, the derived height is flagged as
possibly vegetation-derived and routed to human verification instead of being
treated as settled.

## WHAT IT DOES NOT SOLVE

NDVI indicates a **vegetation response**, not building geometry. A building can be
ringed by trees, vegetation can overlap a roof, shadows and mixed 10 m pixels
occur. NDVI alone **cannot prove** an elevation value belongs to a building.

## FINAL PRINCIPLE

> We do **not** claim "NDVI proves this is a building."
> We claim: *"NDVI provides vegetation evidence that increases or decreases
> confidence that the observed surface elevation represents the building."*

The score is an **evidence/confidence score**, not a calibrated probability of
correctness and not a legal certainty. It has **not** been calibrated against
labelled ground truth for this AOI. AI/evidence assists the reviewer; it does not
make a legal determination. Low confidence never hides or deletes a building.

---

## 1. NDVI data source & provenance

| Field | Value |
|---|---|
| Source | Copernicus **Sentinel-2 L2A** surface reflectance |
| Access | Element84 **earth-search** STAC (`https://earth-search.aws.element84.com/v1`), collection `sentinel-2-l2a`; COGs from `s3://sentinel-cogs` (AWS Open Data, anonymous HTTPS) |
| Scene selection | Least-cloud scene intersecting the AOI within the configured datetime window (`config/regions/<region>.json` → `datasets.ndvi.datetime`, default `2023-11-01 … 2024-04-30`, `max_cloud_cover` default 15%) |
| Bands | B04 red (10 m), B08 nir (10 m), SCL scene-classification (20 m) |
| Acquisition date | Recorded per run in `data/manifests/ndvi_<region>_manifest.json` and `data/interim/ndvi_status.json` (`scene_id`, `acquisition_datetime`, `eo:cloud_cover`, `processing_baseline`) |
| Spatial resolution | **10 m** (NDVI grid = B04 grid, not resampled) |
| Native CRS | **EPSG:32643** for the Bengaluru AOI — already the project's `crs_processing`; no NDVI reprojection |
| Preprocessing | windowed COG read for the AOI bbox → B08 bilinear-resampled to the B04 10 m grid, SCL nearest → NDVI on DN → `denom==0` / band-NoData / out-of-`[-1,1]` → NoData → SCL classes `{0,1,3,8,9,10,11}` (no-data, saturated, cloud shadow, cloud med/high, cirrus, snow) → NoData → float32 GeoTIFF, `nodata = -9999`, DEFLATE |
| Licence | Free and open. *"Contains modified Copernicus Sentinel data."* [Legal notice](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice) |

**If the scene cannot be obtained** (offline, STAC empty, read error, missing
libraries): no raster is written, `data/interim/ndvi_status.json` records
`ndvi_available: false` with a reason, and Phase 11 marks every building
`vertical_evidence_status = NDVI_UNAVAILABLE` with a **null** score. No values are
fabricated.

## 2. Raster / vector alignment

- NDVI raster stays in its native S2 UTM CRS (EPSG:32643). Its CRS is written into
  the file; Phase 11 **refuses to sample** a raster with no CRS rather than mix
  coordinate systems.
- Building footprints (EPSG:4326) are reprojected to the raster CRS with `pyproj`
  — the same transform approach as `scripts/05_match_parcels_buildings.py`.
- The **building footprint is the spatial constraint**: NDVI is sampled *inside*
  each footprint via `rasterio.mask`.
- NoData is explicit: `ndvi_pixels_total`, `ndvi_pixels_valid`,
  `ndvi_nodata_fraction` are all reported per building.

## 3. Per-building NDVI sampling (robust, not one pixel)

For each footprint:

1. Erode the footprint by **½ pixel (5 m)** to drop edge/mixed pixels, *if* the
   eroded shape still covers ≥ 1 pixel; otherwise sample the full footprint and
   set `ndvi_data_quality_flag = SMALL_FOOTPRINT` (footprint < ~1 pixel).
2. Take all pixels whose cell centre falls inside that shape; drop NoData and
   values outside `[-1, 1]`.
3. Robust statistics: **median**, p25, p75, IQR, and
   **`vegetation_fraction`** = share of valid pixels with `NDVI ≥ 0.40`.

Using the median + vegetation fraction means a single vegetated edge pixel cannot
invalidate a building; partial canopy overlap shows up as a mid-range
`vegetation_fraction` rather than a hard flip.

## 3b. Spatially-resolved evaluation — the robustness fix

> **A single footprint statistic still mistakes vegetation _around_ a real
> building for vegetation-derived height.** Phase 11 therefore evaluates four
> zones and asks *where* the vegetation is, not merely whether it is present.
> `evaluate_building_spatial()` in `scripts/ndvi_evidence.py` is the default;
> the flat `evaluate_building()` is kept for compatibility and unit tests.

**Four zones** (all sampled in the NDVI raster CRS, EPSG:32643):

| Zone | Geometry | Meaning |
|---|---|---|
| **core** | footprint eroded ½ pixel (5 m), cell-centres only | the building surface / roof |
| **interior** | the full footprint (any touched pixel; NoData denominator = real polygon-covered pixels via a masked read) | zone "B" |
| **edge** | ~1-pixel band straddling the footprint boundary | canopy touching / overhanging the outline |
| **ring** | 5–30 m outside the footprint | surrounding context (neighbourhood trees) |

Each zone gets a coarse **level**: `LOW` (median < 0.20 and veg-fraction < 0.15) ·
`HIGH` (median ≥ 0.40 or veg-fraction ≥ 0.60) · `MIXED` · `NONE` (no valid
pixels — never fabricated).

**Vegetation pattern** (new `vegetation_pattern` / `vegetation_evidence` value):

| Pattern | Zone signature | Effect on building-height confidence |
|---|---|---|
| `LOW_VEGETATION` | surface LOW, surroundings LOW | HIGH when score ≥ 0.70 & data OK |
| `SURROUNDING_VEGETATION` | surface LOW, edge/ring vegetated | **not reduced** by the surrounding trees — HIGH when score ≥ 0.70 & data OK, else MEDIUM |
| `EDGE_VEGETATION` | core clear, interior vegetated, boundary vegetated | MEDIUM + human verification |
| `INTERNAL_VEGETATION` | vegetation inside the footprint but **not** in the ring (courtyard, garden, green roof, footprint mismatch) | MEDIUM + human verification — *not* auto-tree |
| `MIXED_VEGETATION` | mixed within the footprint, no clear roof signal | MEDIUM + human verification |
| `VEGETATION_DOMINANT` | vegetation dominates core **and** interior **and** surroundings (or uniform veg-fraction ≥ 0.85) | LOW / `VEGETATION_POSSIBLE` + human verification |
| `RESOLUTION_LIMITED` | footprint ≲ one 10 m pixel, no reliable core, < 4 valid pixels | `NOT_DETERMINABLE` + human verification |
| `NODATA` / `NOT_DETERMINABLE` | no valid NDVI inside the footprint | `NOT_DETERMINABLE` + human verification |

**Core rule:** vegetation in the `edge`/`ring` zones is *context*; only vegetation
that dominates the building **surface** (`core`, else `interior`) lowers
confidence. A footprint at/below one pixel with no core cannot reach `HIGH`
(the roof is unresolved) — it is capped at `MEDIUM` or returned
`RESOLUTION_LIMITED`.

**Tall-height guard (spatial):** an unusually tall derived height only downgrades
confidence when the building *surface* NDVI is itself vegetated/ambiguous — never
"tall + vegetation nearby ⇒ tree".

Full weights and the per-run before/after audit are in
`ne.spatial_method_manifest()`, `docs/NDVI_VEGETATION_EVIDENCE_REPORT.md` and
`docs/NDVI_SPATIAL_AUDIT.md`.

## 4. Thresholds (heuristic, tunable, **not** ground-truth-validated)

| Constant | Value | Meaning |
|---|---|---|
| `NDVI_BARE_THRESHOLD` | `0.20` | at/below → vegetation contribution negligible (roof / impervious / dry soil) |
| `NDVI_VEG_THRESHOLD` | `0.40` | at/above → pixel shows a clear vegetation response (**not** "this is a tree") |
| `IQR_REFERENCE` | `0.40` | NDVI IQR treated as a fully mixed surface (spatial-consistency scaling) |
| `MIN_VALID_PIXELS` | `3` | fewer valid pixels → `NOT_DETERMINABLE` |
| `NODATA_FRACTION_MAX` | `0.60` | more NoData than this → `NOT_DETERMINABLE` |
| `NODATA_FRACTION_OK` | `0.20` | at/below → `data_quality_flag = OK`, else `PARTIAL_NODATA` |
| `HEIGHT_TALL_FLAG` | `60 m` | derived height above this cannot read as `HIGH` unless vegetation is clearly low |
| `HEIGHT_PLAUSIBLE_MAX` | `120 m` | above this the elevation sub-score is additionally weakened (never rewrites the height) |

Rationale: on Sentinel-2 surface reflectance, dense green canopy/grass typically
returns NDVI ≳ 0.4 while dry rooftops and impervious surfaces in this AOI sit well
below ~0.2–0.3. `0.40` is used as *"vegetation response present"*, deliberately
**not** as a building/tree decision boundary. All constants live in
`scripts/ndvi_evidence.py` and are echoed into the run report and ledger.

## 5. Building-height confidence score (bounded 0–1 and 0–100)

> *"How strongly does the available evidence support that this observed elevated
> surface/height belongs to the building rather than vegetation?"*

Weighted sum of five bounded sub-scores (weights sum to 1):

| Sub-score | Weight | From |
|---|---|---|
| `ndvi` | **0.40** | `0.5·(median mapped 0.20→1 … 0.40→0) + 0.5·(1 − vegetation_fraction)` |
| `footprint` | 0.15 | existing `match_status_2d` + `parcel_overlap_ratio` (CONTAINED 1.0 / MAJORITY 0.7 / BOUNDARY_OVERLAP 0.4 / NO_PARCEL 0.3, blended with overlap ratio) |
| `elevation` | 0.15 | existing `building_height_m` plausibility × `height_confidence` (HIGH/MEDIUM/LOW) — **read only** |
| `quality` | 0.20 | `1 − ndvi_nodata_fraction` |
| `consistency` | 0.10 | `1 − ndvi_iqr / 0.40` (spatial consistency within the footprint) |

`building_height_confidence_score ∈ [0,1]`, and `…_score_100` is that ×100.
Per-building `building_height_confidence_subscores` are stored for audit.
When NDVI is unavailable or insufficient the score is **`null`** — never a number.

## 6. Evidence categories

| Category | `vertical_evidence_status` | Condition |
|---|---|---|
| **HIGH BUILDING CONFIDENCE** | `SUPPORTED` | score ≥ **0.70** *and* `vegetation_evidence = LOW_VEGETATION` *and* `data_quality_flag = OK` — little/no vegetation in the footprint, elevation spatially consistent |
| **MEDIUM / MIXED CONFIDENCE** | `PROVISIONAL` | vegetation & building evidence mixed, limited resolution, or significant uncertain pixels |
| **LOW BUILDING CONFIDENCE / VEGETATION POSSIBLE** | `VEGETATION_POSSIBLE` | `vegetation_evidence = STRONG_VEGETATION` *or* score < **0.40** — elevation may be vegetation-derived |
| **NOT DETERMINABLE** | `NOT_DETERMINABLE` | `< MIN_VALID_PIXELS` valid pixels or `nodata_fraction > 0.60` |
| *(NDVI missing)* | `NDVI_UNAVAILABLE` | scene could not be obtained — score `null` |

With the spatial path (§3b), `vegetation_evidence` / `vegetation_pattern` takes
the pattern values: `LOW_VEGETATION` · `SURROUNDING_VEGETATION` ·
`EDGE_VEGETATION` · `INTERNAL_VEGETATION` · `MIXED_VEGETATION` ·
`VEGETATION_DOMINANT` · `RESOLUTION_LIMITED` · `NODATA` · `NOT_DETERMINABLE` ·
`NOT_COMPUTED`. `SURROUNDING_VEGETATION` reaches **HIGH** exactly like
`LOW_VEGETATION`; only `VEGETATION_DOMINANT` maps to `VEGETATION_POSSIBLE`. The
flat path's `STRONG_VEGETATION` is retained for its own tests.

## 7. Human-verification integration

Additive advisory field **`ndvi_review_recommendation`**:

- `HIGH` → `NONE`
- `MEDIUM` / `LOW` / `NOT_DETERMINABLE` / NDVI-unavailable → `HUMAN_VERIFICATION_REQUIRED`

Consistent with the project principle — low/mixed vertical confidence means
*"reviewer, please check"*, **never** *"this building is illegal"*. The existing
`final_verification_status` gate is **not modified**; an integrator may choose to
union the two, but that decision is left to the reviewer.

## 8. Fields added per building (nothing overwritten)

```
ndvi_value  ndvi_median  ndvi_p25  ndvi_p75  ndvi_iqr
ndvi_vegetation_fraction  ndvi_pixels_valid  ndvi_pixels_total  ndvi_nodata_fraction
ndvi_core_median  ndvi_edge_median  ndvi_ring_median  ndvi_surface_median  ndvi_footprint_pixel_ratio
ndvi_zone_levels                     ({core, interior, edge, ring} -> LOW|MIXED|HIGH|NONE)
ndvi_source  ndvi_scene_id  ndvi_acquisition_date  ndvi_resolution  ndvi_crs  ndvi_provenance
vegetation_evidence  vegetation_pattern  vegetation_evidence_label
building_height_confidence            (HIGH | MEDIUM | LOW | NOT_DETERMINABLE)
building_height_confidence_score      (0..1 or null)
building_height_confidence_score_100  (0..100 or null)
building_height_confidence_subscores  ({ndvi_surface, spatial, footprint, elevation, quality, consistency})
vertical_evidence_status  confidence_reason
ndvi_data_quality_flag   (OK | PARTIAL_NODATA | INSUFFICIENT_NDVI | RESOLUTION_LIMITED | NDVI_LAYER_UNAVAILABLE)
ndvi_review_recommendation
```

`ground_elevation_m` (Copernicus GLO-30) and `building_height_m` are **preserved
byte-for-byte**. Auditable triple kept side by side:

```
COPERNICUS_ELEVATION  +  NDVI_VEGETATION_EVIDENCE  +  DERIVED_BUILDING_HEIGHT_CONFIDENCE
```

Ledger: an **additive** `evidence_lineage.ndvi_vegetation_evidence` sub-key is
appended to `data/processed/evidence_fusion_ledger.json`;
`evidence_lineage.elevation_base` (`COPERNICUS_GLO30_DEM`) is left intact.

## 9. 3D visualisation

No building is hidden or removed. The existing property panel gains four rows —
*NDVI Evidence*, *Building Height Confidence*, *Vertical Evidence*, and (only when
relevant) *Human Verification: REQUIRED* — and the data-source line reads
`… + NDVI`. Extrusion heights, colours, toggles and the reviewer gate are
unchanged.

```
Building Height: 14.2 m            Building Height: 14.2 m
NDVI Evidence: Low vegetation      NDVI Evidence: Strong vegetation
Building Height Confidence: HIGH    Building Height Confidence: LOW
Vertical Evidence: SUPPORTED       Vertical Evidence: VEGETATION POSSIBLE
Source: Copernicus GLO-30 + NDVI   Human Verification: REQUIRED
```

## 10. Reproduce

```bash
pip install rasterio shapely pyproj numpy requests   # geo stack (+ pytest for tests)
python scripts/ingestion/load_sentinel2_ndvi.py       # writes data/raw/ndvi_s2_aoi.tif + manifest + status
python scripts/11_ndvi_vegetation_evidence.py         # annotates buildings_fused_final.geojson
python -m pytest tests/ -q                             # scoring-logic validation
```

`run_pipeline.py` runs both steps automatically after Phase 10.

## 11. Files

**New**

- `scripts/ndvi_evidence.py` — pure-Python scoring core (numpy only), unit-tested.
  Holds both the flat `evaluate_building()` and the spatial
  `evaluate_building_spatial()` / `classify_vegetation_pattern()` (§3b).
- `scripts/ingestion/load_sentinel2_ndvi.py` — Sentinel-2 NDVI fetch for the AOI
- `scripts/11_ndvi_vegetation_evidence.py` — Phase 11: 4-zone sampling + annotation
  + flat-vs-spatial audit
- `tests/conftest.py`, `tests/test_ndvi_evidence.py` (flat),
  `tests/test_ndvi_spatial.py` (spatial — surrounding / edge / internal / dominant
  / resolution-limited / NoData / tall-height / determinism / bounds)
- `docs/NDVI_VEGETATION_EVIDENCE.md` (this file)
- generated at run time: `data/raw/ndvi_s2_aoi.tif`,
  `data/manifests/ndvi_bengaluru_manifest.json`, `data/interim/ndvi_status.json`,
  `data/processed/buildings_ndvi_evidence.geojson`,
  `docs/NDVI_VEGETATION_EVIDENCE_REPORT.md`, `docs/NDVI_SPATIAL_AUDIT.md`

**Edited (minimal, additive)**

| File | Change | Why necessary |
|---|---|---|
| `run_pipeline.py` | +2 entries in the script list after Phase 10 | the new phase must execute in sequence |
| `config/regions/bengaluru.json` | +`datasets.ndvi` block | keep the datetime window / cloud threshold reproducible and in-repo (mirrors the existing `datasets.elevation` block; script has safe defaults if absent) |
| `frontend/index.html` | +4 `.prop-row`s in the property card (existing classes reused); `app.js?v=9`→`v=10` | Task item 8 — expose the new evidence in the existing panel |
| `frontend/app.js` | +1 render block in the existing click handler; ` + NDVI` on the source string | render the new rows; no existing branch touched |
| `data/manifests/dataset_manifest.csv` | +1 dataset row | AGENTS.md Rule 9 — every dataset needs a manifest entry |
| `README.md` | +1 data-source bullet | document the new source |

**No** existing field, building/parcel ID, `match_status_2d`, Isolation-Forest
result, fusion rule, `final_verification_status`, CRS choice, LOD1 extrusion,
matching threshold, or elevation value is changed.
