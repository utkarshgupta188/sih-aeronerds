# Phase 6: Vertical Elevation Report

This report summarizes the 3D elevation parameters extracted for the SIH26011 prototype.
As per Project Rule 4, strict adherence to determinism is enforced. Guesswork for building heights is strictly avoided.

## 1. Ground Elevation (Z-axis)
- **Source**: Copernicus DEM GLO-30 (`data/raw/copernicus_dem_glo30.tif`)
- **Total Features Sampled**: 2734
- **Average Ground Elevation**: 896.60 m
- **Min Ground Elevation**: 885.48 m
- **Max Ground Elevation**: 917.52 m

## 2. Above-Ground Height
- **Source**: OSM `building_levels` (Estimated as levels * 3.5m)
- **Status**:
  - `VERIFIED` (Explicit floor count available): 0
  - `NOT_DETERMINABLE` (No explicit floor count): 2734

> **Note on 3D Visualisation**: Because only 0 buildings have verified height data, the resulting 3D UI will mostly display base footprints at their correct ground elevation without vertical extrusion, strictly complying with the rule against fabricated data.

**Output File**: `data/processed/buildings_3d.geojson`
