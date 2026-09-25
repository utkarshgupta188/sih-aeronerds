"""
Google Open Buildings 2.5D Temporal Dataset Downloader
This script requires Google Earth Engine authentication.

Before running:
1. pip install earthengine-api geemap
2. earthengine authenticate
"""

import os

try:
    import ee
    import geemap
except ImportError:
    print("Please install required packages: pip install earthengine-api geemap")
    exit(1)

def load_google_buildings():
    print("Initializing Google Earth Engine...")
    try:
        # Try initializing with default auth or prompts
        ee.Initialize()
    except Exception as e1:
        print(f"Default ee.Initialize() failed ({e1}). Attempting to initialize with high-volume API...")
        try:
            # Fallback initialization
            import google.auth
            credentials, project = google.auth.default()
            ee.Initialize(credentials, project=project)
        except Exception as e2:
            print(f"\nEarth Engine initialization failed: {e2}")
            print("\nNOTE: Earth Engine now requires a Google Cloud Project ID.")
            print("If you have a GCP project, run this script after setting your project ID in the code, or set environment variable:")
            print("  $env:GOOGLE_CLOUD_PROJECT='your-project-id'")
            return

    # AOI from 01_select_aoi.py (Bengaluru Koramangala 2sqkm box)
    lat_min, lat_max = 12.92365, 12.93635
    lon_min, lon_max = 77.61365, 77.62635
    
    aoi = ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])
    
    # 1. Google Open Buildings 2.5D Temporal Dataset (Raster)
    print("Fetching Google Open Buildings 2.5D Height Raster...")
    dataset = ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
    
    # Get the latest image (2023)
    image = dataset.filterDate('2023-01-01', '2023-12-31').first()
    
    # Select the building height band
    height_raster = image.select('building_height')
    
    out_dir = os.path.join("data", "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_raster_path = os.path.join(out_dir, "google_open_buildings_25d_height.tif")
    
    if os.path.exists(out_raster_path):
        print(f"File {out_raster_path} already exists. Skipping download.")
        return
    
    print(f"Downloading Height Raster to {out_raster_path}...")
    try:
        geemap.ee_export_image(height_raster, filename=out_raster_path, scale=4, region=aoi, file_per_band=False)
        print("Raster download complete!")
    except Exception as e:
        print(f"Failed to download raster: {e}")

if __name__ == "__main__":
    load_google_buildings()
