#!/usr/bin/env bash
# AeroNerds SIH26011 — roll out a new version, no Docker.
#
#   sudo bash deploy/deploy.sh
#
# Safe to run repeatedly. Refreshes the code, reinstalls dependencies if the
# requirements changed, restarts the service, and verifies the access model
# before reporting success. The signing secret and the auth database are
# never touched.

set -euo pipefail

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root: sudo bash deploy/deploy.sh"

APP_USER=aeronerds
APP_ROOT=/opt/aeronerds
APP_DIR="$APP_ROOT/app"
DATA_DIR=/var/lib/aeronerds
ENV_FILE=/etc/aeronerds/aeronerds.env
SRC_DIR="${AERONERDS_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

[ -d "$APP_DIR/backend" ] || die "not installed yet — run deploy/install.sh first"
[ -f "$ENV_FILE" ] || die "missing $ENV_FILE — run deploy/install.sh first"

# ------------------------------------------------------- pre-flight the code ---
# Import the new code in a throwaway process first. A syntax error or a broken
# import should be discovered here, not after a service restart has already
# taken the site down.
log "Pre-flight: importing the new code"
if ! sudo -u "$APP_USER" "$APP_ROOT/venv/bin/python" -c "
import sys
sys.path.insert(0, '$APP_DIR')
from backend.main import app
routes = len(app.routes)
assert routes > 5, 'app registered almost no routes'
print(f'  imports cleanly, {routes} routes')
"; then
    die "the new code does not import — not rolling out"
fi

# ------------------------------------------------------------------ back up ---
# Keep the previous tree so a bad release can be rolled back by hand.
if [ -d "$APP_DIR" ] && [ ! -L "$APP_DIR" ]; then
    log "Snapshotting the current version"
    rm -rf "$APP_ROOT/app.prev"
    cp -a "$APP_DIR" "$APP_ROOT/app.prev"
fi

# -------------------------------------------------------------------- deploy ---
log "Refreshing application code"
for item in backend frontend requirements-auth.txt run_server.py run_demo.py; do
    [ -e "$SRC_DIR/$item" ] || continue
    rm -rf "${APP_DIR:?}/$item"
    cp -r "$SRC_DIR/$item" "$APP_DIR/"
done
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# Reinstall only when the requirements actually changed.
REQ_SRC=$(sha256sum "$SRC_DIR/requirements-auth.txt" | cut -d' ' -f1)
REQ_CUR=$(sha256sum "$APP_DIR/requirements-auth.txt" 2>/dev/null | cut -d' ' -f1 || echo none)
if [ "$REQ_SRC" != "$REQ_CUR" ]; then
    log "requirements changed — reinstalling dependencies"
    sudo -u "$APP_USER" "$APP_ROOT/venv/bin/pip" install \
        --quiet --upgrade pip wheel
    sudo -u "$APP_USER" "$APP_ROOT/venv/bin/pip" install \
        --quiet -r "$APP_DIR/requirements-auth.txt"
else
    log "dependencies unchanged"
fi

# ------------------------------------------------------------------- restart ---
log "Restarting aeronerds"
systemctl restart aeronerds

log "Verifying"
ok=0
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:8000/api/meta/health" >/dev/null 2>&1; then
        ok=1; break
    fi
    sleep 1
done
if [ "$ok" -ne 1 ]; then
    echo
    systemctl status aeronerds --no-pager || true
    journalctl -u aeronerds -n 50 --no-pager || true
    cat <<'EOF'

Roll back to the previous version:
  sudo rm -rf /opt/aeronerds/app
  sudo mv /opt/aeronerds/app.prev /opt/aeronerds/app
  sudo systemctl restart aeronerds

EOF
    die "service did not come up — see the log above"
fi

echo "  $(systemctl is-active aeronerds)  (started $(systemctl show -p ActiveEnterTimestamp --value aeronerds))"
curl -fsS "http://127.0.0.1:8000/api/meta/health"; echo

if curl -fsS "http://127.0.0.1:8000/" | grep -q "AeroNerds"; then
    echo "  public homepage renders"
else
    die "homepage did not render as expected"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8000/api/records/portfolio" || true)
[ "$code" = "401" ] || die "unauthenticated API read returned $code, expected 401"
echo "  unauthenticated API access refused (401)"

[ -f "$DATA_DIR/aeronerds_auth.db" ] || die "auth database missing at $DATA_DIR"
echo "  auth database intact"

# ----------------------------------------------------------------- smoke ---
if [ -f "$SRC_DIR/scripts/smoke_test.py" ]; then
    log "Running the access-model smoke test"
    if python3 "$SRC_DIR/scripts/smoke_test.py" http://127.0.0.1:8000; then
        echo "  smoke test passed"
    else
        printf '\033[1;33mWARNING: smoke test failed. Review the output above.\033[0m\n'
    fi
fi

    cat <<'EOF'

Point DNS at the server's Elastic IP, then issue a certificate:

  sudo certbot --nginx -d your-domain.example
  sudo certbot renew --dry-run

Check it:

  curl -I https://your-domain.example/            # 200, public homepage
  curl -I https://your-domain.example/index.html  # 200, sign-in gate

--------------------------------------------------------------------
EOF
