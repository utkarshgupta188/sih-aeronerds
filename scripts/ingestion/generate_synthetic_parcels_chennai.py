import os
import json
import geopandas as gpd

def generate_synthetic_parcels():
    print("=========================================")
    print("  PHASE 4.5: TIER C SYNTHETIC PARCELS")
    print("=========================================\n")

    bldgs_path = os.path.join("data", "processed", "drdo_chennai_buildings.geojson")
    out_path = os.path.join("data", "processed", "chennai_synthetic_parcels.geojson")
    frontend_path = os.path.join("frontend_chennai", "data", "cadastral_parcels_valid.geojson")

    if not os.path.exists(bldgs_path):
        print(f"Error: {bldgs_path} not found.")
        return

    print("Loading DRDO buildings...")
    gdf = gpd.read_file(bldgs_path)
    
    # Project to metric CRS to apply buffer
    gdf = gdf.to_crs(epsg=32644)
    
    print("Generating synthetic parcels (2m buffer)...")
    # Apply a 2m buffer to simulate a property boundary
    synthetic_geom = gdf.geometry.buffer(2)
    
    parcel_gdf = gpd.GeoDataFrame(geometry=synthetic_geom, crs=gdf.crs)
    
    # Assign IDs and required properties
    parcel_ids = []
    sources = []
    
    for i in range(len(parcel_gdf)):
        parcel_ids.append(f"synthetic_parcel_{i+1}")
        sources.append("TIER_C_SYNTHETIC_TEST_DATA")
        
    parcel_gdf["id"] = parcel_ids
    parcel_gdf["source"] = sources
    
    # Project back to EPSG:4326 for storage
    parcel_gdf = parcel_gdf.to_crs(epsg=4326)
    
    print(f"Generated {len(parcel_gdf)} synthetic parcels.")
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    parcel_gdf.to_file(out_path, driver="GeoJSON")
    print(f"Saved to {out_path}")
    
    # Also copy to frontend for the UI to render the parcel borders
    os.makedirs(os.path.dirname(frontend_path), exist_ok=True)
    parcel_gdf.to_file(frontend_path, driver="GeoJSON")
    print(f"Synced synthetic parcels to frontend at {frontend_path}")

if __name__ == "__main__":
    generate_synthetic_parcels()
