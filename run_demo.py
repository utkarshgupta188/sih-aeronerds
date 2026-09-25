"""
BoundaryLens SIH26011 — Lightweight Demo Launcher
Team areonerds

Starts the MapLibre 3D Web UI on port 8000 using pre-computed, verified datasets.
Does NOT download datasets.
Does NOT retrain ML models.
Does NOT contact external APIs.
"""

import http.server
import os
import socketserver
import sys

PORT = 8000
DIRECTORY = "frontend"

REQUIRED_FILES = [
    os.path.join("frontend", "index.html"),
    os.path.join("frontend", "app.js"),
    os.path.join("frontend", "styles.css"),
    os.path.join("frontend", "floor3d.js"),
    os.path.join("frontend", "data", "buildings_3d.geojson"),
    os.path.join("frontend", "data", "cadastral_parcels_valid.geojson"),
]


def verify_demo_data():
    missing = []
    empty = []
    for rel_path in REQUIRED_FILES:
        if not os.path.exists(rel_path):
            missing.append(rel_path)
        elif os.path.getsize(rel_path) == 0:
            empty.append(rel_path)

    if missing or empty:
        print("==================================================")
        print(" [ERROR] Demo data is incomplete or missing!       ")
        print("==================================================")
        if missing:
            print("\nMissing required files:")
            for m in missing:
                print(f"  - {m}")
        if empty:
            print("\nEmpty (0 bytes) files:")
            for e in empty:
                print(f"  - {e}")
        print("\nPlease run the full pipeline first to generate the verified outputs:")
        print("    python run_pipeline.py\n")
        sys.exit(1)


class DemoHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        # Silence routine 200/304 GET requests to keep the terminal clean for judging
        if args and str(args[1]) in ("200", "304"):
            return
        super().log_message(format, *args)


def main():
    print("==================================================")
    print(" BoundaryLens SIH26011 Demo — Team areonerds      ")
    print("==================================================\n")

    verify_demo_data()

    print("[OK] Verified all required frontend and 3D datasets.")
    print(f"\nStarting MapLibre 3D Demo UI on http://localhost:{PORT}")
    print(f"Open in browser: http://localhost:{PORT}/\n")
    print("Use this mode for reliable, offline, zero-latency evaluation.")
    print("Press Ctrl+C to stop the demo server.\n")

    # Allow immediate address reuse
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), DemoHttpRequestHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDemo server stopped. Good luck with the judging!")
    except OSError as e:
        if "address already in use" in str(e).lower() or getattr(e, "winerror", None) == 10048:
            print(f"\n[WARNING] Port {PORT} is already in use by another process.")
            print(f"Check if BoundaryLens is already open at http://localhost:{PORT}/")
        else:
            print(f"\n[ERROR] Could not start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
