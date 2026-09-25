# Phase 3: Normalisation Report

**Target Area of Interest:** Bengaluru Urban District (2 sq km Koramangala / Jayanagar BBox)
- **South**: 12.92365
- **North**: 12.93635
- **West**: 77.61365
- **East**: 77.62635

---

## Standardized Specifications

### 1. Coordinate Reference Systems (CRS)
- **Geographic Storage & Display CRS:** `EPSG:4326` (WGS 84, Lat/Lon degrees).
- **Projected Planar CRS:** `EPSG:32643` (UTM Zone 43N, meters) — to be used for deterministic metric area calculation, buffer calculation, 3D volume extrusion, and spatial intersection.

### 2. Normalized Data Layers in `data/interim/`

| Layer Name | Input File | Output File | Feature Geometry | Primary Attributes | CRS |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OSM Buildings & Levels** | `data/raw/osm_data.json` | `data/interim/osm_buildings_normalised.geojson` | Polygon | `id`, `source`, `building_type`, `name`, `building_levels`, `height_m` | EPSG:4326 |
| **Cadastral Parcels** | `data/raw/bengaluru_cadastral.kmz` | `data/interim/cadastral_parcels_normalised.geojson` | Polygon | `id`, `name`, `source` | EPSG:4326 |
| **Terrain Elevation (DEM)** | `data/raw/copernicus_dem_glo30.tif` | `data/interim/dem_normalised.tif` | GeoTIFF Raster | Elevation (meters above ellipsoid) | EPSG:4326 |

---

## Transformation Pipeline Summary
1. **Spatial Clipping:** All vector geometries and rasters are clipped against the exact 2 sq km AOI bounding box with 0% geometric alteration.
2. **Schema Uniformity:** Standardized property naming (`id`, `source`, `building_levels`, `height_m`).
3. **Data Provenance:** Preserved original identifiers and source attribution tags in feature properties.
