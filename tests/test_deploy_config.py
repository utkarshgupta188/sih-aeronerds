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
SETUP = ROOT / "deploy" / "setup_aws.sh"
DEPLOY = ROOT / "deploy" / "deploy.sh"
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


def test_setup_script_is_idempotent_and_scoped(setup_script):
    assert "set -euo pipefail" in setup_script
    assert "command -v docker" in setup_script, "re-running setup must be safe"
    assert "get.docker.com" not in setup_script, "install from the official apt repo, not a curl|sh script"


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
