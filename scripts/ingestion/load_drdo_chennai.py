import os
import geopandas as gpd

def load_drdo_data():
    raw_path = "data/drdo/raw/chennai_test1.shp"
    out_dir = "data/processed"
    out_path = os.path.join(out_dir, "drdo_chennai_buildings.geojson")

    print(f"Loading DRDO raw dataset: {raw_path}")
    
    if not os.path.exists(raw_path):
        print(f"[ERROR] DRDO dataset not found at {raw_path}")
        return

    gdf = gpd.read_file(raw_path)
    
    print(f"Original CRS: {gdf.crs}")
    if gdf.crs is None:
        print("Warning: CRS is None. Assuming EPSG:32644 (UTM 44N) based on Chennai location.")
        gdf.set_crs(epsg=32644, inplace=True)
    
    print("Converting to EPSG:4326 for standardization...")
    gdf = gdf.to_crs(epsg=4326)

    # Standardize column names
    if 'Z_Max' in gdf.columns:
        print(f"Found Z_Max. Min: {gdf['Z_Max'].min()}, Max: {gdf['Z_Max'].max()}")
        gdf.rename(columns={'Z_Max': 'height_m'}, inplace=True)
    elif 'AGLheight' in gdf.columns:
        print(f"Found AGLheight. Min: {gdf['AGLheight'].min()}, Max: {gdf['AGLheight'].max()}")
        gdf.rename(columns={'AGLheight': 'height_m'}, inplace=True)
        
    # Add building IDs, source, and estimate floors
    bldg_ids = []
    for i in range(len(gdf)):
        bldg_ids.append(f"drdo_bldg_{i+1}")
    gdf["id"] = bldg_ids
    gdf["source"] = "DRDO LiDAR (Tier B)"
    gdf["height_source"] = "DRDO LiDAR (Tier B)"
    
    # Calculate derived floors (approx 3.5m per floor) and mark as unverified
    import numpy as np
    gdf["derived_floors"] = np.maximum(1, np.round(gdf["height_m"] / 3.5)).astype(int)
    gdf["floor_count_status"] = "UNVERIFIED_ESTIMATE"

    os.makedirs(out_dir, exist_ok=True)
    
    print(f"Saving processed DRDO data to {out_path}...")
    gdf.to_file(out_path, driver='GeoJSON')
    print("Done processing DRDO Chennai dataset.")

if __name__ == "__main__":
    load_drdo_data()
