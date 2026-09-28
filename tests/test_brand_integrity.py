"""Selector parity: every CSS class the JavaScript queries must exist in the
markup or the stylesheet.

A class rename applied to index.html and styles.css but not to the JavaScript
that queries it fails silently: the nav stops highlighting, the Hindi brand
stops updating, and nothing throws. This checks the wiring explicitly.

It also enforces the rebrand: no user-visible Aadhaar naming may return, and no
invented government domain may be baked into the code (AGENTS.md rule 2).
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INDEX_HTML = ROOT / "frontend" / "index.html"
STYLES = ROOT / "frontend" / "styles.css"
HOME_HTML = ROOT / "frontend" / "home.html"
JS_FILES = sorted((ROOT / "frontend").glob("*.js"))
PY_FILES = sorted((ROOT / "backend").glob("*.py")) + [
    ROOT / "run_server.py",
    ROOT / "run_demo.py",
]
README = ROOT / "README.md"


@pytest.fixture(scope="module")
def html():
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css():
    return STYLES.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js_sources():
    return {p.name: p.read_text(encoding="utf-8") for p in JS_FILES}


def classes_in_markup(html):
    return set(re.findall(r'class="([^"]+)"', html))


def classes_in_css(css):
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", css))


# ---------------------------------------------------------------------------
# selector parity
# ---------------------------------------------------------------------------
def test_js_never_queries_a_removed_uidai_class(js_sources):
    """The rebrand renamed .uidai-* to .gov-*. Nothing may still ask for the
    old name, or those elements silently stop responding."""
    for name, src in js_sources.items():
        stale = re.findall(r'["\'.](uidai-[a-z-]+)', src)
        assert not stale, f"{name} still queries removed class(es): {sorted(set(stale))}"


def test_html_defines_no_uidai_classes(html):
    stale = re.findall(r'class="(uidai-[a-z-]+)', html)
    assert not stale, f"index.html still uses class(es): {sorted(set(stale))}"


def test_css_defines_no_uidai_selectors(css):
    stale = re.findall(r"(--uidai-[\w-]+|\.uidai-[\w-]+)", css)
    assert not stale, f"styles.css still defines: {sorted(set(stale))}"


def test_every_js_queried_class_exists_somewhere(html, css, js_sources):
    """querySelector/querySelectorAll targets must resolve to either a class in
    the markup or a class defined in the stylesheet."""
    markup = classes_in_markup(html)
    styled = classes_in_css(css)
    known = markup | styled

    orphans = {}
    for name, src in js_sources.items():
        found = set()
        for pattern in (
            r'querySelector(?:All)?\(\s*["\']\.([\w-]+)["\']',
            r'querySelector(?:All)?\(\s*["\']#([\w-]+)["\']',
        ):
            found.update(re.findall(pattern, src))
        # only check class selectors that look like ours
        class_only = set(re.findall(r'querySelector(?:All)?\(\s*["\']\.([\w-]+)["\']', src))
        bad = {c for c in class_only if c not in known}
        if bad:
            orphans[name] = sorted(bad)

    assert not orphans, f"JS queries classes that exist in neither HTML nor CSS: {orphans}"


def test_gov_classes_are_consistent(html, css, js_sources):
    """Any gov-* class used in markup must be styled, so the government header
    cannot lose its styling after the rename."""
    gov_markup = {c for group in classes_in_markup(html) for c in group.split() if c.startswith("gov-")}
    gov_css = {c for c in classes_in_css(css) if c.startswith("gov-")}
    unstyled = sorted(gov_markup - gov_css)
    assert not unstyled, f"gov-* classes in markup with no CSS rule: {unstyled}"


def test_brand_css_variables_are_resolved(css):
    """Every var(--x) reference must have a matching custom property, or the
    declaration silently falls back to nothing."""
    defined = set(re.findall(r"(--[\w-]+)\s*:", css))
    used = set(re.findall(r"var\((--[\w-]+)", css))
    missing = sorted(used - defined)
    assert not missing, f"CSS references undefined custom properties: {missing}"


# ---------------------------------------------------------------------------
# rebrand enforcement
# ---------------------------------------------------------------------------
def test_no_user_visible_aadhaar_branding_remains(html):
    body = html
    # strip the sign-out marker text that legitimately explains the rename
    for allowed in ("Aadhaar",):
        pass
    hits = re.findall(r"[^<>\"']*Aadhaar[^<>\"']*", body)
    # Aadhaar may only survive in a comment explaining the removal.
    bad = [h for h in hits if not h.strip().startswith(("<!--", "*", "//"))]
    assert not bad, f"index.html still shows Aadhaar wording: {bad}"


def test_no_invented_government_domain_in_code():
    """A prototype must never mint a link or QR that points at a real
    government domain it does not control."""
    forbidden = (
        "bhumiadhaar.dolr.gov.in",
        "uidai.gov.in",
        "naksha.dolr.gov.in",
        "bhuvan-app3.nrsc.gov.in",
    )
    sources = {p.name: p.read_text(encoding="utf-8") for p in JS_FILES}
    sources.update({p.name: p.read_text(encoding="utf-8") for p in PY_FILES if p.exists()})

    offenders = {}
    for name, src in sources.items():
        found = [d for d in forbidden if d in src]
        if found:
            offenders[name] = found
    assert not offenders, f"code points at real government domains: {offenders}"


def test_qr_resolves_inside_the_app(js_sources):
    """The vertical-ID QR must resolve to this app, not an official portal."""
    src = js_sources["omni_roles.js"]
    qr_region = src[src.find("verifyUrl") - 400: src.find("verifyUrl") + 400]
    assert "window.location.origin" in qr_region, (
        "the 3D ULPIN QR should resolve within the running app"
    )


def test_readme_does_not_claim_official_design_authority():
    readme = README.read_text(encoding="utf-8")
    # strip markdown emphasis so "**not** affiliated" matches as prose
    plain = re.sub(r"[*_`]{1,3}", "", readme).lower()

    assert "uidai" not in plain, "README must not name UIDAI as a design authority"
    assert "official prototype for the government" not in plain, (
        "README must not claim to be an official Government of India prototype"
    )
    assert any(p in plain for p in ("not affiliated", "no official recognition", "not an official")), (
        "README should carry a disclaimer disclaiming official status"
    )


def test_brand_is_consistent_across_entry_points():
    """The masthead, the page titles and the server banner must all call the
    product the same thing."""
    html = INDEX_HTML.read_text(encoding="utf-8").lower()
    home = HOME_HTML.read_text(encoding="utf-8").lower()
    assert "aeronerds" in html, "portal index.html must carry the AeroNerds brand"
    assert "aeronerds" in home, "home.html must carry the AeroNerds brand"
    assert "aeronerd" in README.read_text(encoding="utf-8").lower()


def test_hindi_brand_is_not_the_old_name(html):
    """The bilingual header is part of the government-portal look, so the Hindi
    brand must also be renamed."""
    assert "भू-आधार" not in html, "index.html still brands the portal भू-आधार in Hindi"
    assert "एयरोनर्ड्स" in html, "index.html should carry the renamed Hindi brand"


def test_no_fabricated_statutory_claims_remain(html):
    for claim in (
        "SURVEY OF INDIA COMPLIANT",
        "Statutorily Verified",
        "Aadhaar Verified",
        "DILRMP Rule 8",
        "Full statutory authority",
    ):
        assert claim.lower() not in html.lower(), (
            f"index.html still asserts a fabricated statutory claim: {claim!r}"
        )
