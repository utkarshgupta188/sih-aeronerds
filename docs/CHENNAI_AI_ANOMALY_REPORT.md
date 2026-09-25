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
- **Total Buildings Evaluated**: 8611
- **Normal Inliers**: 8354
- **AI Anomaly Flags Raised**: 257 (2.98%)

## 3. Sample Flagged Spatial/Vertical Conflicts
| Building ID | Linked Parcel | 2D Match Status | Height | Overlap | AI Anomaly Score |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `drdo_bldg_4` | `synthetic_parcel_4` | `CONTAINED` | 15.0m | 1.0 | `-0.0124` |
| `drdo_bldg_16` | `synthetic_parcel_16` | `CONTAINED` | 3.0m | 1.0 | `-0.0324` |
| `drdo_bldg_18` | `synthetic_parcel_18` | `CONTAINED` | 9.0m | 1.0 | `-0.0144` |
| `drdo_bldg_74` | `synthetic_parcel_74` | `CONTAINED` | 12.0m | 1.0 | `-0.0634` |
| `drdo_bldg_76` | `synthetic_parcel_76` | `CONTAINED` | 6.0m | 1.0 | `-0.0027` |
| `drdo_bldg_84` | `synthetic_parcel_84` | `CONTAINED` | 8.0m | 1.0 | `-0.0148` |
| `drdo_bldg_90` | `synthetic_parcel_90` | `CONTAINED` | 9.0m | 1.0 | `-0.0014` |
| `drdo_bldg_93` | `synthetic_parcel_93` | `CONTAINED` | 17.0m | 1.0 | `-0.0509` |
| `drdo_bldg_102` | `synthetic_parcel_102` | `CONTAINED` | 10.0m | 1.0 | `-0.0416` |
| `drdo_bldg_121` | `synthetic_parcel_121` | `CONTAINED` | 9.0m | 1.0 | `-0.0255` |

**Output File**: `data/processed/buildings_ai_analyzed.geojson`
