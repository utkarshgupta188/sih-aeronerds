These are excellent questions! It gets into the core of how geospatial data processing actually works under the hood.

Here is exactly how both modes work, and where the ISRO data fits into all of it:

### Where is the ISRO dataset being used?
The ISRO CartoDEM you downloaded (`cartodem_bengaluru.tif`) is actually powering the **entire** 3D map! 

During the pipeline execution:
1. The script `03_normalise_layers.py` loads your CartoDEM file, aligns it to our coordinate system, and saves it as the master surface raster.
2. The script `06_extract_elevation.py` then takes every single building footprint on the map and overlays it onto your CartoDEM. 
3. It extracts the **Ground Elevation** (e.g. `898.24 m` in your screenshot) and the **Surface Height** directly from the ISRO pixels!

### Strict Mode vs. Simulated Mode
The difference between the two modes comes down to **Resolution**. The ISRO CartoDEM is an incredible dataset, but it has a resolution of 30 meters (meaning each "pixel" of data covers a massive 30x30 meter square of land). 

Most residential buildings in Bengaluru are much smaller than 30x30 meters.

- **Strict Mode (30m Satellite):** This uses a strict mathematical rule (`all_touched=False`). It asks: *"Does this building cover the dead-center of the 30m pixel?"* If a building is too small to cover the center, the pipeline refuses to guess and drops the height data entirely. This guarantees we don't accidentally assign the height of a nearby tall tree to a small house, but it results in most small buildings showing "NO DATA".
- **Simulated Mode (1m Drone):** This uses a relaxed mathematical rule (`all_touched=True`). It asks: *"Does this building touch ANY part of the 30m pixel?"* If it touches even a corner, it grabs the ISRO height and assigns it to the building. We call it "Simulated" because we are mathematically stretching coarse 30m data to behave as if we had high-resolution 1-meter drone data, and then we simulate the floors by dividing that height by 3.5 meters!

So, in both modes, **all the height data is coming directly from your ISRO CartoDEM download**. The toggle just changes how aggressively we squeeze data out of those 30m pixels!