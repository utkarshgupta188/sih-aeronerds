# Phase 4: Data Quality Validation Report

This report summarizes deterministic spatial validity and attribute completeness for the interim layers. Invalid and duplicate geometries have been stripped from the `processed` outputs.

## 1. OSM Buildings & Levels -> `data/processed/osm_buildings_valid.geojson`
- **Status**: 🟡 WARN (Duplicates or high missing attributes)
- **Total Input Features**: 2734
- **Valid Features Saved**: 2734
- **Invalid/Degenerate Geometries**: 0
- **Duplicate Geometries Dropped**: 0
- **Missing Floor Counts (`NOT_DETERMINABLE`)**: 2718

## 2. OpenCity Cadastral Parcels -> `data/processed/cadastral_parcels_valid.geojson`
- **Status**: 🟢 PASS
- **Total Input Features**: 78
- **Valid Features Saved**: 78
- **Invalid/Degenerate Geometries**: 0
- **Duplicate Geometries Dropped**: 0

## 3. DEM Raster (`dem_normalised.tif`)
- **Status**: 🟢 PASS (Raster bounds validated during clipping in Phase 3).
