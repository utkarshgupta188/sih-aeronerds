
The reason so few buildings have a derived 3D height is due to the **resolution of the free satellite data** combined with a strict mathematical rule we are using.

### The Problem: 30-Meter Pixels vs. Small Buildings
The Copernicus DSM and SRTM DEM both have a resolution of **30 meters per pixel**. That means one single pixel of height data covers an area of **900 square meters**. 

By default, the geospatial library we are using (`rasterio`) only counts a pixel if the building footprint covers the **dead-center** of that 30x30m square. 
Since most residential buildings in Bengaluru are much smaller than 30x30m, their footprints often fall between the pixel centers. The script sees "0 valid pixels" for these buildings and correctly flags them as `NOT_DETERMINABLE`.

Only the 38 largest buildings (like massive apartment complexes or commercial malls) were big enough to cover the pixel centers!

### The Solution: `all_touched=True`
We can change the extraction rule from "must cover the pixel center" to "must touch the pixel at all" (`all_touched=True`). 

If we do this:
1. Almost **all 2,700+ buildings** will suddenly get 3D heights!
2. **The Tradeoff:** For very small houses, the height might be less accurate because that 30m pixel might also be measuring a large tree next to the house, or the street.

In a real production environment, the government would use 1-meter resolution drone data to solve this. But for a hackathon prototype, using `all_touched=True` is the standard accepted way to force low-resolution satellite data onto high-resolution building footprints. 

Would you like me to update the pipeline to use `all_touched=True` so we can see 3D heights for the entire city block?