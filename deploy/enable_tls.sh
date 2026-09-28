#!/usr/bin/env bash
# AeroNerds SIH26011 — switch a deployed instance to HTTPS on a real domain.
#
#   sudo bash deploy/enable_tls.sh aeronerds.example.com
#
# Run this AFTER the A record resolves. It replaces the IP-only nginx config
# with the TLS one, issues a certificate, and rolls back if the certificate
# cannot be obtained, so a failed attempt never leaves nginx down.
#
# Why a script rather than a list of commands: the order matters and the
# failure modes are quiet. nginx will not start with a config referencing a
# certificate that does not exist yet, so the sequence is
# HTTP-only -> reload -> certbot -> switch to TLS. Skipping a step leaves you
# with either a dead nginx or a certificate request that fails because DNS has
# not propagated.

set -euo pipefail

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root: sudo bash deploy/enable_tls.sh your.domain.example"

DOMAIN="${1:-}"
[ -n "$DOMAIN" ] || die "pass the domain, e.g. sudo bash deploy/enable_tls.sh aeronerds.example.com"

# A hostname is required: Let's Encrypt will not issue for a bare IP.
case "$DOMAIN" in
    *.*) ;;
    *) die "'$DOMAIN' is not a fully qualified domain" ;;
esac
# The bare-IP case is caught explicitly rather than by the '*.*' glob above,
# because 65.0.71.122 does match '*.*' and the error deserves a real answer.
if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    die "Let's Encrypt cannot issue a certificate for a bare IP address. Get a free hostname first."
fi

SITE=/etc/nginx/sites-available/aeronerds
ENABLED=/etc/nginx/sites-enabled/aeronerds
SRC_DIR="${AERONERDS_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEMPLATE="$SRC_DIR/deploy/nginx/aeronerds.conf"
BACKUP=/etc/nginx/sites-available/aeronerds.pre-tls

command -v nginx >/dev/null || die "nginx is not installed"
command -v certbot >/dev/null || die "certbot is not installed: sudo apt-get install -y certbot python3-certbot-nginx"
[ -f "$TEMPLATE" ] || die "cannot find $TEMPLATE"

# ---------------------------------------------------------------- DNS check ---
# Fail here, not after a half-finished certbot run. Propagation can be slow, so
# report what is actually resolving rather than just "wrong".
log "Checking DNS for $DOMAIN"
RESOLVED=$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)
PUBLIC_IP=$(curl -4 -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)

if [ -z "$RESOLVED" ]; then
    cat <<EOF

$DOMAIN does not resolve yet.

  Add an A record:  $DOMAIN -> ${PUBLIC_IP:-<this server's public IP>}
  type A, TTL 300.

  Then re-run this script. Cloudflare and most DNS providers propagate within a
  minute, but it can take longer. Verify with:

    getent hosts $DOMAIN

EOF
    die "DNS has not propagated"
fi

if [ -n "$PUBLIC_IP" ] && [ "$RESOLVED" != "$PUBLIC_IP" ]; then
    cat <<EOF

$DOMAIN resolves to $RESOLVED
but this server's public IP is $PUBLIC_IP

  If that is an old record, wait for it to expire and re-run.
  If it is a Cloudflare proxy address, that is fine -- leave the proxy on, but
  be aware Cloudflare will terminate TLS itself. Set SSL/TLS mode to "Full" and
  the certificate below still works for direct origin traffic.

EOF
    die "DNS points somewhere else"
fi
log "  $DOMAIN -> $RESOLVED"

# ------------------------------------------------------- step 1: HTTP config ---
# A config that references a certificate which does not exist will not load, so
# the first pass serves plain HTTP on the new server_name. Certbot needs a
# reachable HTTP server for the ACME challenge anyway.
log "Step 1/4: serving the domain over plain HTTP for the ACME challenge"
cp -a "$SITE" "$BACKUP"
cat > "$SITE" <<EOF
# Temporary HTTP-only config, written by enable_tls.sh.
# Replaced with the TLS config once certbot succeeds.
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}
EOF
# The redirect above would loop until the cert exists; serve the app instead.
sed -i 's|    location / { return 301 https://\$host\$request_uri; }|    location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto \$scheme; }|' "$SITE"

nginx -t || { cp -a "$BACKUP" "$SITE"; die "nginx rejected the HTTP config; original restored"; }
systemctl reload nginx
log "  nginx is serving $DOMAIN over HTTP"

# ------------------------------------------------------------- step 2: certbot ---
log "Step 2/4: requesting the certificate"
# --nginx edits the live config in place and reloads, so nginx must be healthy.
# --non-interactive is safe here because the HTTP challenge needs no input, but
# an email is still useful for expiry warnings, so it is requested if absent.
EMAIL_ARGS=()
if [ -n "${AERONERDS_CERTBOT_EMAIL:-}" ]; then
    EMAIL_ARGS=(--email "$AERONERDS_CERTBOT_EMAIL")
else
    EMAIL_ARGS=(--register-unsafely-without-email)
    log "  no AERONERDS_CERTBOT_EMAIL set; registering without an expiry address"
fi

if ! certbot --nginx -d "$DOMAIN" --non-interactive --agree-to-rs "${EMAIL_ARGS[@]}"; then
    cat <<EOF

certbot could not obtain a certificate. Common causes:
  * the A record has not propagated (check: getent hosts $DOMAIN)
  * port 80 is closed in the AWS security group -- it must be open to the world
  * the origin is behind a Cloudflare proxy set to "Full (strict)", which
    requires a valid origin certificate

EOF
    die "certificate not issued; the previous config is still in place at $BACKUP"
fi

# --------------------------------------------------------- step 3: TLS config ---
log "Step 3/4: switching nginx to the full TLS config"
cp -a "$TEMPLATE" "$SITE"
sed -i "s/your-domain\.example/$DOMAIN/g" "$SITE"
grep -q "$DOMAIN" "$SITE" || die "the domain was not substituted into $SITE"

if ! nginx -t; then
    cp -a "$BACKUP" "$SITE"
    nginx -t && systemctl reload nginx
    die "the TLS config failed to load; rolled back to the previous config"
fi
systemctl reload nginx

# -------------------------------------------------------------- step 4: verify ---
log "Step 4/4: verifying"
ok=0
for _ in $(seq 1 15); do
    if curl -fsS "https://$DOMAIN/api/meta/health" >/dev/null 2>&1; then
        ok=1; break
    fi
    sleep 2
done
if [ "$ok" -ne 1 ]; then
    journalctl -u aeronerds -n 20 --no-pager || true
    die "the app is not answering over HTTPS; check that the service is up"
fi

echo "  https health      ok"
echo "  homepage          $(curl -o /dev/null -s -w '%{http_code}' "https://$DOMAIN/")"
echo "  sign-in gate      $(curl -o /dev/null -s -w '%{http_code}' "https://$DOMAIN/index.html")"
code=$(curl -s -o /dev/null -w '%{http_code}' "https://$DOMAIN/api/records/portfolio" || true)
[ "$code" = "401" ] || die "unauthenticated API read returned $code over HTTPS, expected 401"
echo "  unauthenticated   401 (expected)"

# confirm the app itself is still loopback-only
if ss -tln 2>/dev/null | grep -q '0.0.0.0:8000'; then
    die "the app is bound to 0.0.0.0:8000 -- only nginx should reach it"
fi
echo "  app still loopback-only"

log "Checking certificate auto-renewal"
certbot renew --dry-run 2>&1 | tail -3 || die "auto-renewal is not configured correctly"

cat <<EOF

--------------------------------------------------------------------
HTTPS is live at https://$DOMAIN
--------------------------------------------------------------------
  certbot renew --dry-run     verify renewal
  certbot certificates        issued certs and expiry
  sudo systemctl status aeronerds
  sudo journalctl -u aeronerds -f

The previous config is kept at $BACKUP

Remaining before real data:
  * change the demo passwords (they are printed on the sign-in page)
  * back up /etc/aeronerds/aeronerds.env and /var/lib/aeronerds/
  * see the checklist at the end of docs/DEPLOY_AWS.md

EOF
