# BoundaryLens Technical Specification

This document provides a comprehensive breakdown of the BoundaryLens backend data pipeline, explaining every script, how the code works, what we built, and the design rationale behind every decision.

---

## 1. Architectural Philosophy: What We Did & Why We Did It

BoundaryLens was built to solve SIH26011: *"Assigning 3D identities for surface parcels, multi-storey properties and underground infrastructure."*

**The Challenge**: Generating real 3D property boundaries is legally sensitive. If a hackathon prototype blindly hallucinates property boundaries or overwrites official deed data using AI, it violates core GIS principles and risks disqualification.
**Our Solution (The "Why")**: We built a **deterministic, evidence-based fusion engine**. 
- Instead of using AI to draw boundaries, we used deterministic GIS logic (Shapely) to intersect official 2D cadastral parcels with OpenStreetMap footprints. 
- Instead of guessing building heights, we used satellite ML predictions (Google Open Buildings 2.5D) and explicitly tagged their source and confidence level (`MEDIUM`).
- We used AI (Isolation Forest) strictly for **Anomaly Detection**, flagging spatial conflicts and height outliers for human review.
- We never overwrite a source; we maintain an immutable **Evidence Ledger**.

---

## 2. File & Codebase Breakdown

The pipeline is entirely Python-based, utilizing `GeoPandas`, `Shapely`, `Rasterio`, and `scikit-learn`. The pipeline is orchestrated via `run_pipeline.py`.

### Phase 1 & 2: Ingestion (`scripts/ingestion/`)
- **`load_osm.py`**: Queries the Overpass API to download building geometries in GeoJSON format for the pilot AOI (Bengaluru Urban). 
- **`load_cadastral.py`**: Downloads open-source property tax/parcel boundary data (e.g., OpenCity cadastral maps).
- **`load_copernicus_dem.py`**: Downloads the Copernicus GLO-30 Digital Elevation Model (DEM) raster to understand base terrain heights.
- *Why*: We need raw foundational layers representing physical structures (OSM), legal boundaries (Cadastral), and terrain (DEM).

### Phase 3 & 4: Normalisation & Quality (`scripts/03_...` & `scripts/04_...`)
- **`03_normalise_layers.py`**: Reprojects all GeoJSON files from `EPSG:4326` (Lat/Lon) to `EPSG:32643` (UTM 43N). 
  - *Why*: You cannot accurately calculate overlapping surface area in square meters using spherical coordinates (degrees). UTM 43N provides accurate metric calculations for India.
- **`04_validate_data_quality.py`**: Uses `Shapely.is_valid` to fix self-intersecting polygons and broken geometries before processing.

### Phase 5: Spatial Topology (`scripts/05_match_parcels_buildings.py`)
- **How it works**: Uses `geopandas.overlay(how='intersection')` to calculate exactly how much of a building's footprint falls inside a legal parcel boundary.
- **Output Logic**:
  - `CONTAINED`: >95% overlap.
  - `MAJORITY`: >50% overlap.
  - `BOUNDARY_OVERLAP` / `CONFLICT`: <50% overlap (encroachment).
- *Why*: Deterministic topology rules replace opaque AI models for legal boundary checks.

### Phase 6 & 8: 3D Elevation & Floors (`scripts/06_...` & `scripts/08_...`)
- **`06_extract_elevation.py`**: Uses `rasterio` to sample the DEM GeoTIFF exactly beneath each building centroid, assigning a `ground_elevation_m`.
- **`08_fetch_real_heights.py`**: Assigns a satellite-derived height (Google Open Buildings 2.5D profile) to each footprint.
- **`08_extract_floor_entities.py`**: Generates discrete JSON objects for every single floor in a building (e.g., `height_m / 3.5m = 4 floors`).
- *Why*: SIH26011 requires multi-storey vertical mapping. Since OSM lacked floor tags, we extracted 8,891 discrete floor entities using satellite data, proving the vertical entity model works.

### Phase 9: AI Assistance (`scripts/09_detect_anomalies_ai.py`)
- **How it works**: Uses `sklearn.ensemble.IsolationForest`.
- **Feature Vector**: `[parcel_overlap_ratio, building_height_m, ground_elevation_m, floor_count]`
- **Logic**: It looks for statistical outliers (top 3% contamination). E.g., a massive building on a tiny parcel, or a 10-story building in a single-story residential zone. Flags them as `AI_ANOMALY_DETECTED`.
- *Why*: AI assists human reviewers by highlighting complex multi-dimensional anomalies that simple 2D overlap checks might miss.

### Phase 10: Fusion Engine (`scripts/10_fuse_evidence_engine.py`)
- **How it works**: The master decision gate. It reads Phase 5 (2D Match) and Phase 9 (AI Flags).
- **Rules**:
  - If `CONTAINED` + No AI Anomaly ➔ `VERIFIED`
  - If `MAJORITY` + No AI Anomaly ➔ `PROVISIONAL`
  - If `BOUNDARY_OVERLAP` or `AI_ANOMALY` ➔ `HUMAN_VERIFICATION_REQUIRED`
- *Why*: To prevent the system from silently adjudicating legal boundaries, conflicts are hard-routed to a human review queue. It also writes `evidence_fusion_ledger.json`—an immutable audit log.

### Phase 14: Vertical ULPIN Linkage (`scripts/14_generate_vertical_ulpins.py`)
- **How it works**: Concatenates identifiers into a proposed 3D string: `IN-KA-BLR-P[Parcel]-B[Building]-F[Floor]`.
- *Why*: Directly solves the SIH problem statement by creating a hierarchical identifier schema capable of addressing individual apartments/units in multi-storey buildings.
