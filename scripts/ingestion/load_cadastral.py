import os
import requests
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_active_config

def load_cadastral():
    config = get_active_config()
    print(f"Loading Cadastral Maps for {config['region_name']}...")
    
    if config["datasets"]["cadastral"]["source_name"] == "TIER_C_SYNTHETIC":
        print("Using Tier C Synthetic Data strategy for cadastral parcels.")
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), "generate_synthetic_parcels_chennai.py")
        subprocess.run([sys.executable, script_path], check=True)
        return

    url = config["datasets"]["cadastral"]["url"]
    if not url:
        print("No cadastral URL provided in config. Skipping.")
        return
    
    out_dir = os.path.join("data", "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{config['region_name'].lower().replace(' ', '_')}_cadastral.kmz")
    
    if os.path.exists(out_path):
        print(f"File {out_path} already exists. Skipping download.")
        return

    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"Successfully saved Cadastral KMZ to {out_path}")
        
    except Exception as e:
        print(f"Failed to download Cadastral data: {e}")

if __name__ == "__main__":
    load_cadastral()
