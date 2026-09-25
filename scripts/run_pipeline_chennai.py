import os
import subprocess
import sys
import time

def run_script(script_path):
    print(f"\n[{time.strftime('%H:%M:%S')}] Executing (Chennai Route): {script_path}")
    print("-" * 50)
    result = subprocess.run([sys.executable, script_path], check=False)
    if result.returncode != 0:
        print(f"\n[ERROR] Script {script_path} failed with exit code {result.returncode}")
        print("Pipeline aborted.")
        sys.exit(result.returncode)

def main():
    print("==================================================")
    print(" BoundaryLens SIH26011 - DRDO Chennai Route       ")
    print(" ** WARNING: UNVERIFIED MANIFEST OVERRIDE **      ")
    print("==================================================\n")

    os.environ["BOUNDARYLENS_REGION"] = "chennai.json"

    scripts = [
        "scripts/ingestion/load_drdo_chennai.py",
        "scripts/ingestion/load_cadastral.py",
        "scripts/05_match_chennai.py",
        "scripts/06_extract_elevation_chennai.py",
        "scripts/09_detect_anomalies_chennai.py",
        "scripts/10_fuse_chennai.py"
    ]

    for script in scripts:
        run_script(script)

    print("\n==================================================")
    print(" CHENNAI PIPELINE COMPLETE! ")
    print("==================================================")

    print("\nStarting MapLibre 3D UI on http://localhost:8001")
    print("Press Ctrl+C to stop the server.\n")
    
    try:
        subprocess.run([sys.executable, "-m", "http.server", "8001", "--directory", "frontend_chennai"])
    except KeyboardInterrupt:
        print("\nServer stopped. Pipeline execution finished.")

if __name__ == "__main__":
    main()
