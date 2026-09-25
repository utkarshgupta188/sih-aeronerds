import os
import json
import shutil

def main():
    print("=========================================")
    print("  PHASE 8: EXTRACT FLOOR ENTITIES        ")
    print("=========================================\n")

    bldgs_path = os.path.join("data", "processed", "buildings_3d.geojson")
    out_floors_path = os.path.join("data", "processed", "floor_entities.json")
    frontend_bldgs_path = os.path.join("frontend", "data", "buildings_3d.geojson")
    report_path = os.path.join("docs", "FLOOR_EVIDENCE_REPORT.md")

    if not os.path.exists(bldgs_path):
        print(f"Error: {bldgs_path} not found.")
        return

    with open(bldgs_path, "r", encoding="utf-8") as f:
        bldgs_data = json.load(f)

    all_floors = []
    floor_distribution = {}
    source_distribution = {}

    for b in bldgs_data["features"]:
        props = b["properties"]
        b_id = props.get("id", "UNKNOWN")
        parcel_id = props.get("linked_parcel_id", None)
        ground_elev = props.get("ground_elevation_m", 896.0)
        height_m = props.get("building_height_m", 3.5)
        num_floors = props.get("derived_floors", int(height_m // 3.5) or 1)
        source = props.get("height_source", "GOOGLE_OPEN_BUILDINGS_2.5D")
        confidence = props.get("height_confidence", "MEDIUM")

        floor_distribution[num_floors] = floor_distribution.get(num_floors, 0) + 1
        source_distribution[source] = source_distribution.get(source, 0) + 1

        for f_idx in range(num_floors):
            base_z = round(ground_elev + (f_idx * 3.5), 2)
            top_z = round(ground_elev + ((f_idx + 1) * 3.5), 2)
            
            floor_entity = {
                "floor_id": f"{b_id}-F{f_idx}",
                "building_id": b_id,
                "parcel_id": parcel_id,
                "floor_level": f_idx,
                "floor_name": "Ground Floor" if f_idx == 0 else f"Floor {f_idx}",
                "base_elevation_m": base_z,
                "top_elevation_m": top_z,
                "height_m": 3.5,
                "source": source,
                "confidence": confidence,
                "match_status_2d": props.get("match_status_2d", "UNKNOWN")
            }
            all_floors.append(floor_entity)

    # Save floor entities
    os.makedirs(os.path.dirname(out_floors_path), exist_ok=True)
    with open(out_floors_path, "w", encoding="utf-8") as f:
        json.dump(all_floors, f, indent=2)

    # Copy updated 3D buildings to frontend
    os.makedirs(os.path.dirname(frontend_bldgs_path), exist_ok=True)
    shutil.copy(bldgs_path, frontend_bldgs_path)

    print(f"Extracted {len(all_floors)} discrete floor entities across {len(bldgs_data['features'])} buildings.")
    print(f"Saved floor entities to {out_floors_path}")
    print(f"Synced 3D GeoJSON to {frontend_bldgs_path}")

    # Generate Report
    report = f"""# Phase 8: Floor Evidence Extraction Report

This report documents the extraction of 3D multi-storey floor entities linking physical structures to cadastral parcels in Bengaluru Urban.

## 1. Summary Statistics
- **Total Buildings Analyzed**: {len(bldgs_data['features'])}
- **Total Discrete Floor Entities Extracted**: {len(all_floors)}
- **Average Floors per Building**: {len(all_floors) / len(bldgs_data['features']):.2f}

## 2. Floor Count Distribution
| Floor Count | Building Count | Percentage |
| :--- | :--- | :--- |
"""
    for fl in sorted(floor_distribution.keys()):
        cnt = floor_distribution[fl]
        pct = (cnt / len(bldgs_data['features'])) * 100
        report += f"| **{fl} Floors** ({fl*3.5:.1f}m) | {cnt} | {pct:.1f}% |\n"

    report += f"""
## 3. Data Provenance & Evidence Hierarchy (Rule 3)
| Source | Count | Confidence | Provenance Description |
| :--- | :--- | :--- | :--- |
"""
    for src, cnt in source_distribution.items():
        conf = "HIGH" if src == "OSM_VERIFIED" else "MEDIUM"
        desc = "Explicit ground survey tagging" if src == "OSM_VERIFIED" else "Satellite ML height estimation (Google Open Buildings 2.5D)"
        report += f"| `{src}` | {cnt} | `{conf}` | {desc} |\n"

    report += f"""
**Output Artefacts**:
- Floor Entities Database: `data/processed/floor_entities.json`
- Updated 3D Web UI Dataset: `frontend/data/buildings_3d.geojson`
"""

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report generated at {report_path}")

if __name__ == "__main__":
    main()
