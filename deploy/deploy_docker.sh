#!/usr/bin/env bash
# AeroNerds SIH26011 — build, roll out, and verify.
#
#   bash deploy/deploy_docker.sh
#
# Idempotent: safe to run again for every release. The SQLite auth volume is
# preserved, and the signing secret is generated once and kept in .env so that
# sessions survive a redeploy.

set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$APP_DIR"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------- secret key ---
# Session tokens are HMAC-signed with this. If it changes, every signed-in user
# is logged out. If it leaks, anyone can mint a valid session. So: generate it
# once into .env and never overwrite it.
if [ ! -f .env ]; then
    log "Generating a signing secret into .env (first run only)"
    umask 077
    printf 'AERONERDS_TOKEN_SECRET=%s\n' "$(openssl rand -hex 32)" > .env
    chmod 600 .env
    echo "  wrote .env — keep it out of git and back it up"
else
    log "Reusing the existing signing secret from .env"
fi

# shellcheck disable=SC1091
set -a; . ./.env; set +a
[ -n "${AERONERDS_TOKEN_SECRET:-}" ] || die "AERONERDS_TOKEN_SECRET is empty in .env"

if ! grep -qxF 'AERONERDS_TOKEN_SECRET' .env 2>/dev/null; then
    log "Adding .env to .gitignore"
    grep -qxF '.env' .gitignore 2>/dev/null || printf '\n# secrets\n.env\n' >> .gitignore
fi

# ----------------------------------------------------------------- config ---
command -v docker >/dev/null || die "docker is not installed — run deploy/setup_aws_docker.sh first"
docker compose version >/dev/null 2>&1 || die "docker compose v2 is required"

# ------------------------------------------------------------------ build ---
log "Building the image"
docker compose build --pull

# ------------------------------------------------------------------- roll ---
# Refuse to start if the image is obviously broken: boot it on a throwaway port
# and require a healthy auth endpoint before touching the live container.
log "Pre-flight check on the freshly built image"
PREFLIGHT_PORT=8099
docker rm -f aeronerds-preflight >/dev/null 2>&1 || true
docker run -d --name aeronerds-preflight \
    -e AERONERDS_TOKEN_SECRET="$AERONERDS_TOKEN_SECRET" \
    -p "127.0.0.1:${PREFLIGHT_PORT}:8000" \
    aeronerds/sih26011:latest >/dev/null

ok=0
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${PREFLIGHT_PORT}/api/meta/health" >/dev/null 2>&1; then
        ok=1; break
    fi
    sleep 1
done
docker logs aeronerds-preflight 2>&1 | tail -20 || true
docker rm -f aeronerds-preflight >/dev/null 2>&1 || true
[ "$ok" -eq 1 ] || die "new image never became healthy — not rolling out"

# ------------------------------------------------------------------ start ---
log "Rolling out"
docker compose up -d --remove-orphans

# ----------------------------------------------------------------- verify ---
log "Verifying the live container"
ok=0
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:8000/api/meta/health" >/dev/null 2>&1; then
        ok=1; break
    fi
    sleep 1
done
if [ "$ok" -ne 1 ]; then
    docker compose logs --tail=40
    die "container is not healthy after rollout"
fi

curl -fsS "http://127.0.0.1:8000/api/meta/health"; echo

# The public homepage must be the landing page, and the API must refuse
# unauthenticated reads. If either of these fails the deploy is not good.
if curl -fsS "http://127.0.0.1:8000/" | grep -q "AeroNerds"; then
    echo "  homepage serves the public landing page"
else
    die "homepage did not render as expected"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8000/api/records/portfolio" || true)
[ "$code" = "401" ] || die "unauthenticated API read returned $code, expected 401"
echo "  unauthenticated API access correctly refused (401)"

if [ -f scripts/smoke_test.py ]; then
    log "Running the access-model smoke test"
    if python3 scripts/smoke_test.py http://127.0.0.1:8000; then
        echo "  smoke test passed"
    else
        printf '\033[1;33mWARNING: smoke test failed. The app is up, but review the output above.\033[0m\n'
    fi
fi

cat <<'EOF'

--------------------------------------------------------------------
Deployed. Remaining manual steps
--------------------------------------------------------------------
1. Point DNS at the Elastic IP.
2. sudo certbot --nginx -d your-domain.example
3. Confirm:  https://your-domain.example/           public homepage
              https://your-domain.example/index.html sign-in gate

Keep .env safe. Losing it logs every user out; leaking it lets an
attacker mint valid sessions for any role.
EOF
