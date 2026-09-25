import os
import json
import zipfile
import xml.etree.ElementTree as ET

import sys

# Ensure config module can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_active_config

config = get_active_config()
LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = config["bbox"]
REGION_NAME = config["region_name"]
CRS_SOURCE = config.get("crs_source", "EPSG:4326")

def is_point_in_aoi(lon, lat):
    return LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX

def is_polygon_in_aoi(coords):
    # coords is list of [lon, lat]
    for lon, lat in coords:
        if is_point_in_aoi(lon, lat):
            return True
    return False

def normalise_osm():
    print("--- 1. Normalising OSM Building Footprints & Levels ---")
    raw_path = os.path.join("data", "raw", "osm_data.json")
    out_path = os.path.join("data", "interim", "osm_buildings_normalised.geojson")
    
    if not os.path.exists(raw_path):
        print(f"Error: Raw file {raw_path} not found.")
        return

    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Index nodes by ID
    nodes = {}
    elements = data.get("elements", [])
    for elem in elements:
        if elem.get("type") == "node":
            nodes[elem["id"]] = [elem["lon"], elem["lat"]]

    features = []
    building_count = 0
    levels_count = 0

    for elem in elements:
        if elem.get("type") == "way" and "tags" in elem:
            tags = elem["tags"]
            if "building" in tags:
                way_nodes = elem.get("nodes", [])
                coords = [nodes[node_id] for node_id in way_nodes if node_id in nodes]
                
                if len(coords) >= 3 and is_polygon_in_aoi(coords):
                    # Ensure polygon ring is closed
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    
                    levels = tags.get("building:levels")
                    height = tags.get("height")
                    
                    try:
                        levels_num = float(levels) if levels else None
                    except ValueError:
                        levels_num = None
                        
                    try:
                        height_num = float(height.replace("m", "").strip()) if height else None
                    except (ValueError, AttributeError):
                        height_num = None

                    if levels_num is not None:
                        levels_count += 1

                    feature = {
                        "type": "Feature",
                        "properties": {
                            "id": f"osm_way_{elem['id']}",
                            "source": "OpenStreetMap",
                            "building_type": tags.get("building", "yes"),
                            "name": tags.get("name"),
                            "building_levels": levels_num,
                            "height_m": height_num,
                            "crs": "EPSG:4326"
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [coords]
                        }
                    }
                    features.append(feature)
                    building_count += 1

    geojson_output = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson_output, f, indent=2)

    print(f"Normalised {building_count} building footprints inside AOI.")
    print(f"Buildings with explicit 'building:levels' tag: {levels_count}")
    print(f"Saved to {out_path}\n")

def normalise_cadastral():
    print(f"--- 2. Normalising {config['datasets']['cadastral']['source_name']} Cadastral Parcels ---")
    
    # We construct the expected file name from load_cadastral.py
    cadastral_filename = f"{REGION_NAME.lower().replace(' ', '_')}_cadastral.kmz"
    raw_path = os.path.join("data", "raw", cadastral_filename)
    
    # Fallback to the old name if the new dynamic one doesn't exist yet (for transition)
    if not os.path.exists(raw_path):
        raw_path = os.path.join("data", "raw", "bengaluru_cadastral.kmz")

    out_path = os.path.join("data", "interim", "cadastral_parcels_normalised.geojson")

    if not os.path.exists(raw_path):
        print(f"Error: Raw file {raw_path} not found.")
        return

    features = []
    parcel_count = 0

    try:
        with zipfile.ZipFile(raw_path, "r") as kmz:
            kml_files = [f for f in kmz.namelist() if f.endswith(".kml")]
            if not kml_files:
                print("No KML file found inside KMZ archive.")
                return
            
            kml_content = kmz.read(kml_files[0])
            root = ET.fromstring(kml_content)
            
            # Namespace handling for KML
            ns = {"kml": "http://www.opengis.net/kml/2.2"}

            for idx, placemark in enumerate(root.findall(".//kml:Placemark", ns)):
                name_elem = placemark.find("kml:name", ns)
                name = name_elem.text if name_elem is not None else f"parcel_{idx}"

                # Extract coordinates from Polygon outerBoundaryIs
                coord_elem = placemark.find(".//kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
                if coord_elem is None:
                    # Fallback search without namespace prefix if necessary
                    coord_elem = placemark.find(".//coordinates")

                if coord_elem is not None and coord_elem.text:
                    coord_str = coord_elem.text.strip()
                    raw_coords = coord_str.split()
                    coords = []
                    for pt in raw_coords:
                        parts = pt.split(",")
                        if len(parts) >= 2:
                            try:
                                lon, lat = float(parts[0]), float(parts[1])
                                coords.append([lon, lat])
                            except ValueError:
                                continue
                    
                    if len(coords) >= 3 and is_polygon_in_aoi(coords):
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])
                            
                        feature = {
                            "type": "Feature",
                            "properties": {
                                "id": f"cadastral_parcel_{idx}",
                                "name": name,
                                "source": "OpenCity / BDA / KSRSAC",
                                "crs": "EPSG:4326"
                            },
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [coords]
                            }
                        }
                        features.append(feature)
                        parcel_count += 1

    except Exception as e:
        print(f"Failed to parse KMZ/KML: {e}")

    geojson_output = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson_output, f, indent=2)

    print(f"Normalised & clipped {parcel_count} cadastral parcels inside AOI.")
    print(f"Saved to {out_path}\n")

def normalise_elevation_rasters():
    print("--- 3. Normalising Elevation Rasters (DSM & DEM) ---")
    
    elevation_cfg = config["datasets"].get("elevation", {})
    elevation_filename = elevation_cfg.get("filename", "copernicus_dem_glo30.tif")
    
    dsm_raw_path = os.path.join("data", "raw", elevation_filename)
    dem_raw_path = os.path.join("data", "raw", "bare_earth_dem.tif")
    
    dsm_aligned_path = os.path.join("data", "interim", "dsm_aligned.tif")
    dem_aligned_path = os.path.join("data", "interim", "dem_aligned.tif")
    
    if not os.path.exists(dsm_raw_path) or not os.path.exists(dem_raw_path):
        print(f"Error: Missing one or both raw rasters (DSM: {os.path.exists(dsm_raw_path)}, DEM: {os.path.exists(dem_raw_path)}).")
        return

    try:
        import rasterio
        import numpy as np
        from rasterio.mask import mask
        from shapely.geometry import box
        from rasterio.enums import Resampling
        from rasterio.warp import reproject
        
        aoi_polygon = [box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)]
        
        # 1. Process DSM (Master Grid)
        with rasterio.open(dsm_raw_path) as src_dsm:
            dsm_image, dsm_transform = mask(src_dsm, aoi_polygon, crop=True)
            dsm_meta = src_dsm.meta.copy()
            
            dsm_meta.update({
                "driver": "GTiff",
                "height": dsm_image.shape[1],
                "width": dsm_image.shape[2],
                "transform": dsm_transform,
                "crs": "EPSG:4326"
            })
            
            os.makedirs(os.path.dirname(dsm_aligned_path), exist_ok=True)
            with rasterio.open(dsm_aligned_path, "w", **dsm_meta) as dest_dsm:
                dest_dsm.write(dsm_image)
        
        print(f"Cropped DSM raster saved to {dsm_aligned_path}")
        
        # 2. Process DEM (Slave Grid) - Reproject & Align to match Master Grid exactly
        with rasterio.open(dem_raw_path) as src_dem:
            dem_image, dem_transform = mask(src_dem, aoi_polygon, crop=True)
            
            # Create empty array matching DSM dimensions exactly
            dem_reprojected = np.empty((1, dsm_meta['height'], dsm_meta['width']), dtype=src_dem.dtypes[0])
            
            reproject(
                source=dem_image,
                destination=dem_reprojected,
                src_transform=dem_transform,
                src_crs=src_dem.crs,
                dst_transform=dsm_meta['transform'],
                dst_crs=dsm_meta['crs'],
                resampling=Resampling.bilinear
            )
            
            with rasterio.open(dem_aligned_path, "w", **dsm_meta) as dest_dem:
                dest_dem.write(dem_reprojected)
                
        print(f"Cropped and aligned DEM raster saved to {dem_aligned_path}\n")
        
    except ImportError:
        print("rasterio package not installed. Skipping raster alignment.")

def main():
    print("=========================================")
    print("  PHASE 3: LAYER NORMALISATION PIPELINE  ")
    print("=========================================\n")
    normalise_osm()
    normalise_cadastral()
    normalise_elevation_rasters()
    print("Phase 3 Normalisation complete!")

if __name__ == "__main__":
    main()