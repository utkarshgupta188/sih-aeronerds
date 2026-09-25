import os
import json

def get_active_config(region_file=None):
    if region_file is None:
        region_file = os.environ.get("BOUNDARYLENS_REGION", "bengaluru.json")
    config_path = os.path.join(os.path.dirname(__file__), "regions", region_file)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
