import os
import json
import shutil

def main():
    print("=========================================")
    print("  PHASE 9: AI ANOMALY DETECTION (SKLEARN)")
    print("=========================================\n")

    try:
        from sklearn.ensemble import IsolationForest
        import numpy as np
    except ImportError:
        print("Error: scikit-learn is required for AI anomaly detection.")
        print("Please run: pip install scikit-learn numpy")
        return

    bldgs_path = os.path.join("data", "processed", "buildings_3d.geojson")
    out_path = os.path.join("data", "processed", "buildings_ai_analyzed.geojson")
    frontend_path = os.path.join("frontend", "data", "buildings_3d.geojson")
    report_path = os.path.join("docs", "AI_ANOMALY_REPORT.md")

    if not os.path.exists(bldgs_path):
        print(f"Error: {bldgs_path} not found.")
        return

    with open(bldgs_path, "r", encoding="utf-8") as f:
        bldgs_data = json.load(f)

    features = bldgs_data["features"]
    total = len(features)
    print(f"Loaded {total} buildings. Building feature matrix for Isolation Forest...")

    # Extract 4D Feature Vector: [overlap_ratio, height_m, ground_elevation_m, num_floors]
    X = []
    for b in features:
        props = b["properties"]
        overlap = float(props.get("parcel_overlap_ratio", 1.0))
        
        height_val = props.get("building_height_m")
        try:
            height = float(height_val)
        except (TypeError, ValueError):
            height = np.nan
        
        elev = float(props.get("ground_elevation_m", 896.0))
        
        floors_val = props.get("derived_floors")
        try:
            floors = float(floors_val)
        except (TypeError, ValueError):
            floors = np.nan
        
        # Add non-linear interaction feature (height per floor ratio anomaly)
        X.append([overlap, height, elev, floors])

    X = np.array(X)
    
    # Impute missing heights/floors gracefully for the ML model without injecting fake data into the ledger
    from sklearn.impute import SimpleImputer
    imputer = SimpleImputer(strategy='median')
    X = imputer.fit_transform(X)

    # Train Isolation Forest (3% contamination target for top spatial/vertical outliers)
    clf = IsolationForest(contamination=0.03, random_state=42)
    predictions = clf.fit_predict(X)  # -1 for anomaly, 1 for normal
    scores = clf.decision_function(X) # lower score = more anomalous

    anomaly_count = 0
    anomalies_list = []

    for idx, b in enumerate(features):
        props = b["properties"]
        is_anomaly = bool(predictions[idx] == -1)
        score = float(scores[idx])

        props["ai_anomaly_flag"] = is_anomaly
        props["ai_anomaly_score"] = round(score, 4)
        props["ai_status"] = "AI_ANOMALY_DETECTED" if is_anomaly else "NORMAL"

        if is_anomaly:
            anomaly_count += 1
            anomalies_list.append({
                "id": props.get("id"),
                "parcel_id": props.get("linked_parcel_id"),
                "match_status": props.get("match_status_2d"),
                "height_m": props.get("building_height_m"),
                "overlap_ratio": props.get("parcel_overlap_ratio"),
                "ai_score": round(score, 4)
            })

    # Save outputs
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bldgs_data, f, indent=2)

    shutil.copy(out_path, frontend_path)

    print(f"\nAI Analysis Complete!")
    print(f"  Total Analyzed: {total}")
    print(f"  Anomalies Flagged: {anomaly_count} ({(anomaly_count/total)*100:.2f}%)")
    print(f"Saved analyzed GeoJSON to {out_path}")
    print(f"Synced 3D GeoJSON to {frontend_path}")

    # Generate Report
    report = f"""# Phase 9: AI Anomaly Detection Report (Isolation Forest)

This report details the unsupervised Machine Learning analysis conducted on the 2,734 3D building entities in Bengaluru Urban, strictly following **Project Rule 5** (*AI assists; it does not adjudicate legal rights*).

## 1. Model Configuration
- **Algorithm**: `sklearn.ensemble.IsolationForest`
- **Contamination Parameter**: `0.03` (Top 3% spatial/vertical outliers)
- **Feature Matrix Inputs**:
  1. `parcel_overlap_ratio` (2D Spatial Boundary Intersection)
  2. `building_height_m` (Satellite Height)
  3. `ground_elevation_m` (Copernicus DEM Terrain)
  4. `derived_floors` (Multi-Storey Count)

## 2. Detection Results
- **Total Buildings Evaluated**: {total}
- **Normal Inliers**: {total - anomaly_count}
- **AI Anomaly Flags Raised**: {anomaly_count} ({(anomaly_count/total)*100:.2f}%)

## 3. Sample Flagged Spatial/Vertical Conflicts
| Building ID | Linked Parcel | 2D Match Status | Height | Overlap | AI Anomaly Score |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for a in anomalies_list[:10]:
        report += f"| `{a['id']}` | `{a['parcel_id']}` | `{a['match_status']}` | {a['height_m']}m | {a['overlap_ratio']} | `{a['ai_score']}` |\n"

    report += f"""
**Output File**: `data/processed/buildings_ai_analyzed.geojson`
"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report generated at {report_path}")

if __name__ == "__main__":
    main()
