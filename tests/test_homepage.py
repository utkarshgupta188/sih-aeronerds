"""Public landing page: wiring, honesty and anti-fabrication checks.

The homepage publishes hard counts (12,887 footprints, 582 parcels, 185 AI
anomalies). A marketing page that quietly drifts from the shipped data is the
exact failure mode AGENTS.md rules 3 and 5 exist to prevent, so these tests
recompute every published figure from the real GeoJSON and compare.

They also assert the page does not impersonate a government authority, which
rule 2 forbids.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import records  # noqa: E402

HOME = ROOT / "frontend" / "home.html"
HOME_JS = ROOT / "frontend" / "home.js"
HOME_CSS = ROOT / "frontend" / "home.css"

REGION_LAYERS = {
    "bhopal": ("bhopal_buildings_3d.geojson", "bhopal_cadastral_parcels.geojson"),
    "bengaluru": ("buildings_3d.geojson", "cadastral_parcels_valid.geojson"),
    "indore": ("indore_buildings_3d.geojson", "indore_cadastral_parcels.geojson"),
    "navi_mumbai": ("navi_mumbai_buildings_3d.geojson", "navi_mumbai_cadastral_parcels.geojson"),
    "mumbai_kalyan": ("mumbai_kalyan_buildings_3d.geojson", "mumbai_kalyan_cadastral_parcels.geojson"),
    "coimbatore": ("coimbatore_buildings_3d.geojson", "coimbatore_cadastral_parcels.geojson"),
}


@pytest.fixture(scope="module")
def home_html():
    return HOME.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def home_prose(home_html):
    """Visible text with markup removed, so a phrase broken up by a <b> or a
    line wrap still matches. Prose assertions must run against this."""
    no_style = re.sub(r"<style[\s\S]*?</style>", " ", home_html, flags=re.I)
    no_script = re.sub(r"<script[\s\S]*?</script>", " ", no_style, flags=re.I)
    no_tags = re.sub(r"<[^>]+>", " ", no_script)
    return re.sub(r"\s+", " ", no_tags).lower()


def real_capabilities():
    """Every capability string the backend actually defines."""
    from backend import rbac

    return {
        v
        for k, v in vars(rbac).items()
        if k.startswith("CAP_") and isinstance(v, str)
    }


def stat_value(html, key):
    m = re.search(rf'data-stat="{key}"[^>]*>([\d,]+)<', html)
    assert m, f"home.html has no data-stat=\"{key}\""
    return int(m.group(1).replace(",", ""))


# ---------------------------------------------------------------------------
# the published numbers must equal the data on disk
# ---------------------------------------------------------------------------
def test_published_region_count_matches_manifest(home_html):
    assert stat_value(home_html, "regions") == len(records.available_regions())


def test_published_building_count_matches_geojson(home_html):
    total = 0
    for region in records.available_regions():
        b, _ = records.record_count(region)
        total += b
    assert stat_value(home_html, "buildings") == total, (
        "home.html advertises a building count that no longer matches the "
        "GeoJSON layers — update the stat band rather than letting it drift"
    )


def test_published_parcel_count_matches_geojson(home_html):
    total = 0
    for region in records.available_regions():
        _, p = records.record_count(region)
        total += p
    assert stat_value(home_html, "parcels") == total


def test_published_anomaly_count_matches_ai_output(home_html):
    anomalies = 0
    for region in records.available_regions():
        for _bid, feat in records.building_index(region).items():
            if (feat.get("properties") or {}).get("ai_anomaly_flag"):
                anomalies += 1
    assert stat_value(home_html, "anomalies") == anomalies


def test_every_layer_named_in_home_js_exists():
    """home.js re-reads the layers to detect drift; a renamed file would
    silently disable the check rather than fail loudly."""
    js = HOME_JS.read_text(encoding="utf-8")
    for region, (bfile, pfile) in REGION_LAYERS.items():
        assert bfile in js, f"home.js does not reference {bfile}"
        assert pfile in js, f"home.js does not reference {pfile}"
        assert (ROOT / "frontend" / "data" / bfile).exists(), f"{bfile} missing from data/"
        assert (ROOT / "frontend" / "data" / pfile).exists(), f"{pfile} missing from data/"
        assert region in js, f"home.js omits region {region}"


# ---------------------------------------------------------------------------
# the verification-status sentence must match the real evidence coverage
# ---------------------------------------------------------------------------
def test_verification_figures_in_prose_match_the_data(home_prose):
    """The stats note spells out the Bhopal+Bengaluru coverage. Every number it
    publishes must be the real combined count for that verification status."""
    combined = {}
    for region in ("bhopal", "bengaluru"):
        for _bid, feat in records.building_index(region).items():
            status = (feat.get("properties") or {}).get("final_verification_status")
            if status:
                combined[status] = combined.get(status, 0) + 1

    total = sum(combined.values())
    assert f"{total:,}" in home_prose, (
        f"home.html should state that {total:,} buildings carry the full "
        "evidence-fusion output"
    )

    for status, n in combined.items():
        assert f"{n:,}" in home_prose, (
            f"home.html should state {n:,} {status} across the gated regions; "
            f"actual combined count is {n:,}"
        )


def test_regions_without_the_ai_gate_are_disclosed(home_prose):
    """Only Bhopal and Bengaluru carry ai_anomaly_flag / final_verification_status.
    The page must not imply the other four went through the same gate."""
    gated = {"bhopal", "bengaluru"}
    ungated = set(records.available_regions()) - gated
    assert ungated, "expected some regions to lack the AI gate"

    for region in ungated:
        idx = records.building_index(region)
        sample = next(iter(idx.values()))
        assert "ai_anomaly_flag" not in (sample.get("properties") or {})

    assert "bhopal" in home_prose and "bengaluru" in home_prose
    assert "earlier-stage" in home_prose or "earlier stage" in home_prose


# ---------------------------------------------------------------------------
# rule 2: no impersonation of a real authority
# ---------------------------------------------------------------------------
def test_page_does_not_brand_itself_as_a_real_government_authority(home_html, home_prose):
    """UIDAI may appear only inside the disclaimer that disclaims any link to
    it. Anywhere else, the page is impersonating a real authority."""
    disclaimer = re.search(
        r'<div class="footer-disclaimer">([\s\S]*?)</div>\s*</div>', home_html
    )
    assert disclaimer, "home.html must keep a footer disclaimer block"

    outside = home_html.replace(disclaimer.group(1), "")
    for forbidden in ("uidai", "uidai.gov.in", "unique aadhaar number"):
        assert forbidden not in outside.lower(), (
            f"home.html must not present itself as {forbidden!r} outside the "
            "disclaimer; rule 2 forbids claiming official recognition"
        )
    assert "uidai" in home_prose  # disclaimed, in the footer


def test_page_carries_an_explicit_non_official_disclaimer(home_prose):
    for phrase in (
        "not affiliated",
        "does not create",
        "proposals for human verification",
        "operated on behalf of",
    ):
        assert phrase in home_prose, f"disclaimer should state {phrase!r}"


def test_page_refuses_legal_and_tax_claims(home_prose):
    """Statutory facts must be declared NOT_DETERMINABLE, not asserted."""
    for item in ("legal title", "tax dues", "encumbrance"):
        assert item in home_prose, f"home.html should address {item}"
    assert "not determinable" in home_prose


def test_page_does_not_claim_height_gives_exact_floor_counts(home_prose):
    assert "never presented as an exact floor count" in home_prose
    assert "dsm" in home_prose and "dem" in home_prose


# ---------------------------------------------------------------------------
# wiring
# ---------------------------------------------------------------------------
def test_homepage_is_self_contained(home_html):
    for asset in ('href="home.css', 'src="home.js'):
        assert asset in home_html, f"home.html must load {asset}"
    assert (ROOT / "frontend" / "home.css").exists()
    assert (ROOT / "frontend" / "home.js").exists()


def test_homepage_links_to_the_authenticated_portal(home_html):
    assert 'href="/index.html"' in home_html


def test_service_cards_expose_all_four_seats(home_html):
    from backend.rbac import ROLES

    for role_id in ROLES:
        assert f'data-seat="{role_id}"' in home_html, (
            f"no service card links to the {role_id} seat"
        )


def service_cards(html):
    """Yield (role_id, [capabilities]) for each service card, scoped correctly
    to a single <article> so a card cannot borrow its neighbour's capabilities."""
    for block in re.findall(r'<article class="service">([\s\S]*?)</article>', html):
        seat = re.search(r'data-seat="([a-z0-9_]+)"', block)
        if not seat:
            continue
        caps = re.findall(r'<span class="cap">([a-z0-9:_]+)</span>', block)
        yield seat.group(1), caps


def test_service_caps_match_the_backend_capability_matrix(home_html):
    """Each service card advertises capabilities. They must be real, and the
    role whose card lists one must actually hold it."""
    from backend.rbac import ROLES

    published = set(re.findall(r'<span class="cap">([a-z0-9:_]+)</span>', home_html))
    unknown = published - real_capabilities()
    assert not unknown, f"home.html advertises capabilities that do not exist: {unknown}"

    cards = list(service_cards(home_html))
    assert len(cards) == len(ROLES), (
        f"expected one service card per role, found {len(cards)} for {len(ROLES)} roles"
    )

    for role_id, caps in cards:
        assert role_id in ROLES, f"service card points at unknown role {role_id!r}"
        held = set(ROLES[role_id].capabilities)
        for cap in caps:
            assert cap in held, (
                f"card for '{role_id}' advertises {cap!r}, which that role does not hold"
            )
        assert caps, f"card for '{role_id}' lists no capabilities"


def test_service_cards_cover_every_capability(home_html):
    """No capability may exist in the matrix without appearing on the page;
    otherwise an evaluator never learns the role can do it."""
    from backend.rbac import ROLES

    shown = set(re.findall(r'<span class="cap">([a-z0-9:_]+)</span>', home_html))
    defined = {c for v in ROLES.values() for c in v.capabilities}
    missing = defined - shown
    assert not missing, f"capabilities absent from the homepage: {sorted(missing)}"


def test_nav_targets_all_exist(home_html):
    ids = set(re.findall(r'id="([a-zA-Z0-9_-]+)"', home_html))
    for href in re.findall(r'href="#([a-zA-Z0-9_-]+)"', home_html):
        assert href in ids, f"nav link #{href} has no matching element"


def test_emoji_does_not_break_markup(home_html):
    """The crest/flag glyphs are literal UTF-8 emoji; make sure the file
    declares an encoding so they never render as mojibake."""
    assert 'charset="utf-8"' in home_html.lower()
    # ZWJ sequences must not have been split by an editor
    assert "\ufffd" not in home_html, "home.html contains a replacement character"


def test_page_is_accessible_basics(home_html):
    assert "<html lang=" in home_html.lower()
    assert 'name="viewport"' in home_html
    assert "skip-link" in home_html
    assert "<main" in home_html and "</main>" in home_html
    # interactive rows expose a real button element, not a bare div
    assert "<button" in home_html
