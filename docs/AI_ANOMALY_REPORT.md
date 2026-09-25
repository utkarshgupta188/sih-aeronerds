# Phase 9: AI Anomaly Detection Report (Isolation Forest)

This report details the unsupervised Machine Learning analysis conducted on the 2,734 3D building entities in Bengaluru Urban, strictly following **Project Rule 5** (*AI assists; it does not adjudicate legal rights*).

## 1. Model Configuration
- **Algorithm**: `sklearn.ensemble.IsolationForest`
- **Contamination Parameter**: `0.03` (Top 3% spatial/vertical outliers)
- **Feature Matrix Inputs**:
  1. `parcel_overlap_ratio` (2D Spatial Boundary Intersection)
  2. `building_height_m` (Satellite Height)
  3. `ground_elevation_m` (Copernicus DEM Terrain)
  4. `derived_floors` (Multi-Storey Count)

## 2. Detection Results
- **Total Buildings Evaluated**: 2734
- **Normal Inliers**: 2652
- **AI Anomaly Flags Raised**: 82 (3.00%)

## 3. Sample Flagged Spatial/Vertical Conflicts
| Building ID | Linked Parcel | 2D Match Status | Height | Overlap | AI Anomaly Score |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `osm_way_130829155` | `cadastral_parcel_22068` | `CONTAINED` | 7.0m | 1.0 | `-0.0363` |
| `osm_way_147860505` | `cadastral_parcel_22459` | `BOUNDARY_OVERLAP` | 10.5m | 0.4699 | `-0.0308` |
| `osm_way_345860231` | `cadastral_parcel_22433` | `MAJORITY` | 10.5m | 0.5138 | `-0.0031` |
| `osm_way_347151412` | `cadastral_parcel_22254` | `MAJORITY` | 10.5m | 0.5313 | `-0.0051` |
| `osm_way_347187488` | `cadastral_parcel_22276` | `BOUNDARY_OVERLAP` | 10.5m | 0.4572 | `-0.0205` |
| `osm_way_347187503` | `cadastral_parcel_22072` | `MAJORITY` | 7.0m | 0.5432 | `-0.0448` |
| `osm_way_347187505` | `cadastral_parcel_22074` | `MAJORITY` | 14.0m | 0.5109 | `-0.0061` |
| `osm_way_347187537` | `cadastral_parcel_22072` | `BOUNDARY_OVERLAP` | 14.0m | 0.49 | `-0.0082` |
| `osm_way_347187611` | `cadastral_parcel_22068` | `MAJORITY` | 7.0m | 0.745 | `-0.0671` |
| `osm_way_347187629` | `cadastral_parcel_22061` | `MAJORITY` | 10.5m | 0.5121 | `-0.0051` |

**Output File**: `data/processed/buildings_ai_analyzed.geojson`
