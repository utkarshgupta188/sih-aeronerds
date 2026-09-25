# Area of Interest (AOI) Selection

**Macro Region:** Bengaluru Urban District, Karnataka, India

## Target Sub-AOI Criteria
To fulfill the SIH26011 prototype requirements efficiently, the specific working AOI within Bengaluru Urban must satisfy:
1. Overlap of Cadastral KML/KMZ data.
2. Presence of Microsoft/Google Building footprints.
3. Presence of OSM `building:levels` attributes (critical for vertical property demonstration).
4. Availability of Copernicus GLO-30 DSM.
5. Manageable computational size for a prototype (e.g., a specific block or ward, such as Koramangala, Indiranagar, or Jayanagar).

## Selected AOI
We have selected a **2 sq km bounding box** centered on Koramangala / Jayanagar intersection, a dense area with multistory buildings.

- **South**: 12.92365
- **North**: 12.93635
- **West**: 77.61365
- **East**: 77.62635

This BBox was generated using `scripts/01_select_aoi.py` and saved to `data/raw/aoi_bbox.geojson`.

## Next Steps
1. Ingest Bengaluru Urban Cadastral bounds.
2. Query OSM Overpass for `building:levels` counts across the wards.
3. Select a 1 sq km bounding box with the highest overlap.
4. Extract DEM, DSM, and Footprints specifically for that bounding box.
