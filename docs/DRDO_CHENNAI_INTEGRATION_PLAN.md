# DRDO Chennai Dataset — Integration Plan

**Status:** Draft plan, not yet executed. No code has been changed to produce this document — see [Ground rules](#ground-rules).
**Scope:** How to fold `data/drdo/raw/chennai_test1.shp` into BoundaryLens without breaking `AGENTS.md`.
**Companion docs:** Read alongside `docs/AGENTS.md`, `docs/PHASES.md`, `docs/PHASE_EXECUTION_TEMPLATE.md`, `docs/TECH_AND_DATA_STRATEGY.md`.

---

## TL;DR

You have 8,611 real building footprints for a 2×2 km patch of Chennai, LiDAR-derived by DRDO between 2013–2018, with exactly one attribute: `Z_Max` (1m–86m). That's it — no cadastral parcels, no DEM, no floor counts, no legal metadata. It is a **building-mass layer**, not a second Bengaluru.

That's genuinely useful — real LiDAR from a defence-research agency is a stronger height source than anything else in the project — but it cannot replace or match the Bengaluru pilot, because the Bengaluru demo's best feature (parcel↔building matching → CONTAINED/MAJORITY/BOUNDARY_OVERLAP → provisional ULPIN) depends entirely on a cadastral layer Chennai doesn't have.

The right move, per `AGENTS.md` §10, is to treat Chennai as a **second, independent region track** — not a replacement pilot — that proves the pipeline generalizes to a new real dataset. `frontend_chennai/` and `run_pipeline_chennai.py` already exist as a stub of exactly this track; this plan finishes it properly.

Before any of the 15 phases below matter, there is one open question that determines whether `height_m` is even correct: **is `Z_Max` an above-ground building height, or an absolute rooftop elevation above sea level?** See Phase 1 — nothing downstream should be trusted until that's answered.

---

## Ground rules

- **Never edit or move anything under `data/drdo/raw/`.** Those five files (plus `.shp.xml`, `.cpg`, `.sbn/.sbx`) are the original DRDO delivery. Every phase below only ever *reads* from there and writes to `data/interim/`, `data/processed/`, or `docs/`.
- This plan does not touch `run_pipeline.py` or anything in the Bengaluru track. Chennai is additive.
- Every phase inherits `AGENTS.md` in full — the evidence-status vocabulary (VERIFIED / PROVISIONAL / CONFLICT / NOT_DETERMINABLE / HUMAN_VERIFICATION_REQUIRED), the "no fabricated data" rule, and the stop-condition list in §15 apply exactly as they do to the Bengaluru pipeline.
- One correction already needed: `data/manifests/drdo_chennai_manifest.json` currently lists `"schema": ["AGLheight", "MSLheight"]` — the actual file has neither; it has `Z_Max` only. Fix this in Phase 2, don't let it linger as a false record.
- Loose end spotted in the raw folder: `chennai_test_pt.shx` exists with no matching `.shp`/`.dbf`. That's a fragment of a *different* (point) layer DRDO may have intended to include — worth asking your professor for the missing companion files; it might carry per-point elevation or a ground-truth reference that resolves Phase 1 outright.

---

## Phase 0 — Provenance & legal confirmation

**Meaning:** Establish, in writing, what "(legally) got my hands on it" actually means before this data appears in anything gradeable or public.
**Why:** `AGENTS.md` §9 forbids implying a dataset is more than it is. "DRDO data via professor" is not yet a citable source — it has no URL, no licence, no acquisition record.
**How:** Ask the professor directly: (a) is this an official DRDO product or a derived/internal extract; (b) is it cleared for use in an SIH submission and any public repo/demo; (c) can it be attributed by name, or does it have to stay uncredited/internal-only. Record the answer verbatim in the manifest's `source`/`licence` fields — do not upgrade "professor gave it to me" into "DRDO" in your own words.
**Verification:** `data/manifests/drdo_chennai_manifest.json` has a real `source` and `licence` value, not `UNVERIFIED_INTERNAL` / `UNVERIFIED_PROPRIETARY`.
**Stop condition:** If the professor can't confirm redistribution/demo rights, keep the whole Chennai track in a private branch and never surface it in the public repo, submission video, or judge-facing UI. This is exactly the AGENTS.md §15 case: *"a dataset cannot be legally/technically accessed."*

**Agentic prompt:** none — this is a conversation with your professor, not an agent task.

---

## Phase 1 — Resolve `Z_Max` semantics (blocking)

**Meaning:** Determine whether `Z_Max` is (a) building height above ground (AGL) or (b) the maximum rooftop elevation above sea level (MSL/ellipsoid) captured at each footprint's highest vertex.
**Why this is genuinely ambiguous:** The `.shp.xml` lineage shows DRDO ran ArcGIS **`AddZInformation`** on the geometry — that tool's normal job is to read the Z-coordinate already embedded in 3D geometry vertices and write out a `Z_Max`/`Z_Min`/`Z_Mean` attribute. That reads as "maximum elevation of the roof," not "building height." Two numbers support the ambiguity either way: Chennai's ground elevation is mostly 0–15m ASL, so a rooftop-elevation reading of up to ~86m (a ~25-storey building on ~10m ground) is plausible — but so is an AGL height of 86m for a genuine Chennai high-rise. The low end is the tell: a **1m AGL building height** is implausible (no real structure), whereas a **1m Z_Max** is very plausible if it's an elevation reading over open/low ground.
**How:**
1. Pull an independent DEM for the same 2×2 km AOI (Copernicus GLO-30 or Bhuvan CartoDEM — reuse `scripts/ingestion/load_copernicus_dem.py`/`load_bhuvan_dem.md` patterns).
2. Sample ground elevation under a handful of known-low-height footprints (small huts/sheds/boundary walls if any exist in the footprint set) and compare directly against their `Z_Max`.
3. Cross-check 3–5 buildings you can independently identify in the AOI (a landmark, a known-storey building) via satellite imagery/Google Earth against their `Z_Max`. If the number lines up with an AGL height for that many floors, it's AGL. If it's much larger and tracks local terrain elevation instead, it's MSL.
4. Whichever way it resolves, document the reasoning and evidence in `docs/ELEVATION_REPORT.md` (or a new `docs/DRDO_HEIGHT_SEMANTICS.md`) so nobody re-litigates this later.
**Verification:** A written, evidenced conclusion — "Z_Max = AGL height, confidence HIGH/MEDIUM" or "Z_Max = MSL rooftop elevation, confidence HIGH/MEDIUM" — with the comparison data attached.
**Stop condition:** If the comparison is inconclusive (ambiguous within your available reference points), `height_m` for the entire Chennai track must carry `height_confidence: NOT_DETERMINABLE` end-to-end, and every downstream 3D visualization must say so in its legend. Do not silently pick the interpretation that "looks better in 3D."

**Agentic prompt:**
```
Read AGENTS.md and docs/DRDO_CHENNAI_INTEGRATION_PLAN.md.
Current phase: P1 — Z_Max semantic verification.

Inputs: data/drdo/raw/chennai_test1.shp (read-only), an independently
fetched DEM for the same bbox (fetch it, do not fabricate values).

Task:
1. Compute the AOI bbox from chennai_test1.shp directly (do not assume
   coordinates — read them from the data).
2. Fetch Copernicus GLO-30 (or Bhuvan CartoDEM, if reachable) for that
   bbox and save it as a new file under data/interim/ — do not touch
   data/drdo/raw/.
3. Sample DEM elevation at each footprint's centroid, join it alongside
   Z_Max in a scratch table (data/interim/chennai_zmax_check.csv).
4. Report the distribution of (Z_Max - dem_elevation) across all 8,611
   buildings: if this quantity clusters in a plausible AGL-height range
   (mostly single digits to ~90m, right-skewed like a real building
   height distribution), Z_Max is likely already AGL height and this
   difference is noise/error, not signal — flag for human judgment
   rather than deciding automatically that it's MSL. If Z_Max itself
   already tracks the DEM curve almost 1:1, that's strong evidence
   Z_Max is MSL elevation and Z_Max - dem_elevation is the real AGL
   height.
5. Do not average, do not fabricate ground-truth comparisons you cannot
   actually check. Report what the arithmetic shows and stop.

Do not guess. Do not proceed to any later phase.
Return: PASS with a documented conclusion (AGL / MSL / NOT_DETERMINABLE)
and the evidence, or BLOCKED with what's missing to decide.
```

---

## Phase 2 — Region config & manifest correction

**Meaning:** Give Chennai the same first-class config treatment Bengaluru has.
**Why:** `config/config_loader.py` hardcodes `bengaluru.json` as the default; every phase script downstream (`05_match_parcels_buildings.py`, `06_extract_elevation.py`, etc.) reads `get_active_config()`. Chennai needs its own `config/regions/chennai.json` with the *real* bbox (derived from the shapefile, not guessed) and the *real* CRS (`EPSG:32644`, already correctly read from the `.prj`).
**How:** Create `config/regions/chennai.json` mirroring `bengaluru.json`'s shape (`region_name`, `state`, `district`, `bbox`, `crs_source`, `crs_processing`, `datasets`). Extend `get_active_config()` to accept a region argument (or an env var) rather than hardcoding Bengaluru, so a Chennai run doesn't require hand-editing shared config. Fix `data/manifests/drdo_chennai_manifest.json`: `schema` should read `["Z_Max"]`, not `["AGLheight", "MSLheight"]`, and `source`/`licence`/`acquisition_date` should reflect whatever Phase 0 actually confirmed.
**Verification:** `chennai.json` bbox matches the shapefile's actual bounds (checked programmatically, not eyeballed); manifest schema field matches `gdf.columns` exactly.
**Stop condition:** Per AGENTS.md §16, don't mark this phase done while the manifest still describes columns that don't exist in the file.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P2 — region config & manifest correction.
Do not edit anything in data/drdo/raw/.

1. Read data/drdo/raw/chennai_test1.shp, compute its true bounding box
   in EPSG:4326.
2. Create config/regions/chennai.json following the exact structure of
   config/regions/bengaluru.json, with crs_source EPSG:4326,
   crs_processing EPSG:32644, and the bbox from step 1.
3. Modify config/config_loader.py's get_active_config() to take a
   region_file parameter (default stays "bengaluru.json" so the
   existing pipeline is unaffected) instead of only ever loading
   Bengaluru.
4. Correct data/manifests/drdo_chennai_manifest.json: schema -> ["Z_Max"],
   and update source/licence/acquisition_date only if Phase 0 produced
   real values — otherwise leave them explicitly UNVERIFIED, don't
   invent plausible-looking values.

Verification: print config to confirm bbox is not a placeholder, and
diff manifest schema field against gdf.columns.tolist().
Return PASS/BLOCKED per the template.
```

---

## Phase 3 — Ingestion hardening

**Meaning:** Turn `scripts/ingestion/load_drdo_chennai.py` from a quick script into something that matches the rigor of the other loaders.
**Why:** The current script silently assumes EPSG:32644 only if CRS is `None` (it isn't — the `.prj` already declares it, so that branch is dead code) and blindly renames whichever of `Z_Max`/`AGLheight` it finds without validating row count, null rate, or plausibility.
**How:** Assert (don't assume) the CRS read from the file matches EPSG:32644, and fail loudly if it doesn't. Add a schema check: exactly one height-like column, with a name whose semantics were fixed in Phase 1 — rename it to `height_m` **only if Phase 1 concluded AGL**; if Phase 1 concluded MSL, compute `height_m = Z_Max - dem_elevation` here instead of a bare rename, and keep the raw `Z_Max` value too for traceability. Emit a row-count check (8,611 in, 8,611 out) and a null/negative-height check.
**Verification:** Script output prints the same 8,611 count, zero nulls in `height_m`, and no negative heights; failing any of those halts the script rather than writing a bad file.
**Stop condition:** If Phase 1 wasn't resolved, this phase cannot proceed — `height_m` would be meaningless.

**Agentic prompt:**
```
Read AGENTS.md and the P1 conclusion in docs/DRDO_HEIGHT_SEMANTICS.md
(or wherever P1 recorded it). Current phase: P3 — ingestion hardening.
Do not edit data/drdo/raw/.

Modify scripts/ingestion/load_drdo_chennai.py:
- Assert CRS from the file, don't silently assume it.
- Apply the P1-resolved height formula (straight rename if AGL, or
  Z_Max minus sampled DEM elevation if MSL) to produce height_m.
- Add and print: input feature count, output feature count (must
  match), null count in height_m, min/max height_m.
- Fail (non-zero exit, no output file written) if row counts diverge,
  or if any height_m is null or negative.

Add a small pytest under tests/ that runs this against the real file
and checks the count/null/negative invariants above.
Return PASS/BLOCKED.
```

---

## Phase 4 — Data quality audit

**Meaning:** Apply the same geometry-validity pass Bengaluru got (`04_validate_data_quality.py`) to the Chennai footprints.
**Why:** 8,611 auto-extracted LiDAR polygons will have some self-intersections, slivers, and duplicates — undetected, these break Phase 8/10/11 downstream.
**How:** Reuse `04_validate_data_quality.py`'s checks (Shapely validity, duplicate detection, empty/degenerate geometry) against the Chennai processed output, parameterized by the new `chennai.json` config.
**Verification:** A PASS/WARN/FAIL quality report, same shape as `docs/DATA_QUALITY_REPORT.md`, written for Chennai specifically (don't overwrite the Bengaluru one).
**Stop condition:** Any FAIL-severity geometry issue (unfixable self-intersections beyond a small tolerance) halts before Phase 8.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P4 — Chennai data quality audit.

Adapt scripts/04_validate_data_quality.py to run against the Chennai
processed buildings file (output of P3), using config/regions/chennai.json.
Produce docs/DATA_QUALITY_REPORT_CHENNAI.md in the same format as the
existing docs/DATA_QUALITY_REPORT.md. Do not modify the Bengaluru
report or pipeline.
Return PASS/BLOCKED with the report path.
```

---

## Phase 5 — Ground elevation layer

**Meaning:** Get an independent DEM for the Chennai AOI into the project properly (not just as a Phase-1 scratch check).
**Why:** Even if Phase 1 concludes `Z_Max` is already AGL height, you still need ground elevation to place the extruded 3D buildings at the correct absolute altitude on a real terrain (same reason Bengaluru has `dem_normalised.tif`). If Phase 1 concluded MSL, this DEM is load-bearing for the height formula itself, not optional.
**How:** Reuse `scripts/ingestion/load_copernicus_dem.py` (or `load_bare_earth_dem.py`), pointed at `chennai.json`'s bbox.
**Verification:** DEM covers the full AOI with no nodata gaps under the footprints; CRS/resolution logged, matching the existing DEM report format.
**Stop condition:** If the DEM API fails or coverage doesn't include Chennai (as `load_bare_earth_dem.py` already does), print the existing `"DEM STATUS: INVALID/UNSUPPORTED"` message and stop — don't fall back to a guessed constant elevation.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P5 — Chennai ground elevation.

Run the Copernicus/bare-earth DEM loader against config/regions/chennai.json's
bbox, saving to data/interim/chennai_dem.tif. Verify full spatial
coverage of the AOI (no nodata under any footprint centroid). If
coverage or download fails, stop and report BLOCKED — do not
substitute a constant or estimated elevation.
```

---

## Phase 6 — Height attribute finalization

**Meaning:** Produce the final, provenance-tagged `height_m` field for every Chennai building, following the same evidence ladder as `08_fetch_real_heights.py`.
**Why:** Bengaluru's height pipeline has an explicit hierarchy (OSM levels > DSM-DEM derived > not-connected). Chennai's is simpler but must follow the same discipline: DRDO LiDAR is your *only* and *best* source here, so it should be tagged accordingly rather than run through the Bengaluru fallback-simulation branch (which exists specifically to cover for *missing* real data — Chennai isn't missing real data, it has it).
**How:** Tag every record `height_source: "DRDO_LIDAR_2013_2018"`, `height_confidence` derived from Phase 1's outcome (HIGH if semantics were clearly resolved with strong evidence, MEDIUM if resolved with weaker evidence, NOT_DETERMINABLE if Phase 1 stopped inconclusive). Do **not** run the `random`-seeded floor/height simulation fallback from `08_fetch_real_heights.py` against this data — that branch is a presentation fallback for when no real source exists, and using it here would silently discard real DRDO measurements.
**Verification:** Every one of the 8,611 records has a non-null `height_m`, a `height_source` of `DRDO_LIDAR_2013_2018`, and a `height_confidence` consistent with Phase 1's documented conclusion.
**Stop condition:** If any record needs a fallback/simulated height, that's a sign Phase 3/4 lost data — halt and find out why rather than filling the gap.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P6 — Chennai height finalization.

Using the P3 output and P1's documented conclusion, tag every building
record with height_source="DRDO_LIDAR_2013_2018" and a
height_confidence consistent with P1. Do not invoke any simulated/
random height fallback against this dataset — it has real height
values for all 8,611 records; a fallback firing here means an earlier
phase silently dropped data, which should be investigated and reported,
not papered over.
Return PASS/BLOCKED, with the count of any record missing height_m.
```

---

## Phase 7 — Cadastral gap: decide and document

**Meaning:** Explicitly resolve what happens where Bengaluru's Phase 5 (`05_match_parcels_buildings.py`) would go — Chennai has no parcel layer at all.
**Why:** This is the single biggest capability gap versus Bengaluru, and it must be a documented decision, not a silent skip.
**How:** Two real options, not mutually exclusive:
  - **(a) Source a real Chennai cadastral layer independently** — repeat a mini Phase-1-style dataset discovery audit (Chennai Corporation / TNGIS / OpenCity-style open cadastral data, if any covers this exact 2×2 km patch) and, if found, run the existing `05_match_parcels_buildings.py` unmodified against it (it's already config-driven).
  - **(b) Proceed without a parcel layer.** Every Chennai building record gets `linked_parcel_id: null`, `match_status_2d: "NO_CADASTRAL_LAYER"` (a new status distinct from Bengaluru's `NO_PARCEL`, which means "parcel data exists but this building falls outside it" — Chennai's case is "no parcel data exists at all," a materially different and more limited claim).
**Verification:** A short `docs/MATCHING_REPORT_2D_CHENNAI.md` stating explicitly which path was taken and why.
**Stop condition:** Do not let a UI or slide imply Chennai buildings are "matched to parcels" when they aren't — that would misrepresent the AOI's actual legal linkage.

**Agentic prompt:**
```
Read AGENTS.md and docs/MATCHING_REPORT_2D.md (Bengaluru's, for format
reference). Current phase: P7 — Chennai cadastral gap.

1. Spend up to 30 minutes searching for a genuinely open cadastral/
   parcel dataset covering the Chennai AOI from config/regions/chennai.json
   (Tamil Nadu e-Governance / TNGIS / any OpenCity-equivalent). Verify,
   don't assume, that any candidate actually covers this exact bbox.
2. If found and legitimately downloadable: run scripts/05_match_parcels_buildings.py
   against it via chennai.json, producing docs/MATCHING_REPORT_2D_CHENNAI.md.
3. If not found: set match_status_2d="NO_CADASTRAL_LAYER" and
   linked_parcel_id=null on every Chennai building record, and write
   docs/MATCHING_REPORT_2D_CHENNAI.md stating plainly that no cadastral
   layer exists for this AOI and why.

Do not fabricate parcel boundaries. Return PASS/BLOCKED with which path
was taken.
```

---

## Phase 8 — 3D reconstruction (extrusion)

**Meaning:** Turn the 2D footprints + `height_m` into the 3D view — this is largely already working (`frontend_chennai/app.js` already extrudes on `height_m`, and the `AGLheight`→`Z_Max` bug is already fixed per your session notes).
**Why:** Confirm it's placing buildings at the correct absolute elevation using the Phase 5 DEM, not flat at sea level, and that it's reading the finalized `height_m` from Phase 6, not raw `Z_Max`.
**How:** Verify `app.js`'s MapLibre `fill-extrusion-base`/`fill-extrusion-height` paint properties reference the Phase 6 output and (if relevant) a per-building ground elevation offset from Phase 5.
**Verification:** Visual spot-check in-browser at `localhost:8001` against a couple of known-tall buildings in the AOI; extrusion base isn't uniformly zero if terrain varies.
**Stop condition:** None new — this is confirmation of already-working code, not a blocking gate.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P8 — Chennai 3D extrusion check.

Confirm frontend_chennai/app.js reads height_m (P6 output) and, if
Phase 5's DEM shows meaningful terrain variation across the AOI, uses
a per-building ground elevation for fill-extrusion-base rather than a
flat 0. Do not change the extrusion logic if it's already correct —
just verify and report. Take a screenshot of localhost:8001 for the
verification record.
```

---

## Phase 9 — Floor evidence

**Meaning:** Decide, honestly, what (if anything) can be said about floor counts.
**Why:** `AGENTS.md` §4/§5 is explicit: height alone must not be presented as an exact floor count. Chennai has *no* OSM `building:levels`, no floor plans, no labelled floor data of any kind — only `height_m`.
**How:** Do **not** apply the Bengaluru `height_m / 3.5` heuristic as if it were a determination. Two acceptable options: (a) output `derived_floors: NOT_DETERMINABLE` for every Chennai record (most defensible), or (b) output an explicitly-labelled *estimate* (`derived_floors_estimated`, `floor_confidence: LOW`) using the 3.5m heuristic, kept clearly separate from any field that looks authoritative. Pick (a) unless there's a specific narrative reason to show floor estimates in the demo, in which case use (b) and make the estimation visible in the UI, not hidden in a tooltip.
**Verification:** No field named plainly `floors` or `derived_floors` claims a number without an accompanying confidence/status tag that a viewer would actually see.
**Stop condition:** Per AGENTS.md §15, "labelled data is insufficient for the proposed ML task" applies directly here — don't train or apply any floor-prediction model against this dataset; there's nothing to validate it against.

**Agentic prompt:**
```
Read AGENTS.md §4-5. Current phase: P9 — Chennai floor evidence.

Add floor fields to the Chennai building records: derived_floors =
NOT_DETERMINABLE by default. Only if explicitly instructed to show an
estimate for demo purposes, add a separately-named
derived_floors_estimated (height_m / 3.5, rounded) with
floor_confidence="LOW" and a visible UI label indicating it's an
estimate, not a determination. Do not present any floor number as
authoritative. Do not run or fit any ML floor-prediction model against
this dataset — there is no labelled ground truth to validate it.
```

---

## Phase 10 — AI anomaly detection

**Meaning:** Run the Isolation Forest anomaly pass, adapted to what Chennai actually has.
**Why:** Bengaluru's anomaly features include `overlap_ratio` (needs a parcel) — Chennai can't use that. The feature set has to change, not just run the same code with nulls.
**How:** Use a feature vector of what's genuinely available: `height_m`, `area_sqm`, local footprint density/nearest-neighbor spacing. Document that "anomaly" here means "statistically unusual footprint/height combination," not "boundary/legal conflict" (which needs the parcel layer this AOI lacks).
**Verification:** `docs/AI_ANOMALY_REPORT_CHENNAI.md` states the feature set used and explicitly notes it differs from Bengaluru's.
**Stop condition:** Don't reuse Bengaluru's exact feature schema with missing fields zero-filled — that silently changes what the model is measuring without saying so.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P10 — Chennai AI anomaly detection.

Adapt scripts/09_detect_anomalies_ai.py for Chennai: feature vector =
[height_m, area_sqm, nearest_neighbor_distance] (compute the last one
from footprint centroids). Do not include overlap_ratio or any
parcel-derived feature — none exists for this AOI. Produce
docs/AI_ANOMALY_REPORT_CHENNAI.md explicitly stating the feature set
differs from Bengaluru's and why.
```

---

## Phase 11 — Topology validation

**Meaning:** Building-to-building topology checks (overlaps, duplicates) — narrower in scope than Bengaluru since there's no parcel container to validate against.
**Why:** Still catches duplicate LiDAR extractions or overlapping footprints, a real risk in auto-extracted building layers.
**How:** Pairwise overlap check among the 8,611 footprints (spatial-index accelerated, same bbox-prefilter pattern already used in `05_match_parcels_buildings.py`).
**Verification:** Count of overlapping-footprint pairs found, with a threshold below which the pipeline proceeds and above which it's a stop.
**Stop condition:** A high rate of overlapping footprints indicates the extraction produced duplicates — halt and re-examine Phase 4 rather than proceeding into evidence fusion with duplicated buildings.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P11 — Chennai topology validation.

Check for overlapping/duplicate footprints among the 8,611 Chennai
buildings (bbox-prefiltered pairwise intersection, same pattern as
scripts/05_match_parcels_buildings.py's parcel loop). Report count and
percentage of buildings involved in an overlap. If it's a small
fraction, flag those specific records for P13's human review; if it's
large, stop and report BLOCKED — that likely means P4 didn't catch a
real geometry problem.
```

---

## Phase 12 — Evidence fusion & confidence ledger

**Meaning:** Produce one final verdict per Chennai building, following the same fusion logic as `10_fuse_evidence_engine.py`, but honest about the ceiling this AOI can reach.
**Why:** Bengaluru buildings can reach `VERIFIED` because they have parcel + height + floor evidence converging. Chennai buildings, missing a cadastral link entirely, **cannot** legally reach the same status — there's no parcel to verify containment against.
**How:** Cap every Chennai record's overall status at `PROVISIONAL` (height-verified, cadastral-unlinked) unless Phase 7 found a real cadastral layer, in which case the normal Bengaluru-style ladder applies. Never let a Chennai record read `VERIFIED` on the strength of height data alone.
**Verification:** `docs/EVIDENCE_FUSION_REPORT_CHENNAI.md` shows the status distribution, and no record shows `VERIFIED` unless P7 resolved a real parcel match for it.
**Stop condition:** Any code path that would assign `VERIFIED` to a Chennai record without a resolved parcel match is a bug — fix before proceeding.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P12 — Chennai evidence fusion.

Adapt scripts/10_fuse_evidence_engine.py for Chennai: cap final status
at PROVISIONAL for any record lacking a resolved parcel link (i.e.
match_status_2d == "NO_CADASTRAL_LAYER" from P7), regardless of how
strong the height evidence is. Only allow VERIFIED where P7 found and
applied a real cadastral match. Produce
docs/EVIDENCE_FUSION_REPORT_CHENNAI.md with the status distribution.
Assert no record shows VERIFIED without a real linked_parcel_id;
fail loudly if one does.
```

---

## Phase 13 — Human verification gate

**Meaning:** Surface the genuinely ambiguous cases to a reviewer instead of resolving them silently.
**Why:** AGENTS.md §8 requires this for legally significant uncertainty; Chennai has its own specific flavor of it (height-semantics edge cases, topology overlaps from P11, and the orphan `chennai_test_pt` fragment from Phase 0).
**How:** Route to the same reviewer queue/UI pattern already used for Bengaluru's `HUMAN_VERIFICATION_REQUIRED` records: implausible heights (very low/very high outliers relative to the AOI's distribution), any overlap flags from P11, and anything Phase 1 marked with less than HIGH confidence.
**Verification:** Reviewer queue populated with a real, bounded count (not all 8,611, not zero).
**Stop condition:** None new beyond AGENTS.md §8's existing requirement that reviewer actions be audit-logged.

**Agentic prompt:**
```
Read AGENTS.md §8. Current phase: P13 — Chennai human verification.

Flag for human review: (a) height_m outliers beyond a reasonable
percentile band for this AOI, (b) any building flagged by P11's
overlap check, (c) any record where P1's height_confidence is below
HIGH. Route these into the existing reviewer queue/UI pattern used for
Bengaluru, with APPROVE/CORRECT/REJECT/MARK_UNRESOLVED actions,
audit-logged the same way.
```

---

## Phase 14 — Vertical ULPIN linkage (partial)

**Meaning:** Generate the structured ID string, but honestly reflect that the parcel segment doesn't exist.
**Why:** `14_generate_vertical_ulpins.py` presumably composes `parcel → building → floor`. Chennai has no parcel component (unless P7 found one).
**How:** Use an explicit placeholder segment (`NO_CADASTRAL_LINK`) rather than omitting the field or inventing a parcel ID. The generated string should make the gap visible to anyone reading it, not paper over it.
**Verification:** Every generated ID for a non-parcel-linked Chennai building visibly contains the placeholder segment; none contain a fabricated-looking parcel reference.
**Stop condition:** AGENTS.md §2 — never let this be presented as, or mistaken for, an actual legally recognized ULPIN.

**Agentic prompt:**
```
Read AGENTS.md §2. Current phase: P14 — Chennai vertical ULPIN linkage.

Adapt scripts/14_generate_vertical_ulpins.py: where match_status_2d ==
"NO_CADASTRAL_LAYER", use a literal "NO_CADASTRAL_LINK" placeholder for
the parcel segment of the generated ID instead of a fabricated or
omitted value. Where P7 found a real parcel match, use the normal
scheme. Verify no generated ID could be mistaken for an official
government ULPIN — the wording/format should make clear this is a
BoundaryLens-internal proposed ID.
```

---

## Phase 15 — 3D web UI finalization

**Meaning:** Finish `frontend_chennai/` as a presentable, honest second demo.
**Why:** It already renders and extrudes; it needs a legend/disclosure layer so a viewer (a judge, a teammate) can't mistake it for Bengaluru-equivalent completeness.
**How:** Add a visible legend/banner: "DRDO LiDAR building mass — height-only layer, no cadastral/legal boundary data for this AOI." Style buildings by `height_confidence` or fusion status from P12/P13 rather than reusing Bengaluru's Green/Yellow/Red parcel-conflict coloring (which has no meaning here without parcels).
**Verification:** Screenshot review — legend visible, coloring scheme matches what's actually being shown.
**Stop condition:** None new.

**Agentic prompt:**
```
Read AGENTS.md. Current phase: P15 — Chennai 3D UI finalization.

In frontend_chennai/, add a visible on-map legend/banner stating this
is a DRDO LiDAR height-only layer with no cadastral data for this AOI.
Re-map building fill-extrusion color to reflect P12/P13 status
(PROVISIONAL / HUMAN_VERIFICATION_REQUIRED / etc.) rather than reusing
Bengaluru's parcel-conflict Green/Yellow/Red scheme, which doesn't
apply here. Take a screenshot for the verification record.
```

---

## Phase 16 — Documentation & manifest close-out

**Meaning:** Write the final Chennai-track report and reconcile every doc that now needs a second entry.
**Why:** Keeps the project's existing documentation discipline (`dataUse.md`'s real-vs-synthetic table, `DATASET_AUDIT.md`-style registry) intact instead of leaving Chennai undocumented next to a fully-documented Bengaluru track.
**How:** Write `docs/DRDO_CHENNAI_INTEGRATION_REPORT.md` summarizing what was built, what it proves, and — prominently — what it doesn't have (cadastral, floors, DEM-native). Add a row to `dataUse.md`'s real-data table for the DRDO layer. Update `data/manifests/drdo_chennai_manifest.json` one final time with whatever Phase 0/1 actually concluded.
**Verification:** All of the above files exist and are internally consistent with each other (same conclusions repeated everywhere, not contradicted).
**Stop condition:** None — this is the closing phase.

**Agentic prompt:**
```
Read AGENTS.md and every docs/*_CHENNAI.md / DRDO_* file produced by
P0-P15. Current phase: P16 — documentation close-out.

Write docs/DRDO_CHENNAI_INTEGRATION_REPORT.md summarizing: what the
DRDO dataset is, what P1 concluded about Z_Max, what was built (P2-P15),
what it can honestly claim (height-verified building mass, second real
AOI) versus what it cannot (no cadastral linkage, no floor determination,
capped at PROVISIONAL). Add one row to docs/dataUse.md's real-data table
for the DRDO LiDAR layer. Do a final consistency pass: the Z_Max
semantic conclusion, the manifest, and this report must all agree.
Return PASS with the report path.
```

---

## How to position this in the SIH pitch

Don't present Chennai as "we also did Bengaluru's demo in a second city" — it isn't, and a technical judge will notice the missing cadastral layer within one question. Present it as: *"the pipeline ingested a second real dataset from a different source (DRDO LiDAR, not OSM/satellite-derived) and a different city, and degraded honestly where data was missing rather than faking the gaps."* That is a stronger, more defensible claim, and it's the one `AGENTS.md` was actually written to make possible.
