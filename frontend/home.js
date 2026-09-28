/* AeroNerds SIH26011 — Official Government-Style Landing Page Behaviour.
   Handles:
   - Font resizing (A-, A, A+) and High Contrast mode toggle
   - Mobile navigation toggle
   - Seat deep-links for evaluator desks
   - Hero banner carousel controls
   - Quick search redirect to /index.html
   - Live count check that compares hardcoded stat band against shipped GeoJSON layers
*/

(function () {
    "use strict";

    // ---------- 1. Accessibility Controls: Font Resizer & Contrast ----------
    var btnDec = document.getElementById("btn-font-dec");
    var btnNorm = document.getElementById("btn-font-normal");
    var btnInc = document.getElementById("btn-font-inc");
    var btnContrast = document.getElementById("btn-contrast-toggle");

    if (btnDec && btnNorm && btnInc) {
        btnDec.addEventListener("click", function () {
            document.body.classList.remove("font-normal", "font-lg");
            document.body.classList.add("font-sm");
            btnDec.classList.add("active");
            btnNorm.classList.remove("active");
            btnInc.classList.remove("active");
        });
        btnNorm.addEventListener("click", function () {
            document.body.classList.remove("font-sm", "font-lg");
            document.body.classList.add("font-normal");
            btnNorm.classList.add("active");
            btnDec.classList.remove("active");
            btnInc.classList.remove("active");
        });
        btnInc.addEventListener("click", function () {
            document.body.classList.remove("font-sm", "font-normal");
            document.body.classList.add("font-lg");
            btnInc.classList.add("active");
            btnNorm.classList.remove("active");
            btnDec.classList.remove("active");
        });
    }

    if (btnContrast) {
        btnContrast.addEventListener("click", function () {
            document.body.classList.toggle("theme-contrast");
        });
    }

    // ---------- 2. Mobile Navigation ----------
    var toggle = document.getElementById("navToggle");
    var nav = document.getElementById("mainnav");

    if (toggle && nav) {
        toggle.addEventListener("click", function () {
            var open = nav.classList.toggle("open");
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        });

        nav.addEventListener("click", function (e) {
            if (e.target.tagName === "A") {
                nav.classList.remove("open");
                toggle.setAttribute("aria-expanded", "false");
            }
        });

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && nav.classList.contains("open")) {
                nav.classList.remove("open");
                toggle.setAttribute("aria-expanded", "false");
                toggle.focus();
            }
        });
    }

    // ---------- 3. Quick Search Bar ----------
    var searchInput = document.getElementById("quickSearchInput");
    var searchBtn = document.getElementById("btnQuickSearch");

    function executeQuickSearch() {
        if (!searchInput) return;
        var query = searchInput.value.trim();
        if (query) {
            window.location.href = "/index.html?search=" + encodeURIComponent(query);
        } else {
            window.location.href = "/index.html";
        }
    }

    if (searchBtn && searchInput) {
        searchBtn.addEventListener("click", executeQuickSearch);
        searchInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                executeQuickSearch();
            }
        });
    }

    // ---------- 4. Deep-link a requested seat into the login screen ----------
    // /index.html#seat=registrar pre-selects that demo account on the sign-in form
    var params = new URLSearchParams(window.location.search);
    var hash = window.location.hash.replace(/^#/, "");
    var seat = params.get("seat") || (hash.startsWith("seat=") ? hash.slice(5) : null);

    if (seat) {
        document.querySelectorAll("a[data-seat]").forEach(function (a) {
            var href = a.getAttribute("href") || "";
            if (!href.includes("seat=")) {
                a.setAttribute("href", href + (href.includes("?") ? "&" : "?") + "seat=" + encodeURIComponent(a.dataset.seat));
            }
        });
    }

    // ---------- 5. Ticker tab visibility pause ----------
    var track = document.querySelector(".ticker-track ul");
    if (track) {
        document.addEventListener("visibilitychange", function () {
            track.style.animationPlayState = document.hidden ? "paused" : "running";
        });
    }

    // ---------- 6. Live count check against the shipped GeoJSON ----------
    // Required by tests/test_homepage.py to prevent drift
    var REGIONS = [
        ["bhopal", "bhopal_buildings_3d.geojson", "bhopal_cadastral_parcels.geojson"],
        ["bengaluru", "buildings_3d.geojson", "cadastral_parcels_valid.geojson"],
        ["indore", "indore_buildings_3d.geojson", "indore_cadastral_parcels.geojson"],
        ["navi_mumbai", "navi_mumbai_buildings_3d.geojson", "navi_mumbai_cadastral_parcels.geojson"],
        ["mumbai_kalyan", "mumbai_kalyan_buildings_3d.geojson", "mumbai_kalyan_cadastral_parcels.geojson"],
        ["coimbatore", "coimbatore_buildings_3d.geojson", "coimbatore_cadastral_parcels.geojson"]
    ];

    function parseNum(text) {
        return parseInt(String(text).replace(/[^0-9]/g, ""), 10);
    }

    function fetchLayer(name) {
        return fetch(name, { cache: "no-store" })
            .then(function (r) { return r.ok ? r.json() : null; })
            .catch(function () { return null; });
    }

    function countFeatures(fc) {
        return fc && Array.isArray(fc.features) ? fc.features.length : 0;
    }

    Promise.all(REGIONS.map(function (r) {
        return Promise.all([
            fetchLayer("data/" + r[1]),
            fetchLayer("data/" + r[2])
        ]).then(function (pair) {
            return { buildings: countFeatures(pair[0]), parcels: countFeatures(pair[1]) };
        });
    })).then(function (rows) {
        var totals = rows.reduce(function (acc, r) {
            acc.buildings += r.buildings;
            acc.parcels += r.parcels;
            return acc;
        }, { buildings: 0, parcels: 0 });

        if (totals.buildings === 0 && totals.parcels === 0) return;

        document.querySelectorAll("[data-stat]").forEach(function (el) {
            var key = el.dataset.stat;
            if (key !== "buildings" && key !== "parcels") return;
            var shown = parseNum(el.textContent);
            if (shown && shown !== totals[key]) {
                el.style.color = "#fca5a5";
                el.title = "Data on disk now reports " + totals[key] + " — update home.html";
                el.dataset.stale = "true";
            }
        });
    }).catch(function () { /* static hosting: leave authored figures untouched */ });
})();
