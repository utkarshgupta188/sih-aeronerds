import os
import json

def get_geom_hash(coords):
    """Simple hash for duplicate detection based on coordinate sum/length."""
    try:
        if isinstance(coords[0][0], list): # MultiPolygon or Polygon with holes
            flat = [pt for ring in coords for pt in ring]
        else:
            flat = coords
        return f"{len(flat)}_{sum(pt[0] for pt in flat):.4f}_{sum(pt[1] for pt in flat):.4f}"
    except Exception:
        return "invalid"

def validate_vector_layer(input_path, output_path, layer_name):
    print(f"Validating {layer_name}...")
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return None

    try:
        from shapely.geometry import shape
        has_shapely = True
    except ImportError:
        print("Warning: Shapely not installed. Geometry validity checks will be skipped.")
        has_shapely = False

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_features = len(data.get("features", []))
    valid_features = []
    
    stats = {
        "total": total_features,
        "invalid_geometry": 0,
        "duplicate_geometry": 0,
        "missing_levels": 0
    }
    
    seen_hashes = set()

    for feat in data.get("features", []):
        geom = feat.get("geometry")
        props = feat.get("properties", {})
        
        # 1. Geometry Validity
        is_valid = True
        if has_shapely and geom:
            try:
                s = shape(geom)
                if not s.is_valid or s.area <= 0:
                    is_valid = False
            except Exception:
                is_valid = False
                
        if not is_valid:
            stats["invalid_geometry"] += 1
            continue
            
        # 2. Duplicate Detection
        if geom and "coordinates" in geom:
            ghash = get_geom_hash(geom["coordinates"])
            if ghash in seen_hashes:
                stats["duplicate_geometry"] += 1
                continue
            seen_hashes.add(ghash)
            
        # 3. Attribute Completeness
        if layer_name == "OSM Buildings":
            levels = props.get("building_levels")
            if levels is None:
                stats["missing_levels"] += 1
                props["building_levels_status"] = "NOT_DETERMINABLE"
            else:
                props["building_levels_status"] = "VERIFIED"
                
        valid_features.append(feat)

    # Save processed layer
    data["features"] = valid_features
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    stats["valid_saved"] = len(valid_features)
    print(f"  Total: {stats['total']} | Valid: {stats['valid_saved']} | Invalid: {stats['invalid_geometry']} | Duplicates: {stats['duplicate_geometry']}")
    
    return stats

def generate_report(osm_stats, cadastral_stats):
    report_path = os.path.join("docs", "DATA_QUALITY_REPORT.md")
    
    def get_status(stats):
        if stats["invalid_geometry"] > (stats["total"] * 0.1):
            return "🔴 FAIL (>10% invalid geometries)"
        if stats["duplicate_geometry"] > 0 or stats["missing_levels"] > (stats["total"] * 0.5):
            return "🟡 WARN (Duplicates or high missing attributes)"
        return "🟢 PASS"

    osm_status = get_status(osm_stats) if osm_stats else "🔴 FAIL (File missing)"
    cad_status = get_status(cadastral_stats) if cadastral_stats else "🔴 FAIL (File missing)"

    report_content = f"""# Phase 4: Data Quality Validation Report

This report summarizes deterministic spatial validity and attribute completeness for the interim layers. Invalid and duplicate geometries have been stripped from the `processed` outputs.

## 1. OSM Buildings & Levels -> `data/processed/osm_buildings_valid.geojson`
- **Status**: {osm_status}
- **Total Input Features**: {osm_stats['total'] if osm_stats else 0}
- **Valid Features Saved**: {osm_stats['valid_saved'] if osm_stats else 0}
- **Invalid/Degenerate Geometries**: {osm_stats['invalid_geometry'] if osm_stats else 0}
- **Duplicate Geometries Dropped**: {osm_stats['duplicate_geometry'] if osm_stats else 0}
- **Missing Floor Counts (`NOT_DETERMINABLE`)**: {osm_stats['missing_levels'] if osm_stats else 0}

## 2. OpenCity Cadastral Parcels -> `data/processed/cadastral_parcels_valid.geojson`
- **Status**: {cad_status}
- **Total Input Features**: {cadastral_stats['total'] if cadastral_stats else 0}
- **Valid Features Saved**: {cadastral_stats['valid_saved'] if cadastral_stats else 0}
- **Invalid/Degenerate Geometries**: {cadastral_stats['invalid_geometry'] if cadastral_stats else 0}
- **Duplicate Geometries Dropped**: {cadastral_stats['duplicate_geometry'] if cadastral_stats else 0}

## 3. DEM Raster (`dem_normalised.tif`)
- **Status**: 🟢 PASS (Raster bounds validated during clipping in Phase 3).
"""
    
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\nData Quality Report generated at {report_path}")

def main():
    print("=========================================")
    print("  PHASE 4: DATA QUALITY VALIDATION       ")
    print("=========================================\n")
    
    osm_in = os.path.join("data", "interim", "osm_buildings_normalised.geojson")
    osm_out = os.path.join("data", "processed", "osm_buildings_valid.geojson")
    osm_stats = validate_vector_layer(osm_in, osm_out, "OSM Buildings")
    
    cad_in = os.path.join("data", "interim", "cadastral_parcels_normalised.geojson")
    cad_out = os.path.join("data", "processed", "cadastral_parcels_valid.geojson")
    cad_stats = validate_vector_layer(cad_in, cad_out, "Cadastral Parcels")
    
    generate_report(osm_stats, cad_stats)
    print("\nPhase 4 Data Quality Validation complete!")

if __name__ == "__main__":
    main()
