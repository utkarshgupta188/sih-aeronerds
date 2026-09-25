# AGENTS.md — BoundaryLens / SIH26011 Master Agent Constitution

## 1. Project
BoundaryLens is an SIH26011 prototype for 3D ULPIN-linked vertical property mapping.

The SIH statement asks for 3D identities for surface parcels, multi-storey properties and underground infrastructure, using GIS parcel layers, imagery/point clouds, floor plans, GNSS/CORS and DEM/DSM, with AI/ML for building extraction, floor segmentation, vertical parcel delineation and topology validation.

## 2. Product boundary
The prototype MUST NOT claim that it changes an official government ULPIN or creates a legally recognised 3D ULPIN.

The prototype creates a proposed vertical linkage:

ULPIN / parcel reference
→ building entity
→ floor entity
→ unit/volume entity

Official recognition requires the competent authority.

## 3. Evidence hierarchy
Do not silently choose a source when sources disagree.

Keep:
- source name
- source date
- source licence/usage terms
- geometry/attribute origin
- processing step
- model/version
- verification status

Possible statuses:
- VERIFIED
- PROVISIONAL
- CONFLICT
- NOT_DETERMINABLE
- HUMAN_VERIFICATION_REQUIRED

## 4. Elevation rules
DEM = terrain/ground elevation.
DSM = surface elevation.

DSM - DEM can provide an above-ground height signal where the datasets are compatible.

DSM/DEM alone MUST NOT be described as an exact floor-count source.

If a floor count is not supported by authoritative or validated evidence, return NOT_DETERMINABLE rather than guessing.

## 5. AI rules
Required prototype AI components:
1. U-Net or Mask R-CNN — building extraction/segmentation.
2. Random Forest or XGBoost — supported building-attribute prediction; floor prediction only if labelled floor data is genuinely available and evaluated.
3. Isolation Forest — anomaly/conflict detection.

AI assists; it does not adjudicate ownership, legal rights or disputes.

No fabricated datasets, labels, metrics or accuracy.

## 6. GIS rules
Use deterministic geometry operations for deterministic questions:
- CRS validation
- polygon validity
- intersection/containment
- 2D/3D overlap
- area/volume checks
- parcel/building/floor containment

Do not replace deterministic topology rules with an opaque model.

## 7. Confidence
Use qualitative confidence:
HIGH / MEDIUM / LOW / NOT_DETERMINABLE

If numerical confidence is used, it MUST come from a defined validation/calibration procedure and be documented.

## 8. Human verification
Conflicts and legally significant uncertainty must be surfaced to a reviewer.

Reviewer actions:
- APPROVE
- CORRECT
- REJECT
- MARK_UNRESOLVED

All reviewer actions must be audit logged.

## 9. Data policy
Never call synthetic data "government data".
Never imply a public dataset contains fields that it does not contain.
Every dataset needs a manifest.

Recommended manifest fields:
- dataset_id
- source
- URL
- licence
- acquisition_date
- spatial_extent
- CRS
- resolution
- schema
- known_limitations
- processing_version
- allow unverified manifest (if user chooses/warn user before proceeding)

## 10. Prototype geography
Default pilot area: Baramati ULB, Pune district, Maharashtra, because it appears in published NAKSHA pilot material and Pune district has government-reported cadastral-map digitisation progress.

Do NOT assume that every required layer is publicly downloadable for Baramati. The project uses a tiered data strategy:
Tier A = publicly accessible core data.
Tier B = optional authoritative/partner data if legitimately obtained.
Tier C = clearly labelled synthetic test data only for demonstrating unavailable interfaces.

if a new dataset is found and works, update the manifest in data/manifests/ and make it available. but do not change the original pilot area. create a seperate version for the dataset available

The agent must verify availability before claiming a layer exists.

## 11. Suggested open-source map stack
- OpenStreetMap for map data where licence/attribution is respected.
- MapLibre GL JS for map rendering.
- GeoJSON / vector tiles for project layers.
- CesiumJS or Three.js for 3D visualisation.
Do not scrape Google Maps or Google Street View.

## 12. Tech stack
Backend:
- Python 3.12+
- FastAPI
- Pydantic
- PostgreSQL + PostGIS

Geospatial:
- GeoPandas
- Shapely
- Rasterio
- PyProj
- GDAL
- PDAL/Open3D where point clouds are available

3D:
- CesiumJS or Three.js
- trimesh/Open3D for processing
- glTF/3D Tiles for visualisation where appropriate

AI:
- PyTorch
- U-Net/Mask R-CNN
- scikit-learn
- XGBoost
- Isolation Forest

Frontend:
- React/Next.js
- TypeScript
- MapLibre GL JS
- CesiumJS/Three.js

Testing:
- pytest
- Playwright for E2E
- Ruff
- mypy/pyright where appropriate

## 13. Git rules
main is protected.
Use feature branches:
feature/<name>
fix/<name>
research/<name>
docs/<name>

Never commit:
- secrets
- API keys
- credentials
- private government records
- massive raw datasets
- generated build artefacts

Use Git LFS or external object storage for large permitted artefacts.

## 14. Agent loop
Every phase:
PLAN → IMPLEMENT → TEST → VERIFY → DOCUMENT → PASS/BLOCK.

An agent may not advance after a failed verification gate.

## 15. Stop conditions
STOP and report BLOCKED if:
- a dataset cannot be legally/technically accessed
- CRS is unknown or incompatible
- a schema is ambiguous
- a required legal interpretation is unsupported
- labelled data is insufficient for the proposed ML task
- a source conflict cannot be resolved
- output accuracy cannot be measured
- implementation requires fabricated data
- an agent would need to claim official legal recognition
- tests fail and the failure is not understood
- an architectural change is required but not approved
- if override is initiated, do as said. 

## 16. Definition of Done
A phase is complete only when:
- implementation exists
- tests exist
- tests pass
- output has been inspected
- provenance is recorded
- limitations are documented
- relevant skill/README is updated
- no AGENTS.md rule is violated
