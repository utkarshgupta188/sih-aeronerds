# Data source registry

Use the official/primary pages below as starting points. Access conditions and licences must be checked at implementation time.

## SIH
SIH26011 problem statement:
https://www.sih.gov.in/sih2026PS

## Bhu-Naksha
Official portal:
https://bhunaksha.nic.in/bhunaksha/

User guide:
https://bhunaksha.nic.in/bhunaksha/userguide.jsp

Implementation status:
https://bhunaksha.nic.in/bhunaksha/implementationstatus.jsp

## Local bare-earth DEM (reproducible / hackathon execution)

For reproducible local execution, BoundaryLens supports a **local bare-earth DEM
GeoTIFF** at:

```text
data/raw/dem/bare_earth_dem.tif
```

This avoids requiring an OpenTopography API key. `scripts/ingestion/load_bare_earth_dem.py`
checks this path first:

- **If the file exists** it is validated (readable by rasterio, has a band, has a
  CRS, non-empty, resolution present) and must **overlap the existing Bengaluru
  AOI** — West `77.61365`, South `12.92365`, East `77.62635`, North `12.93635`.
  On success it is staged to `data/raw/bare_earth_dem.tif` (the path every later
  phase already uses) and **OpenTopography is not contacted**. Provenance is
  written to `data/manifests/bare_earth_dem_local_manifest.json` with
  `dem_source = LOCAL_BARE_EARTH_DEM`.
- **If the DEM does not overlap the AOI**, ingestion fails with a clear "wrong
  geographic dataset" error (it is not silently used).
- **If the file is missing**, the exact expected path is printed and the existing
  OpenTopography download mechanism is used as a fallback.

The local bare-earth DEM is the **terrain / ground reference** only. It does not
replace the Copernicus GLO-30 surface elevation or the NDVI vegetation-evidence
layer — these remain separate evidence sources. The dataset is not treated as
authoritative unless its own source establishes that.

## Bhuvan / NRSC
Free data download help:
https://bhuvan-app3.nrsc.gov.in/data/download/help/source/html/steps_to_download_data.htm

Bhuvan store:
https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore.php

Bhuvan data portal:
https://bhuvan-app3.nrsc.gov.in/data/download/index.php

## NAKSHA
Official portal:
https://naksha.dolr.gov.in/NakshaPortal/

NAKSHA / Survey of India SOP:
https://surveyofindia.gov.in/UserFiles/files/NAKSHA%20SOP%20_NAKSHA.pdf

## OpenStreetMap
https://www.openstreetmap.org/

OSM building:levels documentation:
https://wiki.openstreetmap.org/wiki/Key:building:levels

Use Overpass API/Overpass Turbo for bounded extraction:
https://overpass-turbo.eu/

## Microsoft Global ML Building Footprints
https://github.com/microsoft/GlobalMLBuildingFootprints

The dataset includes worldwide building footprints and, in some regions, height estimates. Verify current India coverage and exact available attributes for the chosen AOI before relying on them.

## Google Open Buildings
Use the official Google Research/Open Buildings distribution and licensing documentation available for the current dataset version. Do not assume floor count is present merely because a building footprint exists.

## Map rendering
MapLibre GL JS:
https://maplibre.org/

Use OpenStreetMap data with proper attribution and an appropriate tile provider. Do not overload public OSM tile servers.

## Data.gov.in
https://www.data.gov.in/

Search for:
- Pune property data
- urban development
- PMRDA
- building/property datasets
- land records where legally downloadable
