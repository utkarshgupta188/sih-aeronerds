import os
import json
import shutil

def main():
    print("=========================================")
    print("  PHASE 14: GENERATE VERTICAL 3D ULPINS  ")
    print("=========================================\n")

    bldgs_path = os.path.join("data", "processed", "buildings_fused_final.geojson")
    floors_path = os.path.join("data", "processed", "floor_entities.json")
    out_ulpins_path = os.path.join("data", "processed", "vertical_ulpins_proposed.json")
    frontend_path = os.path.join("frontend", "data", "buildings_3d.geojson")

    if not os.path.exists(bldgs_path) or not os.path.exists(floors_path):
        print("Error: Missing fused buildings or floor entities JSON.")
        return

    with open(bldgs_path, "r", encoding="utf-8") as f:
        bldgs_data = json.load(f)

    with open(floors_path, "r", encoding="utf-8") as f:
        floors_data = json.load(f)

    print(f"Generating hierarchical Vertical ULPINs for {len(bldgs_data['features'])} buildings and {len(floors_data)} floors...")

    ulpins_manifest = []

    # 1. Process Building Geometries
    for b in bldgs_data["features"]:
        props = b["properties"]
        b_id = str(props.get("id", "0"))
        parcel_id = str(props.get("linked_parcel_id", "UNMAPPED_PARCEL"))
        
        # Format: IN-KA-BLR-[PARCEL_ID]-B[BUILDING_ID]
        proposed_ulpin = f"IN-KA-BLR-P{parcel_id}-B{b_id}"
        props["proposed_vertical_ulpin"] = proposed_ulpin
        props["ulpin_disclaimer"] = "PROPOSED_VERTICAL_LINKAGE_NOT_OFFICIAL_ISSUANCE"

    # 2. Process Floor Entities
    for fl in floors_data:
        b_id = str(fl.get("building_id", "0"))
        parcel_id = str(fl.get("parcel_id", "UNMAPPED_PARCEL"))
        fl_num = fl.get("floor_level", 0)

        proposed_fl_ulpin = f"IN-KA-BLR-P{parcel_id}-B{b_id}-F{fl_num}"
        fl["proposed_vertical_ulpin"] = proposed_fl_ulpin

        ulpins_manifest.append({
            "proposed_vertical_ulpin": proposed_fl_ulpin,
            "building_id": b_id,
            "parcel_id": parcel_id,
            "floor_level": fl_num,
            "base_elevation_m": fl.get("base_elevation_m"),
            "top_elevation_m": fl.get("top_elevation_m"),
            "provenance": fl.get("source"),
            "confidence": fl.get("confidence"),
            "legal_disclaimer": "PROPOSED_LINKAGE_REQUIRES_COMPETENT_AUTHORITY"
        })

    # Save outputs
    with open(bldgs_path, "w", encoding="utf-8") as f:
        json.dump(bldgs_data, f, indent=2)

    with open(floors_path, "w", encoding="utf-8") as f:
        json.dump(floors_data, f, indent=2)

    with open(out_ulpins_path, "w", encoding="utf-8") as f:
        json.dump(ulpins_manifest, f, indent=2)

    shutil.copy(bldgs_path, frontend_path)

    print(f"\nVertical ULPIN Generation Complete!")
    print(f"  Generated {len(ulpins_manifest)} Vertical 3D ULPIN records.")
    print(f"Saved ULPIN manifest to {out_ulpins_path}")
    print(f"Synced 3D GeoJSON to {frontend_path}")

if __name__ == "__main__":
    main()
