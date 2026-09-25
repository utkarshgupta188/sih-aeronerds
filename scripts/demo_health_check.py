"""
BoundaryLens SIH26011 — Demo Readiness Health Check
Team areonerds

Verifies the integrity of all frontend, spatial data, and evidence assets
required for an offline, zero-latency demonstration during judging.
"""

import json
import os
import sys

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def check_file(rel_path, min_bytes=10):
    """Returns (exists, valid, message)"""
    if not os.path.exists(rel_path):
        return False, False, f"Missing: {rel_path}"
    size = os.path.getsize(rel_path)
    if size < min_bytes:
        return True, False, f"Empty or too small ({size} bytes): {rel_path}"
    return True, True, "OK"


def check_json_file(rel_path, min_features=1):
    exists, valid, msg = check_file(rel_path)
    if not valid:
        return exists, valid, msg
    try:
        with open(rel_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "features" in data:
            count = len(data["features"])
            if count < min_features:
                return True, False, f"GeoJSON has insufficient features ({count}): {rel_path}"
            return True, True, f"OK ({count} features)"
        return True, True, "OK (valid JSON)"
    except Exception as exc:
        return True, False, f"Corrupt JSON ({exc}): {rel_path}"


def main():
    print("==========================================")
    print(" BoundaryLens SIH26011 Demo Health Check  ")
    print("==========================================")

    all_passed = True
    diagnostics = []

    # 1. Frontend Core
    frontend_files = [
        os.path.join("frontend", "index.html"),
        os.path.join("frontend", "app.js"),
        os.path.join("frontend", "styles.css"),
        os.path.join("frontend", "floor3d.js"),
    ]
    fe_ok = True
    for fp in frontend_files:
        _, valid, msg = check_file(fp)
        if not valid:
            fe_ok = False
            diagnostics.append(f"[REQUIRED FOR DEMO] Frontend: {msg}")

    if fe_ok:
        print("[PASS] Frontend")
    else:
        print("[FAIL] Frontend")
        all_passed = False

    # 2. Building Data (3D & 2D)
    bldg_path = os.path.join("frontend", "data", "buildings_3d.geojson")
    bldg_exists, bldg_valid, bldg_msg = check_json_file(bldg_path, min_features=100)
    if bldg_valid:
        print("[PASS] Building data")
    else:
        print("[FAIL] Building data")
        diagnostics.append(f"[REQUIRED FOR DEMO] Building data: {bldg_msg}")
        all_passed = False

    # 3. Parcel Data (Cadastral)
    parcel_path = os.path.join("frontend", "data", "cadastral_parcels_valid.geojson")
    parcel_exists, parcel_valid, parcel_msg = check_json_file(parcel_path, min_features=10)
    if parcel_valid:
        print("[PASS] Parcel data")
    else:
        print("[FAIL] Parcel data")
        diagnostics.append(f"[REQUIRED FOR DEMO] Parcel data: {parcel_msg}")
        all_passed = False

    # 4. Elevation Data (Bare-Earth DEM)
    dem_raw_path = os.path.join("data", "raw", "dem", "bare_earth_dem.tif")
    dem_staged_path = os.path.join("data", "raw", "bare_earth_dem.tif")
    dem_ok = False

    if os.path.exists(dem_raw_path) and os.path.getsize(dem_raw_path) > 1000:
        dem_ok = True
    elif os.path.exists(dem_staged_path) and os.path.getsize(dem_staged_path) > 1000:
        dem_ok = True
    elif bldg_valid:
        # For demo mode: check if buildings_3d.geojson contains pre-sampled DEM elevation
        try:
            with open(bldg_path, "r", encoding="utf-8") as f:
                sample = json.load(f)["features"][0]["properties"]
            if "ground_elevation_m" in sample or "building_height_m" in sample:
                dem_ok = True
        except Exception:
            pass

    if dem_ok:
        print("[PASS] Elevation data")
    else:
        print("[FAIL] Elevation data")
        diagnostics.append(
            f"[REQUIRED FOR DEMO] Elevation data missing at {dem_raw_path} and {dem_staged_path}"
        )
        all_passed = False

    # 5. Floor Evidence (Phase 12 outputs)
    floor_est_path = os.path.join("data", "processed", "buildings_floor_estimated.geojson")
    floor_model_path = os.path.join("data", "processed", "floor_model.joblib")
    
    # For demo display, if frontend/data/buildings_3d.geojson has floor fields, that suffices
    floor_ok = False
    if os.path.exists(floor_est_path) and os.path.getsize(floor_est_path) > 1000:
        floor_ok = True
    elif bldg_valid:
        # Check if buildings_3d.geojson contains floor properties
        try:
            with open(bldg_path, "r", encoding="utf-8") as f:
                sample = json.load(f)["features"][0]["properties"]
            if "floor_detection_status" in sample or "derived_floors" in sample:
                floor_ok = True
        except Exception:
            pass

    if floor_ok:
        print("[PASS] Floor evidence")
    else:
        print("[FAIL] Floor evidence")
        diagnostics.append(f"[REQUIRED FOR DEMO] Floor evidence missing in {floor_est_path}")
        all_passed = False

    # 6. AI & Evidence Ledger (Phase 9 & 10 outputs)
    ledger_path = os.path.join("data", "processed", "evidence_fusion_ledger.json")
    ledger_exists, ledger_valid, ledger_msg = check_file(ledger_path, min_bytes=500)
    if ledger_valid:
        print("[PASS] AI/evidence data")
    elif bldg_valid:
        # For demo mode: check if buildings_3d.geojson contains pre-computed AI anomaly & evidence fields
        try:
            with open(bldg_path, "r", encoding="utf-8") as f:
                sample = json.load(f)["features"][0]["properties"]
            if "anomaly_status" in sample or "match_status_2d" in sample:
                ledger_valid = True
                print("[PASS] AI/evidence data (embedded in demo GeoJSON)")
            else:
                print("[FAIL] AI/evidence data")
                diagnostics.append(f"[REQUIRED FOR DEMO] AI/evidence ledger: {ledger_msg}")
                all_passed = False
        except Exception:
            print("[FAIL] AI/evidence data")
            diagnostics.append(f"[REQUIRED FOR DEMO] AI/evidence ledger: {ledger_msg}")
            all_passed = False
    else:
        print("[FAIL] AI/evidence data")
        diagnostics.append(f"[REQUIRED FOR DEMO] AI/evidence ledger: {ledger_msg}")
        all_passed = False

    # 7. Required Python Dependencies for Local Environment
    deps = ["json", "http.server", "subprocess"]
    deps_ok = True
    for mod in deps:
        try:
            __import__(mod)
        except ImportError:
            deps_ok = False
            diagnostics.append(f"[REQUIRED FOR DEMO] Python module '{mod}' could not be imported")

    # Optional geospatial packages
    geo_deps = ["shapely", "rasterio", "geopandas", "sklearn"]
    missing_geo = []
    for gmod in geo_deps:
        try:
            __import__(gmod)
        except ImportError:
            missing_geo.append(gmod)

    if deps_ok:
        print("[PASS] Required dependencies")
    else:
        print("[FAIL] Required dependencies")
        all_passed = False

    # Optional / Full Pipeline items audit (informative, non-fatal)
    optional_items = [
        ("Surface DSM Raster (GLO-30)", os.path.join("data", "raw", "glo30_dsm.tif")),
        ("Sentinel-2 NDVI Raster", os.path.join("data", "raw", "ndvi_s2_aoi.tif")),
        ("Cadastral Source KMZ", os.path.join("data", "raw", "bengaluru_urban_cadastral.kmz")),
        ("OSM Source Footprints", os.path.join("data", "raw", "osm_data.json")),
        ("Floor ML Model (.joblib)", floor_model_path),
    ]

    print("\n--- Additional Evidence Status ---")
    for label, path in optional_items:
        exists = os.path.exists(path) and os.path.getsize(path) > 0
        status_tag = "[AVAILABLE]" if exists else "[OPTIONAL / FULL PIPELINE ONLY]"
        print(f"  {status_tag:32} {label}")

    if missing_geo:
        print(f"  {'[OPTIONAL IN DEMO MODE]':32} Geospatial stack: {', '.join(missing_geo)} (needed for full pipeline)")

    print("----------------------------------\n")

    if all_passed:
        print("DEMO READY")
        print("\nTo start the presentation interface:")
        print("    python run_demo.py\n")
        return 0
    else:
        print("DEMO NOT READY")
        print("\nIssues to resolve before presenting:")
        for diag in diagnostics:
            print(f"  - {diag}")
        print("\nTip: To regenerate all processed assets, run:")
        print("    python run_pipeline.py\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
