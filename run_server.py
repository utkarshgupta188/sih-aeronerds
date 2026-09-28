"""
AeroNerds SIH26011 — Authenticated Demo Server (Team areonerds)

Serves the 3D cadastral portal AND the role-scoped auth API from a single
port (8000) so the demo needs no second process and no CORS setup.

    python run_server.py

What this adds over run_demo.py (the static-only launcher, still supported):
  * real sign-in with PBKDF2-hashed passwords
  * HMAC-signed session tokens
  * server-side capability checks on every protected action
  * citizens can only read property records linked to their own account

Demo accounts (fixtures for local evaluation only, not real credentials):

    registrar / Demo@Registrar1   Rule 8 adjudication, exports
    planner   / Demo@Planner1     FSI + zoning audit
    sdm       / Demo@SDM1         Grievance adjudication
    citizen   / Demo@Citizen1     Own linked records only
    citizen2  / Demo@Citizen2     Own linked records only

Set AERONERDS_TOKEN_SECRET to keep sessions alive across restarts.
"""

import os
import sys

try:
    import uvicorn
    from fastapi import FastAPI
except ImportError:
    print("=" * 58)
    print(" [ERROR] FastAPI / uvicorn are not installed.")
    print("=" * 58)
    print("Install the auth service dependencies:")
    print("    pip install -r requirements-auth.txt")
    print()
    print("If you only need the offline static demo, run:")
    print("    python run_demo.py")
    sys.exit(1)

PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "0.0.0.0")


def main() -> None:
    from backend.main import app, store

    users = store.list_users()
    print("=" * 58)
    print(" AeroNerds SIH26011 — Authenticated Portal Server       ")
    print("=" * 58)
    print(f" Accounts provisioned: {len(users)} (demo fixtures)")
    for u in users:
        links = store.citizen_building_ids(u.id)
        scope = f"  linked buildings: {len(links)}" if u.is_citizen else ""
        print(f"   - {u.username:<10} {u.role_id:<10} {u.full_name}{scope}")
    print()
    print(" Sign in at the portal with any username above and its demo password.")
    print(" Citizens can only ever read records linked to their own account.")
    print()
    print(f" Portal : http://localhost:{PORT}/")
    print(f" API    : http://localhost:{PORT}/api/meta/health")
    print("=" * 58)
    print(" Press Ctrl+C to stop.\n")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
