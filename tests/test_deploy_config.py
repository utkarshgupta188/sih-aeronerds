"""Deployment artifacts must stay consistent with the application they ship.

A Dockerfile or compose file that references an environment variable the code
does not read fails *quietly*: the app boots, ignores the setting, and writes
its SQLite file somewhere the volume does not cover, so every deploy silently
loses users and sessions. Same for a CSP that omits the basemap host, which
breaks the map in a way that only shows up in a browser.

These checks are static, so they run without Docker installed.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"
NGINX = ROOT / "deploy" / "nginx" / "aeronerds.conf"
NGINX_IP = ROOT / "deploy" / "nginx" / "aeronerds-ip.conf"
# Two deployment paths, both covered. Native (systemd) is the default; the
# Docker path is retained because the setup guide documents both.
SETUP = ROOT / "deploy" / "setup_aws_docker.sh"
DEPLOY = ROOT / "deploy" / "deploy_docker.sh"
INSTALL = ROOT / "deploy" / "install.sh"
NATIVE_DEPLOY = ROOT / "deploy" / "deploy.sh"
UNIT = ROOT / "deploy" / "aeronerds.service"
DOCS = ROOT / "docs" / "DEPLOY_AWS.md"
REQS = ROOT / "requirements-auth.txt"
GITIGNORE = ROOT / ".gitignore"
SMOKE = ROOT / "scripts" / "smoke_test.py"


@pytest.fixture(scope="module")
def dockerfile():
    return DOCKERFILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def compose():
    return COMPOSE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def nginx():
    return NGINX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def nginx_ip():
    return NGINX_IP.read_text(encoding="utf-8")


def env_vars_read_by_code():
    """Every os.environ / os.getenv lookup in the shipped Python."""
    names = set()
    for path in list((ROOT / "backend").glob("*.py")) + [
        ROOT / "run_server.py",
        ROOT / "run_demo.py",
    ]:
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        names.update(re.findall(r'os\.environ\.get\(\s*["\']([A-Z0-9_]+)["\']', src))
        names.update(re.findall(r'os\.getenv\(\s*["\']([A-Z0-9_]+)["\']', src))
    return names


# ---------------------------------------------------------------------------
# the file must exist before anything else is worth asserting
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path",
    [DOCKERFILE, COMPOSE, NGINX, SETUP, DEPLOY, DOCS, REQS, SMOKE],
    ids=lambda p: p.name,
)
def test_artifact_exists(path):
    assert path.exists(), f"missing deployment artifact: {path.relative_to(ROOT)}"


# ---------------------------------------------------------------------------
# environment variables: the silent-failure class of bug
# ---------------------------------------------------------------------------
def test_every_env_var_set_by_deploy_is_read_by_the_code(dockerfile, compose):
    known = env_vars_read_by_code()
    assert known, "failed to detect any env var reads; the probe is wrong"

    set_by_dockerfile = set(re.findall(r"^\s*([A-Z][A-Z0-9_]+)=", dockerfile, re.M))
    set_by_compose = set(re.findall(r"^\s*([A-Z][A-Z0-9_]+):", compose, re.M))

    # PORT is a uvicorn/deployment convention rather than an app lookup
    allowed = {"PORT", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE", "PIP_NO_CACHE_DIR", "PIP_DISABLE_PIP_VERSION_CHECK"}

    unknown = (set_by_dockerfile | set_by_compose) - known - allowed
    assert not unknown, (
        f"deployment sets environment variable(s) the application never reads: "
        f"{sorted(unknown)}. A setting the code ignores fails silently."
    )


def test_auth_db_variable_name_matches_the_code(dockerfile, compose):
    """The SQLite path must use the exact variable backend/main.py reads."""
    code = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    m = re.search(r'os\.environ\.get\(\s*["\']([A-Z0-9_]*DB[A-Z0-9_]*)["\']', code)
    assert m, "could not find the auth DB env var in backend/main.py"
    var = m.group(1)

    assert var in dockerfile, f"Dockerfile never sets {var}"
    assert var in compose, f"docker-compose.yml never sets {var}"

    wrong = re.findall(r"AERONERDS_[A-Z_]*DB_PATH", dockerfile + compose)
    assert not wrong, (
        f"deployment uses AERONERDS_*DB_PATH but the code reads {var}; "
        "the database would be written outside the mounted volume"
    )


@pytest.fixture(scope="module")
def deploy():
    return DEPLOY.read_text(encoding="utf-8")


def test_token_secret_is_never_hardcoded(dockerfile, compose, deploy):
    """No 32+ hex-char literal may sit next to the secret name. The
    substitution form ${AERONERDS_TOKEN_SECRET:?...} is the one allowed
    pattern, because it forces the operator to supply the value."""
    for text, label in ((dockerfile, "Dockerfile"), (compose, "compose"), (deploy, "deploy.sh")):
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "?" in stripped or "openssl" in stripped:
                continue
            hit = re.search(
                r"AERONERDS_TOKEN_SECRET\s*[:=]\s*(?!\$\{)([\"']?)([^\s\"']*)", stripped
            )
            if not hit:
                continue
            value = hit.group(2)
            if not value:
                continue
            if re.fullmatch(r"[0-9a-fA-F]{32,}", value):
                pytest.fail(f"{label} hardcodes a signing secret: {stripped}")
            if re.fullmatch(r"\$[A-Za-z_{][\w{}:]*", value):
                continue
            # a shell test referencing the variable, e.g. [ -n "${VAR:-}" ]
            if stripped.startswith(("[", "test ")) or value.startswith(('"', "'")):
                continue
            pytest.fail(
                f"{label} assigns a literal value to AERONERDS_TOKEN_SECRET: {stripped}"
            )


def test_session_secret_is_required_not_defaulted(dockerfile, compose):
    """A default secret would let anyone mint a session for any role."""
    assert 'AERONERDS_TOKEN_SECRET=""' in dockerfile, (
        "Dockerfile should ship an empty secret so the deployment must supply one"
    )
    assert "AERONERDS_TOKEN_SECRET:?" in compose, (
        "compose must fail fast if AERONERDS_TOKEN_SECRET is unset"
    )


# ---------------------------------------------------------------------------
# requirements must cover the app's real imports
# ---------------------------------------------------------------------------
def test_requirements_cover_backend_imports():
    src = "\n".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "backend").glob("*.py")
    )
    imported = set(re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_][\w]*)", src, re.M))

    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    third_party = {m for m in imported if m not in stdlib}
    # local helpers that happen to match a module name
    third_party -= {"backend", "records", "users", "rbac", "security", "schemas"}

    reqs = REQS.read_text(encoding="utf-8").lower()
    missing = []
    for mod in sorted(third_party):
        key = mod.replace("_", "-")
        if key not in reqs and mod.lower() not in reqs:
            missing.append(mod)
    assert not missing, (
        f"backend/ imports {missing} but requirements-auth.txt does not list them; "
        "the container would fail to import on boot"
    )


def test_server_is_importable_without_heavy_geo_stack():
    """The portal must not drag in GeoPandas/GDAL/PyTorch, or the web image
    becomes gigabytes for no reason. Import names are checked, not just the
    literal strings, so 'rasterio' in a comment does not trip the test."""
    reqs = REQS.read_text(encoding="utf-8").lower()
    heavy = {
        "geopandas": "geopandas",
        "rasterio": "rasterio",
        "gdal": "gdal",
        "pytorch": "torch",
        "open3d": "open3d",
        "pdal": "pdal",
        "trimesh": "trimesh",
        "shapely": "shapely",
    }
    for mod, package in heavy.items():
        assert not re.search(rf"^\s*{re.escape(package)}\b", reqs, re.M), (
            f"{package} is a pipeline dependency and must not be in the web image"
        )


# ---------------------------------------------------------------------------
# nginx: correct, and it must not break the app it fronts
# ---------------------------------------------------------------------------
def test_nginx_proxies_to_the_loopback_port(nginx, compose):
    assert "127.0.0.1:8000" in nginx, "nginx must proxy to the loopback-bound app"
    # the app port must never be published publicly
    assert '"127.0.0.1:8000:8000"' in compose, (
        "compose must bind the app port to loopback so only the proxy can reach it"
    )
    assert "0.0.0.0:8000:8000" not in compose, "the app port must not be exposed to the internet"


def test_nginx_redirects_http_and_terminates_tls(nginx):
    assert "return 301 https://" in nginx, "plain HTTP must redirect to HTTPS"
    assert "ssl_certificate" in nginx
    assert "listen 443 ssl" in nginx
    for header in ("Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options"):
        assert header in nginx, f"missing security header {header}"


def test_nginx_csp_permits_every_host_the_portal_actually_loads(nginx):
    """A CSP that omits a real dependency silently breaks the map in the
    browser, which no server-side test would ever catch."""
    csp = re.search(r'Content-Security-Policy "([^"]+)"', nginx)
    assert csp, "no CSP header found"
    policy = csp.group(1)

    used = set()
    for rel in ("frontend/app.js", "frontend/index.html", "frontend/home.html"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        used.update(re.findall(r"https://([a-z0-9.-]+\.[a-z]{2,})", src))

    # external links in anchors are not fetched, so they need no CSP allowance
    not_fetched = {
        "www.openstreetmap.org", "bhuvan-app3.nrsc.gov.in",
        "naksha.dolr.gov.in", "surveyofindia.gov.in",
    }
    fetched = {h for h in used if h not in not_fetched}

    missing = sorted(h for h in fetched if h not in policy)
    assert not missing, (
        f"CSP does not allow host(s) the portal loads: {missing}. "
        "Add them to the relevant directive or the page breaks in the browser."
    )


def test_nginx_blocks_state_and_dotfiles(nginx):
    db_block = re.search(r"location\s+~\*\s+[\^~]*\\\.\(db\|sqlite", nginx)
    assert db_block, "nginx must refuse to serve the auth database"
    assert "-journal" in nginx, "the SQLite sidecar files must be blocked too"
    # .well-known is deliberately allowed for ACME, so a blanket dotfile deny
    # is wrong; the rule must carve it out
    dot = nginx[nginx.find("location ~ /\\."):]
    assert dot, "no dotfile rule found"
    assert "well-known" in dot, (
        "the dotfile rule must exempt .well-known, or certificate renewal breaks"
    )


def test_nginx_throttles_signin(nginx):
    assert "limit_req_zone" in nginx
    assert "/api/auth/login" in nginx, "the sign-in endpoint needs its own rate limit"
    login_block = nginx[nginx.find("location /api/auth/login"):][:400]
    assert "limit_req" in login_block, "the sign-in limit must actually be applied there"


# ---------------------------------------------------------------------------
# the IP-only variant, for an instance with no domain and therefore no TLS
# ---------------------------------------------------------------------------
def test_ip_config_exists():
    assert NGINX_IP.exists(), (
        "an instance reached by bare IP has no way to get a certificate, so it "
        "needs a config that serves over plain HTTP"
    )


def test_ip_config_serves_plain_http_only(nginx_ip):
    """It must not pretend to have TLS. A stray ssl_certificate line here would
    stop nginx from starting at all, since no certificate exists yet."""
    assert "listen 80" in nginx_ip

    # Compare directives only. A comment explaining why HSTS is absent must not
    # count as sending it, or this test can never be satisfied and gets "fixed"
    # by deleting the explanation.
    directives = [
        ln for ln in nginx_ip.splitlines() if not ln.strip().startswith("#")
    ]
    active = "\n".join(directives)

    assert "ssl_certificate" not in active, (
        "the IP-only config must not reference a certificate that does not exist"
    )
    assert "return 301 https://" not in active, (
        "redirecting to HTTPS would loop forever with no certificate to serve it"
    )
    # HSTS over plain HTTP is ignored by browsers, so claiming it is misleading
    assert "Strict-Transport-Security" not in active, (
        "do not send HSTS when there is no HTTPS; it is silently ignored and "
        "misrepresents the transport"
    )


def test_ip_config_catches_requests_by_ip(nginx_ip):
    """With no domain there is no hostname to match, so server_name must be the
    catch-all or nginx serves nothing for a request whose Host is the IP."""
    assert re.search(r"server_name\s+_", nginx_ip), (
        "the IP-only config needs 'server_name _' to match requests by IP"
    )
    assert "default_server" in nginx_ip, (
        "so this site answers even if another default vhost exists"
    )


def test_ip_config_keeps_the_protections_that_still_work(nginx_ip):
    """TLS is gone, so the rate limits and headers are the entire defence."""
    assert "limit_req_zone" in nginx_ip
    login_block = nginx_ip[nginx_ip.find("location /api/auth/login"):][:400]
    assert "limit_req" in login_block, (
        "without TLS the sign-in throttle is the only brake on credential "
        "stuffing, so it must survive"
    )
    for header in ("X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy"):
        assert header in nginx_ip, f"missing security header {header}"
    assert "server_tokens off" in nginx_ip, (
        "do not advertise the nginx version on an unauthenticated port"
    )


def test_ip_config_blocks_state_files(nginx_ip):
    """No TLS does not mean no database. The auth store must stay unservable."""
    assert re.search(r"location\s+~\*\s+[\^~]*\\\.\(db\|sqlite", nginx_ip), (
        "the IP-only config must still refuse to serve the auth database"
    )
    assert "-journal" in nginx_ip


def test_ip_config_proxies_to_loopback(nginx_ip):
    assert "127.0.0.1:8000" in nginx_ip, (
        "nginx must still proxy to the loopback-bound app"
    )
    assert "0.0.0.0:8000" not in nginx_ip


def test_ip_config_documents_its_insecurity(nginx_ip):
    """A future reader must not mistake this for a production config."""
    head = nginx_ip[: nginx_ip.find("server {")]
    assert "cleartext" in head.lower(), (
        "the config must state that credentials cross the network in cleartext"
    )
    assert "no TLS" in head or "cannot issue a certificate" in head, (
        "the config must explain why there is no HTTPS, so nobody 'fixes' it by "
        "assuming a certificate is just missing"
    )


def test_ip_config_has_the_same_csp_hosts_as_the_tls_one(nginx_ip, nginx):
    """Two copies of a CSP will drift. The portal loads the same basemap and 3D
    libs either way, so a host allowed in one must be allowed in the other."""
    def hosts(text):
        csp = re.search(r'Content-Security-Policy "([^"]+)"', text)
        return set(re.findall(r"https://[a-z0-9.*-]+", csp.group(1)))

    only_tls = hosts(nginx) - hosts(nginx_ip)
    assert not only_tls, (
        f"CSP hosts present in the TLS config but missing from the IP config: "
        f"{sorted(only_tls)}. The map breaks in the browser with no server-side "
        f"error to explain why."
    )


# ---------------------------------------------------------------------------
# scripts
# ---------------------------------------------------------------------------
def test_deploy_script_preserves_the_auth_volume(compose, deploy):
    assert "auth-db:/data" in compose, "the auth database must live on a named volume"
    # a redeploy must not run `down -v` or the volume would be discarded
    assert "down -v" not in deploy, "deploy.sh must never remove the auth volume"
    assert "docker compose down -v" not in deploy


def test_deploy_script_gates_on_a_preflight_check(deploy):
    """Rolling out an image that never becomes healthy is worse than not
    deploying at all."""
    assert "preflight" in deploy.lower()
    assert "--no-cache" not in deploy, "a forced cache miss is not a health check"


def test_deploy_script_generates_the_secret_once(deploy):
    assert "openssl rand -hex 32" in deploy, "the secret must be randomly generated"
    assert "chmod 600" in deploy, "the secret file must not be world-readable"
    # it must reuse an existing secret, not regenerate and invalidate sessions
    assert re.search(r"if \[ ! -f \.env \]", deploy), (
        "the secret must only be generated when .env is absent, so redeploys "
        "do not invalidate every session"
    )


def test_deploy_script_runs_the_smoke_test(deploy):
    assert "smoke_test" in deploy, "a deploy should verify the access model, not just that the port opens"


@pytest.fixture(scope="module")
def setup_script():
    return SETUP.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def install_script():
    return INSTALL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def native_deploy():
    return NATIVE_DEPLOY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def unit_file():
    return UNIT.read_text(encoding="utf-8")


def test_setup_script_is_idempotent_and_scoped(setup_script):
    assert "set -euo pipefail" in setup_script
    assert "command -v docker" in setup_script, "re-running setup must be safe"
    assert "get.docker.com" not in setup_script, "install from the official apt repo, not a curl|sh script"


# ---------------------------------------------------------------------------
# native (systemd) path — the default, and the one that needs no Docker
# ---------------------------------------------------------------------------
def test_native_path_exists_without_docker():
    for path in (INSTALL, NATIVE_DEPLOY, UNIT):
        assert path.exists(), f"the Docker-free path needs {path.name}"


def test_install_script_generates_the_secret_once(install_script):
    assert "openssl rand -hex 32" in install_script, (
        "the signing secret must be randomly generated"
    )
    # it must reuse an existing secret, or every reinstall logs all users out
    assert re.search(r"if \[ -f \"?\$ENV_FILE", install_script), (
        "the secret must only be generated when absent, so a re-run does not "
        "invalidate every session"
    )
    assert "chmod 0640" in install_script, (
        "the secret file must not be readable by other accounts"
    )


def test_install_script_verifies_the_service(install_script):
    assert "systemctl is-active" in install_script, (
        "the installer must confirm the service is up, not assume it"
    )
    assert "smoke_test" in install_script, (
        "the installer must run the access-model smoke test"
    )
    # a service that is listening but serving the wrong thing is the failure
    # mode that actually happens
    assert "401" in install_script, (
        "verify unauthenticated API access is refused"
    )


def test_native_deploy_keeps_a_rollback_copy(native_deploy):
    assert "app.prev" in native_deploy, (
        "a redeploy must keep the previous tree so a bad release can be undone"
    )
    assert "smoke_test" in native_deploy
    assert "curl" in native_deploy, "the deploy must gate on a health check"


def test_native_deploy_never_touches_the_secret_or_database(native_deploy):
    """A redeploy must not regenerate the secret or delete the auth database.
    Either would log out every user or destroy the session store."""
    assert "openssl rand" not in native_deploy, (
        "deploy.sh must not regenerate the signing secret"
    )
    assert "rm -rf /var/lib/aeronerds" not in native_deploy
    assert "rm -f /etc/aeronerds" not in native_deploy


def test_service_unit_runs_unprivileged(unit_file):
    assert re.search(r"^User=aeronerds", unit_file, re.M), (
        "the service must run as a dedicated user, not root"
    )
    assert "ProtectSystem=strict" in unit_file
    assert "NoNewPrivileges=true" in unit_file
    assert "PrivateTmp=true" in unit_file
    assert "Restart=always" in unit_file, "a crash should not leave a dead listener"


def test_service_unit_binds_loopback_only(unit_file):
    assert "127.0.0.1" in unit_file, (
        "nginx is the only thing that should reach the app; the port must not "
        "be exposed directly"
    )
    assert "0.0.0.0" not in unit_file


def test_service_unit_secret_is_not_inline(unit_file):
    """The secret lives in an EnvironmentFile, so `systemctl cat` — which
    often ends up pasted into bug reports — cannot leak it."""
    assert "EnvironmentFile=/etc/aeronerds/aeronerds.env" in unit_file
    assert "AERONERDS_TOKEN_SECRET" not in unit_file, (
        "the secret must not be written into the unit file"
    )


def test_service_unit_has_exactly_one_writable_path(unit_file):
    writable = re.findall(r"^ReadWritePaths=(\S+)", unit_file, re.M)
    assert writable == ["/var/lib/aeronerds"], (
        f"only the auth database directory should be writable, got {writable}"
    )
    env = (ROOT / "deploy" / "install.sh").read_text(encoding="utf-8")
    assert "AERONERDS_AUTH_DB=$DATA_DIR/aeronerds_auth.db" in env, (
        "the database must live on that writable volume, not in the app tree"
    )
    assert 'DATA_DIR=/var/lib/aeronerds' in env, (
        "the writable path in the unit and the installer must be the same"
    )


def test_unit_paths_are_created_by_the_installer(unit_file, install_script):
    """A unit referencing a directory the installer never creates fails at boot
    with a message that does not obviously point at the installer."""
    for path in re.findall(
        r"(?:WorkingDirectory|ExecStart|EnvironmentFile)=(\S+)", unit_file
    ):
        root = "/".join(path.split("/")[:3])
        assert root in install_script, (
            f"the unit references {path} but install.sh never creates {root}"
        )


def test_native_path_is_documented_first():
    doc = DOCS.read_text(encoding="utf-8")
    native_at = doc.find("install.sh")
    docker_at = doc.find("setup_aws_docker.sh")
    assert native_at != -1, "the Docker-free path must be documented"
    assert docker_at != -1, "the Docker path must stay documented"
    assert native_at < docker_at, (
        "the native path is the default, so it must be documented first"
    )


def test_setup_script_does_not_open_the_app_port(setup_script):
    """The firewall rules must not include 8000. A mention in prose explaining
    that it stays closed is fine, so check the ufw command lines specifically."""
    for line in setup_script.splitlines():
        stripped = line.strip()
        if "ufw" not in stripped:
            continue
        assert "8000" not in stripped, (
            f"firewall rule opens the app port: {stripped}"
        )
    assert "Nginx Full" in setup_script, "nginx (80/443) must be allowed"


# ---------------------------------------------------------------------------
# documentation and secret hygiene
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def gitignore():
    return GITIGNORE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def docs():
    return DOCS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def smoke():
    return SMOKE.read_text(encoding="utf-8")


def test_secrets_are_gitignored(gitignore):
    for entry in (".env", "aeronerds_auth.db", "*.sqlite", "*.sqlite3"):
        assert entry in gitignore, f"{entry} must be gitignored"


def test_deploy_docs_warn_about_the_demo_passwords(docs):
    lowered = docs.lower()
    assert "demo password" in lowered or "demo passwords" in lowered, (
        "the deployment guide must flag that the shipped passwords are public"
    )
    assert "before you go public" in lowered, "the guide needs a pre-production checklist"


def test_deploy_docs_use_the_correct_db_variable(docs):
    assert "AERONERDS_AUTH_DB" in docs or "auth-db" in docs


def test_smoke_test_covers_the_threats_that_matter(smoke):
    for label in (
        "no token -> portfolio denied",
        "blocked from other citizen",
        "may not adjudicate",
        "may not read audit log",
        "token is dead after logout",
    ):
        assert label in smoke, f"smoke test no longer checks: {label!r}"
