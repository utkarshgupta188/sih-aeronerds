import os
import requests
import json
import sys

# Ensure config module can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_active_config

def load_osm():
    config = get_active_config()
    print(f"Loading OSM Building Footprints for {config['region_name']}...")
    
    lon_min, lat_min, lon_max, lat_max = config["bbox"]
    bbox = f"{lat_min},{lon_min},{lat_max},{lon_max}"
    
    query = f'[out:json][timeout:25];(way["building"]({bbox});relation["building"]({bbox}););out body;>;out skel qt;'
    
    endpoints = [
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
        "https://overpass-api.de/api/interpreter"
    ]
    
    headers = {
        "User-Agent": "BoundaryLens/1.0",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    out_dir = os.path.join("data", "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "osm_data.json")
    
    if os.path.exists(out_path):
        print(f"File {out_path} already exists. Skipping download.")
        return
    
    for url in endpoints:
        try:
            print(f"Trying Overpass server: {url}...")
            # Sending raw payload via POST
            r = requests.post(url, data=f"data={query}".encode('utf-8'), headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"Successfully saved OSM data to {out_path}")
                print(f"Total elements retrieved: {len(data.get('elements', []))}")
                return
            else:
                print(f"Server {url} returned HTTP {r.status_code}")
        except Exception as e:
            print(f"Error connecting to {url}: {e}")
            
    print("All Overpass endpoints failed.")

if __name__ == "__main__":
    load_osm()
