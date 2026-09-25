import os
import rasterio
import json

def check_raster(name, path):
    if not os.path.exists(path):
        print(f"{name} loaded: NO (File missing at {path})")
        return None
        
    try:
        with rasterio.open(path) as src:
            print(f"{name} loaded: YES")
            print(f"{name} CRS: {src.crs}")
            print(f"{name} resolution: {src.res}")
            print(f"{name} bounds: {src.bounds}")
            return src.meta
    except Exception as e:
        print(f"{name} loaded: FAILED ({e})")
        return None

def main():
    print("=========================================")
    print("  ELEVATION PIPELINE DIAGNOSTICS         ")
    print("=========================================\n")
    
    dsm_meta = check_raster("DSM", os.path.join("data", "interim", "dsm_aligned.tif"))
    print("-" * 40)
    dem_meta = check_raster("DEM", os.path.join("data", "interim", "dem_aligned.tif"))
    print("-" * 40)
    norm_meta = check_raster("Height raster", os.path.join("data", "processed", "elevation", "normalized_height.tif"))
    print("-" * 40)
    
    if dsm_meta and dem_meta:
        aligned = (dsm_meta['crs'] == dem_meta['crs']) and (dsm_meta['transform'] == dem_meta['transform']) and (dsm_meta['width'] == dem_meta['width'])
        print(f"Aligned grid: {'YES' if aligned else 'NO'}")
    else:
        print("Aligned grid: NO (Missing inputs)")

    bldgs_path = os.path.join("data", "processed", "buildings_3d.geojson")
    if os.path.exists(bldgs_path):
        with open(bldgs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            total = len(data["features"])
            with_height = sum(1 for b in data["features"] if b["properties"].get("dsm_derived_height_m") is not None)
            print(f"\nBuilding overlap: YES")
            print(f"Buildings processed: {total}")
            print(f"Buildings with valid height: {with_height}")
            print(f"Buildings without height: {total - with_height}")
    else:
        print(f"\nBuilding overlap: NO (Missing {bldgs_path})")

if __name__ == "__main__":
    main()
