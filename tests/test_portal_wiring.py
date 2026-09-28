"""Structural checks for the authenticated portal markup and wiring.

Catches the class of regression that is easy to introduce when adding a
workspace: a duplicated element id, a workspace the backend can never render,
or a role-scoped control that is missing its capability attribute.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "frontend" / "index.html"
BACKEND_RBAC = ROOT / "backend" / "rbac.py"
OMNI = ROOT / "frontend" / "omni_roles.js"
AUTH_JS = ROOT / "frontend" / "auth.js"
LOGIN_JS = ROOT / "frontend" / "login.js"
ROLE_DATA = ROOT / "frontend" / "role_data.js"

failures = []
checks = 0


def check(ok, message):
    global checks
    checks += 1
    if not ok:
        failures.append(message)


html = HTML.read_text(encoding="utf-8")
rbac_src = BACKEND_RBAC.read_text(encoding="utf-8")
omni = OMNI.read_text(encoding="utf-8")

# --- 1. no duplicate element ids -----------------------------------------
ids = re.findall(r'id="([^"]+)"', html)
duplicates = sorted({i for i in ids if ids.count(i) > 1})
check(not duplicates, f"duplicate element ids in index.html: {duplicates}")

# --- 2. every backend workspace id exists in the markup -------------------
backend_workspaces = set(re.findall(r'workspace_id="([a-z-]+-workspace)"', rbac_src))
frontend_workspaces = set(re.findall(r'id="([a-z-]+-workspace)"', html))
missing = sorted(backend_workspaces - frontend_workspaces)
check(
    not missing,
    f"backend declares workspaces with no markup: {missing}",
)

# --- 3. every frontend workspace is known to the backend -------------------
orphan = sorted(frontend_workspaces - backend_workspaces)
check(not orphan, f"markup workspaces unknown to backend: {orphan}")

# --- 4. sign-in gate and its controls exist -------------------------------
for required in (
    "auth-gate",
    "auth-form",
    "auth-username",
    "auth-password",
    "auth-submit",
    "auth-role-grid",
    "auth-demo-accounts",
    "auth-status",
):
    check(f'id="{required}"' in html, f"sign-in gate missing #{required}")

# --- 5. auth + login + role data scripts are loaded ------------------------
for script in ("auth.js", "login.js", "role_data.js"):
    check(f'src="{script}' in html, f"index.html does not load {script}")

# --- 6. script load order: auth.js must precede login.js and omni_roles.js -
def script_pos(name):
    m = re.search(rf'src="{re.escape(name)}\?v=\d+"', html)
    return m.start() if m else -1

check(
    -1 < script_pos("auth.js") < script_pos("login.js") < script_pos("omni_roles.js"),
    "auth.js must load before login.js, and both before omni_roles.js",
)

# --- 7. the four statutory seats are all present --------------------------
for role in ("registrar", "planner", "sdm", "citizen"):
    check(f'data-role="{role}"' in html, f"persona card missing for role '{role}'")
    check(
        f'"{role}": Role(' in rbac_src or f'"{role}": Role(' in rbac_src.replace(" ", ""),
        f"backend role '{role}' not defined",
    )

# --- 8. the legacy free-role 'admin' key must not be used for a workspace --
check(
    'id="admin-workspace"' not in html,
    "admin-workspace still present; role was renamed to registrar",
)
check(
    'localStorage.getItem("aeronerds_gov_role")' not in omni,
    "role must not be restored from localStorage; it comes from the session",
)

# --- 9. adjudication + export controls carry capability attributes --------
# Registrar adjudication block
adj_block = re.search(
    r'<div class="action-buttons"([^>]*)>.*?APPROVE.*?</div>\s*</div>', html, re.S
)
check(adj_block is not None, "could not locate the adjudication block")
if adj_block:
    check(
        "review:adjudicate" in adj_block.group(1),
        "adjudication block is missing data-cap=\"review:adjudicate\"",
    )

# Manifest export
export_block = re.search(r'<div style="margin: 10px 0;"([^>]*)>.*?admin-export-csv', html, re.S)
check(
    export_block is not None and "manifest:export" in export_block.group(1),
    "manifest export is missing data-cap=\"manifest:export\"",
)

# Grievance filing
check(
    'data-cap="grievance:file"' in html,
    "citizen grievance button is missing data-cap=\"grievance:file\"",
)

# --- 10. reviewAction must be server-validated -----------------------------
app_src = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
check(
    "/api/review/decision" in app_src,
    "reviewAction must post the decision to /api/review/decision",
)
check(
    'Auth.can("review:adjudicate")' in app_src,
    "reviewAction must check review:adjudicate before adjudicating",
)

# --- 11. setGovRole must refuse a role the session does not hold -----------
check(
    "sessionRole" in omni and "refused role change" in omni,
    "setGovRole must refuse a role different from the signed-in seat",
)

# --- 12. no fabricated citizen ownership claims left in the markup ---------
# These previously rendered as real government registry facts.
fabricated = [
    "Smt. Priya Sharma</span>",
    "MP-BHP-REG-2024-8891",
    "NIL (Clear Title)",
    "Paid (FY 2026-27)",
]
for needle in fabricated:
    check(needle not in html, f"fabricated registry claim still in markup: {needle!r}")

# The honest disclosure must be present instead.
check(
    "NOT_DETERMINABLE</code>" in html or "NOT_DETERMINABLE" in html,
    "citizen panel must disclose NOT_DETERMINABLE for non-geometric statutory facts",
)

# --- 13. citizen workspace must be scoped, not public ---------------------
check(
    'data-cap="building:read:own"' in html,
    "citizen workspace missing its own-records capability attribute",
)

# --- 14. auth client must re-check the session, not trust localStorage -----
auth_src = AUTH_JS.read_text(encoding="utf-8")
check("sessionStorage" in auth_src, "token should live in sessionStorage, not localStorage")
check(
    "applyCapabilityVisibility" in auth_src,
    "auth client must expose a capability visibility pass",
)

# --- 15. role_data must read from the scoped portfolio endpoint -----------
rd = ROLE_DATA.read_text(encoding="utf-8")
check(
    "/api/records/portfolio" in rd,
    "citizen desk must load data from /api/records/portfolio",
)
check(
    "/api/grievances" in rd,
    "SDM desk must load the grievance register from the API",
)

print(f"ran {checks} structural checks")
if failures:
    print(f"\n{len(failures)} FAILED:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all structural checks passed")
# --- pytest entry point ---------------------------------------------------
def test_portal_wiring_is_sound():
    assert not failures, "structural wiring problems:\n" + "\n".join(failures)
    assert checks > 30, f"expected a substantial check count, ran only {checks}"
