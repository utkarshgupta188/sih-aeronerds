"""
AeroNerds SIH26011 — Lightweight Demo Launcher
Team areonerds

Starts the MapLibre 3D Web UI on port 8000 using pre-computed, verified datasets.
Does NOT download datasets.
Does NOT retrain ML models.
Does NOT contact external APIs.
"""

import http.server
import os
import socketserver
import ssl
import sys

PORT = 8000
DIRECTORY = "frontend"

REQUIRED_FILES = [
    os.path.join("frontend", "index.html"),
    os.path.join("frontend", "app.js"),
    os.path.join("frontend", "styles.css"),
    os.path.join("frontend", "floor3d.js"),
    os.path.join("frontend", "omni_roles.js"),
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


import socket


def get_local_ip_addresses():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary = s.getsockname()[0]
        s.close()
        if primary and primary not in ips:
            ips.append(primary)
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


HTTPS_PORT = 8443
CERT_FILE = os.path.join("config", "cert.pem")
KEY_FILE = os.path.join("config", "key.pem")


def start_https_server():
    """Starts background HTTPS server for secure mobile device GPS access."""
    if not (os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)):
        return
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", HTTPS_PORT), DemoHttpRequestHandler) as httpsd:
            httpsd.socket = context.wrap_socket(httpsd.socket, server_side=True)
            print(f"[SECURE] HTTPS Server active on port {HTTPS_PORT} for Mobile Device GNSS/GPS.")
            httpsd.serve_forever()
    except Exception as e:
        print(f"[INFO] HTTPS Server note: {e}")


def main():
    print("==================================================")
    print(" AeroNerds SIH26011 Demo — Team areonerds      ")
    print("==================================================\n")

    verify_demo_data()

    # Launch HTTPS server in background thread for real mobile GPS access
    has_https = os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)
    if has_https:
        import threading
        t = threading.Thread(target=start_https_server, daemon=True)
        t.start()

    lan_ips = get_local_ip_addresses()
    print("[OK] Verified all required frontend and 3D datasets.")
    print(f"\n==================================================")
    print(f" Web UI Access URLs (Local Machine & Local Network):")
    print(f"  > HTTP Localhost:           http://localhost:{PORT}/")
    for ip in lan_ips:
        print(f"  > HTTP LAN Network:         http://{ip}:{PORT}/")
    if has_https:
        print(f"  ------------------------------------------------")
        print(f"  > HTTPS Mobile (Real GPS):  https://localhost:{HTTPS_PORT}/")
        for ip in lan_ips:
            print(f"  > HTTPS Mobile (Real GPS):  https://{ip}:{HTTPS_PORT}/")
    print(f"==================================================\n")

    if has_https and lan_ips:
        print(f"📱 TO ACCESS REAL-TIME DEVICE GPS ON MOBILE PHONE / TABLET:")
        print(f"   1. Open on mobile:  https://{lan_ips[0]}:{HTTPS_PORT}/")
        print(f"   2. Tap 'Advanced' -> 'Proceed' (for local self-signed SSL)")
        print(f"   3. Mobile Chrome/Safari will allow full hardware GNSS & Barometer access!\n")
    elif lan_ips:
        print(f"To open on a mobile phone / tablet on the same Wi-Fi / LAN:")
        print(f"  ==>  http://{lan_ips[0]}:{PORT}/\n")

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
            print(f"Check if AeroNerds is already open at http://localhost:{PORT}/")
            if lan_ips:
                print(f"Or via local network: http://{lan_ips[0]}:{PORT}/")
                if has_https:
                    print(f"Or via secure HTTPS:  https://{lan_ips[0]}:{HTTPS_PORT}/")
        else:
            print(f"\n[ERROR] Could not start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
