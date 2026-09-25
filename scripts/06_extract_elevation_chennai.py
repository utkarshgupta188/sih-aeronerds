import os
import sys
import json
import numpy as np

# Resolve absolute path to the project root directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.config_loader import get_active_config

def generate_report(stats, output_path):
    """Generates the Phase 6 Elevation Extraction markdown report."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    total = stats.get('total', 0)
    extracted = stats.get('extracted', 0)
    defaults = stats.get('defaults', 0)
    
    report_content = f"""# Phase 6: Vertical Elevation Extraction Report

## Summary
- **Total Buildings Processed**: {total}
- **Valid Ground Elevations Extracted**: {extracted}
- **Default Ground Elevation (0.0m)**: {defaults}

## Execution Details
Elevation extraction processed raster values using `shapely` spatial masks on local elevation data.
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"Report generated at {output_path}")

def load_geojson(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("=========================================")
    print("  PHASE 6: VERTICAL DATA EXTRACTION (3D) ")
    print("=========================================\n")

    config = get_active_config()
    region_prefix = config.get("region_name", "bengaluru").lower().replace(" ", "_")

    # Resolve paths dynamically based on active configuration
    bldgs_path = os.path.join(PROJECT_ROOT, "data", "processed", "buildings_linked_2d.geojson")
    if not os.path.exists(bldgs_path):
        bldgs_path = os.path.join(PROJECT_ROOT, "data", "processed", f"{region_prefix}_buildings_linked_2d.geojson")

    dem_path = os.path.join(PROJECT_ROOT, "data", "interim", "dem_aligned.tif")
    if not os.path.exists(dem_path):
        dem_path = os.path.join(PROJECT_ROOT, "data", "raw", "bare_earth_dem.tif")

    if not os.path.exists(bldgs_path) or not os.path.exists(dem_path):
        print(f"Error: Missing required files ({bldgs_path} or {dem_path}). Ensure Phase 3 normalized rasters exist.")
        sys.exit(1)

    try:
        from shapely.geometry import shape
        import rasterio
        from rasterio.mask import mask
    except ImportError:
        print("Error: Required geospatial libraries (shapely, rasterio) missing.")
        sys.exit(1)

    bldgs_data = load_geojson(bldgs_path)
    total_bldgs = len(bldgs_data.get('features', []))
    print(f"Loaded {total_bldgs} buildings. Processing ground elevation from raster...")

    extracted_count = 0
    default_count = 0

    with rasterio.open(dem_path) as dem_src:
        for b in bldgs_data.get("features", []):
            try:
                geom = shape(b["geometry"])
                dem_image, _ = mask(dem_src, [geom], crop=True, filled=True, all_touched=True)
                
                # Check for valid raster values
                if dem_src.nodata is not None:
                    valid_dem = dem_image[(dem_image != dem_src.nodata) & (~np.isnan(dem_image))]
                else:
                    valid_dem = dem_image[~np.isnan(dem_image)]
                
                if len(valid_dem) > 0:
                    b["properties"]["ground_elevation_m"] = round(float(np.median(valid_dem)), 2)
                    extracted_count += 1
                else:
                    b["properties"]["ground_elevation_m"] = 0.0
                    default_count += 1
            except Exception:
                b["properties"]["ground_elevation_m"] = 0.0
                default_count += 1

            # Ensure baseline height calculation is populated for MapLibre 3D rendering
            levels = b["properties"].get("building_levels") or 1
            b["properties"]["building_height_m"] = b["properties"].get("height_m") or round(float(levels * 3.5), 2)

    # Save processed 3D features output
    out_bldgs_path = os.path.join(PROJECT_ROOT, "data", "processed", "buildings_3d.geojson")
    os.makedirs(os.path.dirname(out_bldgs_path), exist_ok=True)
    with open(out_bldgs_path, "w", encoding="utf-8") as f:
        json.dump(bldgs_data, f, indent=2)

    stats = {
        "total": total_bldgs,
        "extracted": extracted_count,
        "defaults": default_count
    }

    print(f"\n3D Extraction complete. Valid Ground Elevations: {extracted_count}")
    report_file = os.path.join(PROJECT_ROOT, "docs", "ELEVATION_REPORT.md")
    generate_report(stats, report_file)

if __name__ == "__main__":
    main()