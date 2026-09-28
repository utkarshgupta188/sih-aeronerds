#!/usr/bin/env bash
# AeroNerds SIH26011 — native install, no Docker.
#
# Installs the portal as a systemd service on Ubuntu 24.04 with a dedicated
# unprivileged user, a virtualenv, and nginx in front.
#
#   sudo bash deploy/install.sh
#
# Re-runnable. It will not overwrite an existing signing secret, so running it
# again does not log every user out.
#
# Layout:
#   /opt/aeronerds/app            the code
#   /opt/aeronerds/venv           Python virtualenv
#   /var/lib/aeronerds            the SQLite auth database (only writable path)
#   /etc/aeronerds/aeronerds.env  the signing secret, mode 0600

set -euo pipefail

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root: sudo bash deploy/install.sh"

APP_USER=aeronerds
APP_ROOT=/opt/aeronerds
APP_DIR="$APP_ROOT/app"
DATA_DIR=/var/lib/aeronerds
CONF_DIR=/etc/aeronerds
ENV_FILE="$CONF_DIR/aeronerds.env"
DOMAIN="${AERONERDS_DOMAIN:-}"

# ------------------------------------------------------------------ checks ---
log "Checking prerequisites"
command -v python3 >/dev/null || die "python3 is not installed"
python3 - <<'PY' || die "Python 3.11+ is required"
import sys
sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
echo "  python3 $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:3])))')"

# Ubuntu 24.04 ships PEP 668, which blocks pip into the system interpreter.
# We use a venv instead, so this is only a warning.
if ! command -v apt-get >/dev/null; then
    die "this script targets a Debian/Ubuntu host (no apt-get found)"
fi

# python3-venv is required on Ubuntu; without it venv creation fails
if ! dpkg -s python3-venv >/dev/null 2>&1; then
    log "Installing python3-venv"
    apt-get update
    apt-get install -y python3-venv
fi

# ------------------------------------------------------------------- nginx ---
if ! command -v nginx >/dev/null 2>&1; then
    log "Installing nginx and certbot"
    apt-get update
    apt-get install -y nginx certbot python3-certbot-nginx
    systemctl enable --now nginx
else
    log "nginx already present"
fi

# -------------------------------------------------------------------- user ---
# A dedicated system user. The service never runs as root or as your login.
if ! id "$APP_USER" >/dev/null 2>&1; then
    log "Creating the $APP_USER system user"
    useradd --system --create-home --home-dir "$APP_ROOT" \
            --shell /usr/sbin/nologin "$APP_USER"
else
    log "user $APP_USER already exists"
fi

install -d -m 0755 -o "$APP_USER" -g "$APP_USER" "$APP_ROOT"
install -d -m 0750 -o "$APP_USER" -g "$APP_USER" "$DATA_DIR"
install -d -m 0750 -o "$APP_USER" -g "$APP_USER" "$CONF_DIR"

# -------------------------------------------------------------------- code ---
SRC_DIR="${AERONERDS_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
[ -d "$SRC_DIR/backend" ] || die "cannot find the application source (looked in $SRC_DIR)"

if [ ! -d "$APP_DIR/backend" ]; then
    log "Copying application to $APP_DIR"
    # copy only what the service needs; tests, docs and git history stay out
    install -d -m 0755 -o "$APP_USER" -g "$APP_USER" "$APP_DIR"
    for item in backend frontend requirements-auth.txt run_server.py run_demo.py; do
        cp -r "$SRC_DIR/$item" "$APP_DIR/"
    done
else
    log "Application already present at $APP_DIR — refreshing code in place"
    for item in backend frontend requirements-auth.txt run_server.py run_demo.py; do
        if [ -e "$SRC_DIR/$item" ]; then
            cp -r "$SRC_DIR/$item" "$APP_DIR/"
        fi
    done
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ------------------------------------------------------------------ venv ---
# Recreate when the requirements change, otherwise just refresh in place.
REQ_HASH_SRC=$(sha256sum "$SRC_DIR/requirements-auth.txt" | cut -d' ' -f1)
REQ_HASH_DST=$(sha256sum "$APP_DIR/requirements-auth.txt" 2>/dev/null | cut -d' ' -f1 || echo none)

if [ ! -d "$APP_ROOT/venv" ] || [ "$REQ_HASH_SRC" != "$REQ_HASH_DST" ]; then
    log "Creating the virtualenv"
    rm -rf "$APP_ROOT/venv"
    sudo -u "$APP_USER" python3 -m venv "$APP_ROOT/venv"
    log "Installing Python dependencies"
    # pins keep the install reproducible and avoid rebuilding GDAL wheels
    sudo -u "$APP_USER" "$APP_ROOT/venv/bin/pip" install \
        --quiet --upgrade pip wheel
    sudo -u "$APP_USER" "$APP_ROOT/venv/bin/pip" install \
        --quiet -r "$APP_DIR/requirements-auth.txt"
else
    log "Virtualenv is current"
    sudo -u "$APP_USER" "$APP_ROOT/venv/bin/pip" install \
        --quiet -r "$APP_DIR/requirements-auth.txt"
fi

# --------------------------------------------------------------- the secret ---
# Session tokens are HMAC-signed with this. If it changes, every signed-in user
# is logged out. If it leaks, anyone can mint a valid session for any role.
# So: generate once, keep it, never overwrite.
if [ -f "$ENV_FILE" ] && grep -q '^AERONERDS_TOKEN_SECRET=' "$ENV_FILE"; then
    log "Reusing the existing signing secret"
else
    log "Generating a signing secret into $ENV_FILE (first run only)"
    umask 077
    SECRET=$(openssl rand -hex 32)
    cat > "$ENV_FILE" <<EOF
# AeroNerds signing secret. Treat this like a private key.
#  * losing it logs out every session
#  * leaking it lets an attacker mint a session for any role
# Regenerate with: openssl rand -hex 32
AERONERDS_TOKEN_SECRET=$SECRET

# The auth/session SQLite database lives outside the app tree.
AERONERDS_AUTH_DB=$DATA_DIR/aeronerds_auth.db
EOF
    chown root:"$APP_USER" "$ENV_FILE"
    chmod 0640 "$ENV_FILE"
    echo "  backup this file — see docs/DEPLOY_AWS.md"
fi

# ---------------------------------------------------------------- systemd ---
log "Installing the systemd unit"
install -m 0644 "$SRC_DIR/deploy/aeronerds.service" /etc/systemd/system/aeronerds.service
systemctl daemon-reload
systemctl enable aeronerds

log "Restarting the service"
if ! systemctl restart aeronerds; then
    systemctl status aeronerds --no-pager || true
    journalctl -u aeronerds -n 40 --no-pager || true
    die "service failed to start"
fi

# ------------------------------------------------------------------ verify ---
log "Verifying the service"
ok=0
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:8000/api/meta/health" >/dev/null 2>&1; then
        ok=1; break
    fi
    sleep 1
done
if [ "$ok" -ne 1 ]; then
    systemctl status aeronerds --no-pager || true
    journalctl -u aeronerds -n 40 --no-pager || true
    die "service is not answering on 127.0.0.1:8000"
fi

echo "  systemd: $(systemctl is-active aeronerds)"
curl -fsS "http://127.0.0.1:8000/api/meta/health"; echo

# Two checks that catch the failure modes this service is most prone to.
if curl -fsS "http://127.0.0.1:8000/" | grep -q "AeroNerds"; then
    echo "  public homepage renders"
else
    die "homepage did not render as expected"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8000/api/records/portfolio" || true)
[ "$code" = "401" ] || die "unauthenticated API read returned $code, expected 401"
echo "  unauthenticated API access refused (401)"

# Confirm the database really is on the writable volume, not in the app tree.
# With ProtectSystem=strict a write to the app tree would fail outright, so a
# successful boot already implies this, but check the file is where we expect.
if [ -f "$DATA_DIR/aeronerds_auth.db" ]; then
    echo "  auth database at $DATA_DIR"
else
    die "expected the auth database at $DATA_DIR but it is not there"
fi

# ----------------------------------------------------------------- smoke ---
if [ -f "$SRC_DIR/scripts/smoke_test.py" ]; then
    log "Running the access-model smoke test"
    if python3 "$SRC_DIR/scripts/smoke_test.py" http://127.0.0.1:8000; then
        echo "  smoke test passed"
    else
        printf '\033[1;33mWARNING: smoke test failed. The service is up; review the output.\033[0m\n'
    fi
fi

# ------------------------------------------------------------------ nginx ---
cat <<EOF

--------------------------------------------------------------------
Application installed and running on 127.0.0.1:8000
--------------------------------------------------------------------
Service : aeronerds  (systemctl status aeronerds)
Logs    : journalctl -u aeronerds -f
Data    : $DATA_DIR/aeronerds_auth.db
Secret  : $ENV_FILE   <-- back this up

Next: put nginx in front.

  sudo cp $APP_DIR/deploy/nginx/aeronerds.conf /etc/nginx/sites-available/aeronerds 2>/dev/null \
    || sudo cp $SRC_DIR/deploy/nginx/aeronerds.conf /etc/nginx/sites-available/aeronerds
  sudo nano /etc/nginx/sites-available/aeronerds     # set server_name
  sudo ln -s /etc/nginx/sites-available/aeronerds /etc/nginx/sites-enabled/
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t && sudo systemctl reload nginx

Then point DNS at the server and issue a certificate:
  sudo certbot --nginx -d your-domain.example

EOF
