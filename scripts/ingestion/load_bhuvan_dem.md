# Manual Ingestion: Bhuvan CartoDEM

Due to authentication and captcha requirements on the Bhuvan NRSC portal, automated downloads are not supported. Follow these steps to manually ingest the DEM for the target AOI.

## Target AOI (2 sq km, Bengaluru Urban)
- **South**: 12.92365
- **North**: 12.93635
- **West**: 77.61365
- **East**: 77.62635

## Instructions
1. Go to the [Bhuvan NRSC Data Download Portal](https://bhuvan-app3.nrsc.gov.in/data/download/index.php).
2. Log in to your Bhuvan account.
3. In the left panel, select **CartoDEM Version-3R**.
4. Use the "Bounding Box" selection tool on the map or input the coordinates above.
5. Search and download the intersecting GeoTIFF tiles.
6. Extract the `.zip` file if necessary.
7. Place the resulting `*_dem.tif` file into `g:\Projects\BoundaryLens\data\raw\` and rename it to `bhuvan_cartodem.tif`.
