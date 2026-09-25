# BoundaryLens technical and data strategy

## Prototype geography
Use **Baramati ULB, Pune district, Maharashtra** as the default pilot AOI, not an entire city/district. The reason is practical: it appears in published NAKSHA pilot material, while Pune district has government-reported cadastral-map digitisation progress.

This is a prototype choice, not a claim that Baramati has every required layer openly downloadable.

## Data tiers

### Tier A — core public/accessible
1. Cadastral/parcel geometry:
   - Bhu-Naksha / state cadastral source where the selected AOI is publicly viewable/exportable.
2. Terrain:
   - Bhuvan CartoDEM / DEM.
3. Building footprints:
   - Microsoft Global ML Building Footprints.
   - Google Open Buildings where coverage/licence permits.
   - OpenStreetMap.
4. Floor/height attributes:
   - OSM `building:levels` and `height` where present.
5. Basemap:
   - OpenStreetMap data + MapLibre.

### Tier B — authoritative if legitimately obtainable
- NAKSHA aerial/oblique/LiDAR/ground-truth products.
- State/ULB building-permission or property datasets.
- Approved floor plans/BIM.
- GNSS/CORS survey observations.
- Authoritative DSM/point clouds.

### Tier C — synthetic test fixtures
Only for testing missing interfaces. Every record must be labelled SYNTHETIC.

## Important limitation
Do not tell judges that Bhuvan CartoDEM is a city-scale DSM. Bhuvan's public store clearly lists CartoDEM products as DEM products. If a true DSM/point cloud is unavailable, the pipeline must support it as an optional input and demonstrate the interface with a small permitted sample or synthetic test fixture, explicitly labelled.

## Data fusion
Fuse by preserving each source separately first:
source geometry/attributes
→ normalise CRS/schema
→ spatial matching
→ evidence table
→ conflict detection
→ derived representation.

Never merge sources by overwriting fields.

## Main output
A 3D parcel/building/floor representation with:
- geometry
- source provenance
- evidence status
- confidence
- conflict flags
- proposed vertical linkage
- human-verification state.

## Main demo
Select one parcel/building and show:
1. parcel
2. building footprint
3. elevation evidence
4. floor evidence
5. 3D volume
6. source agreement/conflict
7. topology validation
8. confidence/provenance
9. human verification
10. proposed vertical linkage
