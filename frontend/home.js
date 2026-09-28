/* AeroNerds SIH26011 — landing page behaviour.
   Deliberately tiny: mobile nav, seat deep-links, and a live count check that
   compares the hardcoded stat band against the shipped GeoJSON so a data
   change on disk is visible on the page instead of silently going stale. */

(function () {
    "use strict";

    // ---------- mobile navigation ----------
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

    // ---------- deep-link a requested seat into the login screen ----------
    // /index.html#seat=registrar pre-selects that demo account on the sign-in
    // form, so an evaluator can jump straight to the desk being discussed.
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

    // ---------- close the ticker when the tab is hidden ----------
    var track = document.querySelector(".ticker-track ul");
    if (track) {
        document.addEventListener("visibilitychange", function () {
            track.style.animationPlayState = document.hidden ? "paused" : "running";
        });
    }

    // ---------- live count check against the shipped GeoJSON ----------
    // The stat band is authored by hand so the page renders instantly with no
    // network round-trip. This check re-reads the real layers and annotates any
    // figure that no longer matches, rather than letting the page claim a
    // number the data no longer supports.
    // region -> [buildings layer, cadastral parcels layer], matching the real
    // filenames on disk. Bengaluru is the unprefixed legacy pair.
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
