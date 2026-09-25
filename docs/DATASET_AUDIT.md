# Phase 1: Dataset Discovery Audit

**Target Area of Interest (AOI):** Bengaluru Urban District, Karnataka, India

## 1. Cadastral Parcel Data
- **Name**: Bengaluru Cadastral Maps
- **Source**: KSRSAC / Bangalore Development Authority ecosystem via OpenCity
- **Official URL**: https://data.opencity.in/dataset/bengaluru-cadastral-maps
- **Download URL**: https://data.opencity.in/dataset/b5d91825-a104-41c8-bf93-3aedcfd58124/resource/3975e8d0-9a23-4b4b-a3c9-9453979406e4/download/038b4a89-98c8-49f7-aa1a-b3d073745d0b.kmz
- **Format**: KMZ / KML
- **CRS**: EPSG:4326 (implied by KML)
- **Spatial Coverage**: Bengaluru Urban District
- **Licence**: Public Domain
- **Free to Download?**: YES
- **Authentication Required?**: NO
- **Payment Required?**: NO
- **Government-only?**: NO

## 2. DEM (Digital Elevation Model)
- **Name**: Copernicus DEM GLO-30 (AWS Open Data)
- **Source**: AWS Open Data Registry (`s3://copernicus-dem-30m`)
- **Official URL**: https://registry.opendata.aws/copernicus-dem/
- **Format**: GeoTIFF
- **Licence**: Free and open (Public)
- **Free to Download?**: YES
- **Authentication Required?**: NO (Direct HTTPS / S3 anonymous access)

## 3. Height Raster (2.5D)
- **Name**: Google Open Buildings 2.5D Temporal Dataset
- **Source**: Google Earth Engine Data Catalog
- **Official URL**: https://sites.research.google/open-buildings/
- **Format**: Raster
- **Resolution**: 4m
- **Licence**: CC BY-4.0
- **Free to Download?**: YES
- **Authentication Required?**: YES (Google Account)

## 4. Building Footprints
- **Name**: Microsoft Global ML Building Footprints / Google Open Buildings V3
- **Source**: Planetary Computer / Google
- **Official URL**: https://github.com/microsoft/GlobalMLBuildingFootprints / https://sites.research.google/open-buildings/
- **Format**: GeoParquet / WKT (Google)
- **Licence**: CDLA Permissive 2.0 / CC BY-4.0
- **Free to Download?**: YES
- **Authentication Required?**: NO

## 5. OSM Building Data & Floor Evidence
- **Name**: OpenStreetMap
- **Source**: Overpass API / Geofabrik
- **Official URL**: https://overpass-turbo.eu/
- **Format**: GeoJSON / OSM XML
- **Attributes**: `building`, `building:levels`, `height`
- **Licence**: ODbL
- **Free to Download?**: YES
- **Authentication Required?**: NO

## 6. AOI Boundary
- **Name**: Nominatim Geocoder Boundary
- **Source**: OpenStreetMap / Nominatim
- **Download URL**: https://nominatim.openstreetmap.org/search?q=Bengaluru+Urban+District,+Karnataka&format=json&polygon_geojson=1
- **Free to Download?**: YES

---

# AUDIT STATUS: PASS

All minimum dataset requirements have been successfully verified as freely downloadable and accessible. We can proceed to choose a specific sub-AOI within Bengaluru Urban and begin Phase 2 (Ingestion).
