import os
import json
import shutil

def main():
    print("=========================================")
    print("  PHASE 10: EVIDENCE FUSION & CONFLICT   ")
    print("=========================================\n")

    bldgs_path = os.path.join("data", "processed", "buildings_ai_analyzed.geojson")
    ledger_path = os.path.join("data", "processed", "evidence_fusion_ledger.json")
    out_bldgs_path = os.path.join("data", "processed", "buildings_fused_final.geojson")
    frontend_path = os.path.join("frontend", "data", "buildings_3d.geojson")
    report_path = os.path.join("docs", "EVIDENCE_FUSION_REPORT.md")

    if not os.path.exists(bldgs_path):
        print(f"Error: {bldgs_path} not found.")
        return

    with open(bldgs_path, "r", encoding="utf-8") as f:
        bldgs_data = json.load(f)

    total = len(bldgs_data["features"])
    print(f"Loaded {total} buildings. Running deterministic fusion engine...")

    ledger = {}
    status_counts = {
        "VERIFIED": 0,
        "PROVISIONAL": 0,
        "HUMAN_VERIFICATION_REQUIRED": 0
    }

    for b in bldgs_data["features"]:
        props = b["properties"]
        b_id = str(props.get("id", "UNKNOWN"))
        match_status_2d = props.get("match_status_2d", "UNKNOWN")
        ai_anomaly = props.get("ai_anomaly_flag", False)
        ai_score = props.get("ai_anomaly_score", 0.0)

        # Rule 3 & 8 Decision Matrix
        if match_status_2d == "CONTAINED" and not ai_anomaly:
            final_status = "VERIFIED"
        elif match_status_2d == "MAJORITY" and not ai_anomaly:
            final_status = "PROVISIONAL"
        else:
            # Encroachment or AI Anomaly forces human review gate
            final_status = "HUMAN_VERIFICATION_REQUIRED"

        status_counts[final_status] += 1
        props["final_verification_status"] = final_status

        # Create immutable provenance ledger entry for auditability
        ledger[b_id] = {
            "building_id": b_id,
            "final_verification_status": final_status,
            "evidence_lineage": {
                "2d_spatial_linkage": {
                    "parcel_id": props.get("linked_parcel_id"),
                    "overlap_ratio": props.get("parcel_overlap_ratio"),
                    "match_status": match_status_2d,
                    "provenance": "OPENCITY_CADASTRAL_INTERSECTION",
                    "confidence": "HIGH" if match_status_2d == "CONTAINED" else "MEDIUM"
                },
                "elevation_base": {
                    "ground_elevation_m": props.get("ground_elevation_m"),
                    "provenance": "COPERNICUS_GLO30_DEM",
                    "confidence": "HIGH"
                },
                "vertical_height": {
                    "height_m": props.get("building_height_m"),
                    "derived_floors": props.get("derived_floors"),
                    "provenance": props.get("height_source", "GOOGLE_OPEN_BUILDINGS_2.5D"),
                    "confidence": props.get("height_confidence", "MEDIUM")
                },
                "ai_anomaly_inspection": {
                    "flagged": ai_anomaly,
                    "anomaly_score": ai_score,
                    "model": "SKLEARN_ISOLATION_FOREST_4D",
                    "provenance": "AI_SURFACE_INSPECTION"
                }
            }
        }

    # Save outputs
    with open(out_bldgs_path, "w", encoding="utf-8") as f:
        json.dump(bldgs_data, f, indent=2)

    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)

    shutil.copy(out_bldgs_path, frontend_path)

    print(f"\nFusion Engine Execution Complete!")
    print(f"  VERIFIED: {status_counts['VERIFIED']} ({(status_counts['VERIFIED']/total)*100:.1f}%)")
    print(f"  PROVISIONAL: {status_counts['PROVISIONAL']} ({(status_counts['PROVISIONAL']/total)*100:.1f}%)")
    print(f"  HUMAN VERIFICATION REQUIRED: {status_counts['HUMAN_VERIFICATION_REQUIRED']} ({(status_counts['HUMAN_VERIFICATION_REQUIRED']/total)*100:.1f}%)")
    print(f"\nSaved evidence ledger to {ledger_path}")
    print(f"Synced 3D GeoJSON to {frontend_path}")

    # Generate Report
    report = f"""# Phase 10: Evidence Fusion & Conflict Engine Report

This report documents the deterministic evidence fusion engine execution for the BoundaryLens SIH26011 prototype.
In strict compliance with **Project Rule 3** (Evidence Hierarchy) and **Project Rule 8** (Human Verification Gates), all conflicting data sources are explicitly surfaced to the audit log.

## 1. Final Verification Gate Summary
- **Total Buildings Evaluated**: {total}
- **🟢 VERIFIED** (100% Contained & AI Approved): {status_counts['VERIFIED']} ({(status_counts['VERIFIED']/total)*100:.1f}%)
- **🟡 PROVISIONAL** (Majority Overlap & AI Approved): {status_counts['PROVISIONAL']} ({(status_counts['PROVISIONAL']/total)*100:.1f}%)
- **🔴 HUMAN VERIFICATION REQUIRED** (Boundary Encroachments or AI Outliers): {status_counts['HUMAN_VERIFICATION_REQUIRED']} ({(status_counts['HUMAN_VERIFICATION_REQUIRED']/total)*100:.1f}%)

## 2. Evidence Lineage Schema
Every building is assigned an immutable audit record in `data/processed/evidence_fusion_ledger.json`.

**Output Files**:
- Evidence Ledger Database: `data/processed/evidence_fusion_ledger.json`
- Final Fused 3D GeoJSON: `data/processed/buildings_fused_final.geojson`
"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report generated at {report_path}")

if __name__ == "__main__":
    main()
