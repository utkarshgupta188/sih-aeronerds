# Phased implementation plan

## Phase 0 — Constitution
Meaning: establish project rules, claims, legal boundary and architecture.
Why: prevents agents from inventing facts or building the wrong product.
How: create AGENTS.md, data policy, folder structure and branch rules.
Verification: files exist; rules reviewed.
Stop: unresolved project scope.

## Phase 1 — Data discovery
Meaning: prove which datasets actually exist for the pilot AOI.
Why: the entire pipeline depends on data availability.
How: create a manifest for cadastral, DEM, DSM/point cloud, OSM, Open Buildings, floor/height sources.
Verification: every dataset has URL/source/licence/CRS/schema/coverage.
Stop: dataset cannot be accessed legally or attributes are misrepresented.

## Phase 2 — Ingestion
Meaning: download/read data into raw storage.
Why: establish reproducible inputs.
How: one loader per source; never edit raw files.
Verification: hashes, metadata, sample read, geometry count.
Stop: corrupt file, unknown CRS, licence problem.

## Phase 3 — Normalisation
Meaning: make CRS, schemas and units consistent.
Why: spatial fusion fails if coordinates/units are wrong.
How: PyProj/GDAL/GeoPandas; standard project CRS; record transformations.
Verification: overlays align; bounds are plausible.
Stop: CRS or vertical datum cannot be established.

## Phase 4 — Data quality
Meaning: validate geometry and raster quality.
Why: invalid inputs create false 3D results.
How: Shapely validity, raster nodata checks, duplicate checks, outlier checks.
Verification: quality report with PASS/WARN/FAIL.
Stop: critical quality failure.

## Phase 5 — Parcel/building matching
Meaning: connect buildings to cadastral parcels.
Why: vertical mapping needs a parcel-to-building relationship.
How: intersection/containment/overlap ratio and conflict flags.
Verification: inspect sample matches visually and numerically.
Stop: systematic misalignment.

## Phase 6 — Elevation processing
Meaning: process DEM and optional DSM/point cloud.
Why: vertical geometry needs Z information.
How: align rasters; DSM-DEM where compatible; point-cloud processing when available.
Verification: plausible height distribution and CRS/datum checks.
Stop: treating DEM as DSM or claiming exact floors from height.

## Phase 7 — 3D reconstruction
Meaning: convert footprints and elevation evidence into volumes.
Why: this is the core 3D cadastral representation.
How: extrusion for MVP; detailed mesh when point cloud/BIM exists.
Verification: valid meshes, correct containment, visual inspection.
Stop: self-intersecting/invalid volumes.

## Phase 8 — Floor evidence
Meaning: establish floor-level entities from evidence.
Why: vertical property requires floors/units.
How: authoritative floor plans first; OSM `building:levels`; validated AI only when labels exist.
Verification: source and confidence shown for every floor count.
Stop: guessing floor count.

## Phase 9 — AI
Meaning: add ML assistance.
Why: automate building extraction, attribute prediction and anomaly detection.
How:
- U-Net/Mask R-CNN for footprint extraction.
- RF/XGBoost for a clearly defined labelled attribute task.
- Isolation Forest for anomaly/conflict detection.
Verification: held-out metrics and error examples.
Stop: insufficient labels, no evaluation set, fabricated accuracy.

## Phase 10 — Fusion and conflict engine
Meaning: combine evidence without losing provenance.
Why: real-world land data will disagree.
How: evidence table + deterministic conflict rules + source lineage.
Verification: intentionally conflicting fixture is detected.
Stop: silent overwriting.

## Phase 11 — Topology
Meaning: validate 3D spatial relationships.
Why: invalid volumes undermine the cadastral model.
How: parcel/building/floor/unit containment and overlap checks.
Verification: known-invalid fixtures fail.
Stop: topology engine cannot distinguish valid/invalid cases.

## Phase 12 — Confidence and provenance
Meaning: explain why a result is trusted.
Why: cadastral outputs need auditability.
How: source authority, agreement, quality, freshness, model validation.
Verification: every derived field has provenance and status.
Stop: confidence is arbitrary.

## Phase 13 — Human verification
Meaning: give an authorized reviewer the final gate.
Why: the prototype must not adjudicate legal rights.
How: review queue, evidence panel, approve/correct/unresolved and audit log.
Verification: reviewer action changes status and creates audit record.
Stop: AI can bypass the review gate.

## Phase 14 — Proposed vertical ULPIN linkage
Meaning: connect the existing parcel/ULPIN reference to vertical entities.
Why: demonstrates the SIH target without falsely changing the official identifier system.
How: stable internal IDs for building/floor/unit; link them to the source parcel identifier.
Verification: traceability from vertical object back to source parcel and evidence.
Stop: prototype implies official legal issuance.

## Phase 15 — 3D UI
Meaning: make the system understandable to judges.
Why: the pipeline must be demonstrable.
How: MapLibre + Cesium/Three.js; floor toggles; evidence/conflict/provenance panels.
Verification: complete demo scenario works from raw inputs to review.
Stop: UI hides uncertainty or provenance.

## Phase 16 — SIH audit
Meaning: challenge every claim.
Why: avoid elimination for scope drift, unsupported claims or fake data.
How: adversarial review against the exact PS.
Verification: every PS requirement maps to an implemented or explicitly scoped module.
Stop: unresolved contradiction or unsupported claim.
