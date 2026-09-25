import subprocess
import sys
import time

def run_script(script_path):
    print(f"\n[{time.strftime('%H:%M:%S')}] Executing: {script_path}")
    print("-" * 50)
    result = subprocess.run([sys.executable, script_path], check=False)
    if result.returncode != 0:
        print(f"\n[ERROR] Script {script_path} failed with exit code {result.returncode}")
        print("Pipeline aborted.")
        sys.exit(result.returncode)

def main():
    print("==================================================")
    print(" BoundaryLens SIH26011 - Full Pipeline Execution  ")
    print("==================================================\n")

    scripts = [
        # Initialization & Ingestion
        "scripts/01_select_aoi.py",
        "scripts/ingestion/load_osm.py",
        "scripts/ingestion/load_cadastral.py",
        "scripts/ingestion/load_copernicus_dem.py",
        "scripts/ingestion/load_bare_earth_dem.py",
        
        # Processing & Normalisation
        "scripts/03_normalise_layers.py",
        "scripts/04_validate_data_quality.py",
        
        # Spatial Matching & Topology
        "scripts/05_match_parcels_buildings.py",
        
        # 3D Extraction & Real Data Evidence
        "scripts/06_extract_elevation.py",
        "scripts/08_fetch_real_heights.py",
        "scripts/08_extract_floor_entities.py",
        
        # AI & Fusion Engine
        "scripts/09_detect_anomalies_ai.py",
        "scripts/10_fuse_evidence_engine.py",

        # Additive: NDVI Vegetation Evidence Layer (Phase 11).
        # Runs AFTER fusion so it only annotates the final fused buildings with a
        # vegetation-vs-building height confidence block. It does not alter any
        # earlier phase. Both steps exit 0 even if the NDVI scene cannot be
        # obtained (buildings are then marked NDVI_UNAVAILABLE, never fabricated).
        "scripts/ingestion/load_sentinel2_ndvi.py",
        "scripts/11_ndvi_vegetation_evidence.py",

        # Additive: Floor Detection (Phase 12).
        #   load_osm_floor_labels : ~12.7k REAL OSM building:levels labels across
        #                           greater Bengaluru (AOI excluded) via Overpass.
        #   train_floor_model     : spatial-split RandomForest / HistGB, calibrated
        #                           confidence + IsolationForest OOD. Real metrics.
        #   12_estimate_floors    : OBSERVED (real tag) / PREDICTED (model, accepted)
        #                           / NOT_DETERMINABLE. No CNN (no floor-resolving
        #                           imagery), no synthetic data, no fabricated
        #                           confidence. All three exit 0 if a source is
        #                           unavailable (buildings -> NOT_DETERMINABLE).
        "scripts/ingestion/load_osm_floor_labels.py",
        "scripts/ingestion/load_copernicus_glo30.py",
        "scripts/train_floor_model.py",
        "scripts/12_estimate_floors.py",

        # Master Outputs & Compliance
        # Note: 14_generate_vertical_ulpins.py was removed to strictly adhere to "No Fake ULPIN" rule.
    ]

    for script in scripts:
        run_script(script)

    print("\n==================================================")
    print(" PIPELINE COMPLETE! STARTING WEB UI ")
    print("==================================================")
    
    print("\nStarting MapLibre 3D UI on http://localhost:8000")
    print("Press Ctrl+C to stop the server.\n")
    
    try:
        subprocess.run([sys.executable, "-m", "http.server", "8000", "--directory", "frontend"])
    except KeyboardInterrupt:
        print("\nServer stopped. Pipeline execution finished.")

if __name__ == "__main__":
    main()
