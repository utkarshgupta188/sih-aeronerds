import json
import os
import sys

# Ensure config module can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_active_config

def main():
    config = get_active_config()
    lon_min, lat_min, lon_max, lat_max = config["bbox"]
    region_name = config["region_name"]

    bbox_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": f"{region_name} AOI"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [lon_min, lat_min],
                        [lon_max, lat_min],
                        [lon_max, lat_max],
                        [lon_min, lat_max],
                        [lon_min, lat_min]
                    ]]
                }
            }
        ]
    }

    out_dir = os.path.join("data", "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "aoi_bbox.geojson")
    with open(out_path, "w") as f:
        json.dump(bbox_geojson, f, indent=2)
    
    print(f"Generated AOI bounding box for {region_name} at {out_path}")
    print(f"BBox (South, North, West, East): {lat_min}, {lat_max}, {lon_min}, {lon_max}")

if __name__ == "__main__":
    main()
