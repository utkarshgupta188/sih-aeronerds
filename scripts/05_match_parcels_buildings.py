import os
import json

def load_geojson(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_report(stats, report_path):
    content = f"""# Phase 5: Parcel/Building 2D Matching Report

This report summarizes the deterministic 2D topological linkage between OpenCity cadastral parcels and OSM building footprints within the 2 sq km Bengaluru Urban AOI.

## Matching Rules Applied
Geometries were projected to the region's configured processing CRS for highly accurate metric area intersection calculations.
- **CONTAINED**: Building footprint is >95% inside a single parcel.
- **MAJORITY**: Building footprint is 50%-95% inside a single parcel.
- **BOUNDARY_OVERLAP (CONFLICT)**: Building footprint intersects a parcel, but <50% of its area is inside it (likely crossing a boundary). Marked for human verification.
- **NO_PARCEL**: Building footprint falls entirely outside any known cadastral parcel.

---

## Results Summary

- **Total Buildings Analyzed**: {stats['total_buildings']}
- **Total Parcels Available**: {stats['total_parcels']}

### Linkage Distribution

| Match Status | Count | Percentage |
| :--- | :--- | :--- |
| **CONTAINED** | {stats['CONTAINED']} | {(stats['CONTAINED'] / stats['total_buildings']) * 100:.1f}% |
| **MAJORITY** | {stats['MAJORITY']} | {(stats['MAJORITY'] / stats['total_buildings']) * 100:.1f}% |
| **BOUNDARY_OVERLAP** | {stats['BOUNDARY_OVERLAP']} | {(stats['BOUNDARY_OVERLAP'] / stats['total_buildings']) * 100:.1f}% |
| **NO_PARCEL** | {stats['NO_PARCEL']} | {(stats['NO_PARCEL'] / stats['total_buildings']) * 100:.1f}% |

**Output File**: `data/processed/buildings_linked_2d.geojson`
"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\nAudit Report generated at {report_path}")


def main():
    print("=========================================")
    print("  PHASE 5: PARCEL/BUILDING MATCHING (2D) ")
    print("=========================================\n")
    
    try:
        from shapely.geometry import shape, Polygon
        from shapely.ops import transform
        import pyproj
    except ImportError:
        print("Error: Required libraries (shapely, pyproj) are missing.")
        print("Please run: pip install shapely pyproj")
        return

    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from config.config_loader import get_active_config
    config = get_active_config()
    CRS_SOURCE = config.get("crs_source", "EPSG:4326")
    CRS_PROCESSING = config.get("crs_processing", "EPSG:32643")

    bldgs_path = os.path.join("data", "processed", "osm_buildings_valid.geojson")
    parcels_path = os.path.join("data", "processed", "cadastral_parcels_valid.geojson")
    out_path = os.path.join("data", "processed", "buildings_linked_2d.geojson")

    if not os.path.exists(bldgs_path) or not os.path.exists(parcels_path):
        print("Error: Processed GeoJSON files from Phase 4 are missing.")
        return

    bldgs_data = load_geojson(bldgs_path)
    parcels_data = load_geojson(parcels_path)

    print(f"Loaded {len(bldgs_data['features'])} buildings and {len(parcels_data['features'])} parcels.")
    print(f"Projecting geometries to {CRS_PROCESSING} for accurate metric area calculation...")

    # Setup projector
    project_to_utm = pyproj.Transformer.from_crs(CRS_SOURCE, CRS_PROCESSING, always_xy=True).transform

    # Pre-process parcels
    parcel_shapes = []
    for p in parcels_data["features"]:
        geom = shape(p["geometry"])
        utm_geom = transform(project_to_utm, geom)
        parcel_shapes.append({
            "id": p["properties"]["id"],
            "utm_geom": utm_geom,
            "bounds": utm_geom.bounds
        })

    stats = {
        "total_buildings": len(bldgs_data['features']),
        "total_parcels": len(parcels_data['features']),
        "CONTAINED": 0,
        "MAJORITY": 0,
        "BOUNDARY_OVERLAP": 0,
        "NO_PARCEL": 0
    }

    print("Computing deterministic spatial intersections...")
    
    for b in bldgs_data["features"]:
        b_geom = shape(b["geometry"])
        b_utm = transform(project_to_utm, b_geom)
        b_bounds = b_utm.bounds
        b_area = b_utm.area
        
        best_parcel = None
        max_overlap_area = 0.0
        
        # BBox filter then exact intersection
        for p in parcel_shapes:
            pb = p["bounds"]
            # Check bounding box intersection first for speed
            if not (b_bounds[2] < pb[0] or b_bounds[0] > pb[2] or b_bounds[3] < pb[1] or b_bounds[1] > pb[3]):
                if b_utm.intersects(p["utm_geom"]):
                    intersection_area = b_utm.intersection(p["utm_geom"]).area
                    if intersection_area > max_overlap_area:
                        max_overlap_area = intersection_area
                        best_parcel = p["id"]
        
        props = b["properties"]
        if best_parcel and b_area > 0:
            overlap_ratio = max_overlap_area / b_area
            props["linked_parcel_id"] = best_parcel
            props["parcel_overlap_ratio"] = round(overlap_ratio, 4)
            
            if overlap_ratio >= 0.95:
                status = "CONTAINED"
            elif overlap_ratio >= 0.50:
                status = "MAJORITY"
            else:
                status = "BOUNDARY_OVERLAP"
        else:
            props["linked_parcel_id"] = None
            props["parcel_overlap_ratio"] = 0.0
            status = "NO_PARCEL"

        props["match_status_2d"] = status
        stats[status] += 1

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bldgs_data, f, indent=2)

    print(f"\nMatching complete. Processed file saved to {out_path}")
    print(f"Stats: CONTAINED ({stats['CONTAINED']}), MAJORITY ({stats['MAJORITY']}), "
          f"BOUNDARY_OVERLAP ({stats['BOUNDARY_OVERLAP']}), NO_PARCEL ({stats['NO_PARCEL']})")

    report_path = os.path.join("docs", "MATCHING_REPORT_2D.md")
    generate_report(stats, report_path)

if __name__ == "__main__":
    main()
