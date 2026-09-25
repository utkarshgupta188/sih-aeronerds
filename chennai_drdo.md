# Chennai DRDO Pipeline Reconstruction: A Walkthrough

This document outlines the complete technical journey, challenges, and architectural pivots we executed to make the BoundaryLens SIH prototype work with the provided DRDO dataset for Chennai.

## 1. Initial Data Assessment
We started with a raw DRDO shapefile (`data/drdo/raw/chennai_test1.shp`). Upon analysis via GeoPandas and checking the `chennai_test1.shp.xml` metadata, we discovered:
- The dataset contained exactly **8,611 building footprints** located in the Royapuram / Kasimedu area of North Chennai.
- It contained exactly **one attribute column**: `Z_Max`, representing the maximum building height derived from LiDAR.
- **The Challenge:** Unlike the Bengaluru dataset, this DRDO data lacked any Cadastral (legal property) boundaries, ground elevation grids, or AI anomaly flags.

### Breakdown of the Raw Shapefile Components
When you see a "Shapefile" in GIS, it is actually a bundle of mandatory and optional files. The `data/drdo/raw/` directory contains:
- **`chennai_test1.shp`**: The main geometry file. This stores the actual mathematical coordinates for all 8,611 3D polygons.
- **`chennai_test1.dbf`**: The dBase attribute database. This stores the tabular data attached to each polygon (in this case, just the single `Z_Max` column).
- **`chennai_test1.shx`**: The spatial index file. This allows GIS software to rapidly search and render the `.shp` file without loading the entire geometry file into memory.
- **`chennai_test1.prj`**: The projection format file. This tiny text file specifies that the coordinates are in **EPSG:32644 (UTM Zone 44N)**.
- **`chennai_test1.cpg`**: The character encoding file, specifying how text is encoded inside the `.dbf` database.
- **`chennai_test1.shp.xml`**: The XML metadata file. This contains the "lineage" or history of the dataset, revealing that DRDO used ArcGIS `ArcToolbox` tools (like "AddZInformation") to extract these building footprints from LiDAR point clouds.

## 2. First Attempt: Visualization MVP
To quickly visualize the data, we:
1. Wrote `scripts/ingestion/load_drdo_chennai.py` to convert the Shapefile (EPSG:32644) to a standard GeoJSON (EPSG:4326).
2. Duplicated the frontend to `frontend_chennai`.
3. Created a dedicated runner `scripts/run_pipeline_chennai.py` to process the data and spin up a local Python HTTP server.

*Initial Result:* The map showed flat, grey polygons because the frontend expected `building_height_m` but the data provided `Z_Max`, and it lacked the `match_status_2d` required for the green/yellow/red color logic.

## 3. The Cadastral Data Blockade
To run the full BoundaryLens engine (which generates 3D ULPINs by detecting conflicts between legal parcels and physical buildings), we needed Chennai's cadastral maps.
We initiated a **Data Discovery Sweep**:
- We searched OpenCity.in and the TN e-Services portals (`eservices.tn.gov.in`).
- We concluded that bulk cadastral shapefiles are **strictly restricted** by the TN Government. Only individual FMB/TSLR sketches can be viewed manually.
- Per project rules (`AGENTS.md` Rule 5 & 9), we were blocked from illegally scraping or blindly fabricating fake government data to force the pipeline to work.

## 4. The Breakthrough: Tier C Synthetic Strategy
Instead of abandoning the pipeline, we leveraged **Rule 10 of the AGENTS.md Constitution**, which permits using explicitly labeled "Tier C Synthetic Test Data" to demonstrate unavailable interfaces.
We reconstructed the pipeline around the DRDO data by simulating the missing layer:
- **`generate_synthetic_parcels_chennai.py`**: We wrote a script that computationally generated a 2-meter "property buffer" around every single DRDO building footprint.
- We tagged this generated layer explicitly as `source: TIER_C_SYNTHETIC_TEST_DATA` to ensure total transparency and rule compliance.
- We also added a formal manifest `data/manifests/chennai_synthetic_parcels_manifest.json`.

## 5. Scaling the Core Engine
With synthetic parcels in place, we cloned and adapted the core processing scripts to run exclusively on the Chennai data:
1. **`05_match_chennai.py`**: Calculated the 2D intersection between the synthetic parcels and DRDO buildings (resulting in a 100% "CONTAINED" match rate, by design).
2. **`09_detect_anomalies_chennai.py`**: Passed the buildings into the `Isolation Forest` Machine Learning model. Even though the spatial boundaries were synthetically perfect, the AI analyzed the vertical dimension!
3. **`10_fuse_chennai.py`**: The evidence fusion engine processed the AI results and generated the final 3D ULPIN ledgers.

## 6. Final Results & UI Integration
We updated `run_pipeline_chennai.py` to orchestrate this entire sequence automatically. 
We then updated `frontend_chennai/app.js` to load the newly fused data and the synthetic parcel boundaries.

**The Outcome:**
- The pipeline successfully processed all 8,611 buildings.
- The Isolation Forest AI flagged **217 buildings (2.5%) as anomalies** due to being extreme statistical outliers in height (e.g., abnormally tall skyscrapers).
- The `frontend_chennai` map now beautifully renders the 3D city with full property cards, synthetic dashed parcel lines, and traffic-light colors (Green for verified, Red for AI-flagged vertical anomalies).
