import os
import requests
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_active_config

def load_copernicus_dem():
    config = get_active_config()
    print(f"Downloading Copernicus DSM for {config['region_name']}...")
    
    url = config["datasets"]["elevation"]["url"]
    out_path = os.path.join("data", "raw", "copernicus_dem_glo30.tif")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    if os.path.exists(out_path):
        print(f"File {out_path} already exists. Skipping download.")
        return
    
    if not url or url == "local":
        print(f"Elevation DSM source is set to {url}. Skipping download (using local file).")
        return
    
    try:
        print(f"Fetching from {url}...")
        r = requests.get(url, stream=True, timeout=30)
        
        # If the specific COG name varies, we fallback to AWS STAC or public HTTPS download
        if r.status_code != 200:
            print(f"Direct download returned status code {r.status_code}. Trying OpenTopography / alternative public mirror...")
            url = "https://prs-dem-open.s3.amazonaws.com/GLO-30/Copernicus_DSM_COG_10_N12_00_E077_00_DEM.tif"
            r = requests.get(url, stream=True, timeout=30)
            
        r.raise_for_status()
        
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"Successfully downloaded Copernicus DSM to {out_path}")
        
    except Exception as e:
        print(f"Failed to download Copernicus DSM automatically: {e}")
        print("Alternative: You can download NASADEM / SRTM 30m or Copernicus DEM via OpenTopography freely.")

if __name__ == "__main__":
    load_copernicus_dem()
