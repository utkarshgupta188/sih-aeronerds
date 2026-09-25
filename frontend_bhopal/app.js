document.addEventListener("DOMContentLoaded", function () {
    let parcelsData = null;
    let bldgsData = null;
    let isSatellite = false;
    let isLightMode = false;
    let auditLogs = [];
    let currentFeatureId = null;
    let vegHighlightOn = false;

    // --- Additive: colour expressions for the "highlight likely vegetation" mode ---
    // BASE_COLOR_EXPR is an exact copy of the default buildings-3d-layer colour
    // expression, used only to restore it when the vegetation highlight is turned off.
    const BASE_COLOR_EXPR = [
        "case",
        ["==", ["feature-state", "reviewer_status"], "APPROVE"], "#10b981",
        ["==", ["feature-state", "reviewer_status"], "CORRECT"], "#3b82f6",
        ["==", ["feature-state", "reviewer_status"], "REJECT"], "#ef4444",
        ["==", ["feature-state", "reviewer_status"], "UNRESOLVED"], "#f59e0b",
        [
            "match", ["get", "3d_representation_status"],
            "EXACT STRUCTURED 3D", "#3b82f6",
            "HEIGHT-DERIVED MASS", "#10b981",
            "2D FOOTPRINT ONLY", "#f59e0b",
            [
                "match", ["get", "match_status_2d"],
                "CONTAINED", "#10b981",
                "MAJORITY", "#f59e0b",
                "BOUNDARY_OVERLAP", "#ef4444",
                "#64748b"
            ]
        ]
    ];
    // Vegetation evidence (spatially-resolved pattern):
    //   green  = low / surrounding vegetation (building surface is clear)
    //   amber  = edge / internal / mixed vegetation (verify)
    //   red    = vegetation dominant (elevation may be canopy)
    //   grey   = resolution-limited / not determinable
    // Older flat values (LOW/MIXED/STRONG_VEGETATION) are kept for back-compat.
    // Reviewer overrides still win so audited buildings keep their status colour.
    const VEG_COLOR_EXPR = [
        "case",
        ["==", ["feature-state", "reviewer_status"], "APPROVE"], "#10b981",
        ["==", ["feature-state", "reviewer_status"], "CORRECT"], "#3b82f6",
        ["==", ["feature-state", "reviewer_status"], "REJECT"], "#ef4444",
        ["==", ["feature-state", "reviewer_status"], "UNRESOLVED"], "#f59e0b",
        [
            "match", ["get", "vegetation_evidence"],
            ["LOW_VEGETATION", "SURROUNDING_VEGETATION"], "#10b981",
            ["EDGE_VEGETATION", "INTERNAL_VEGETATION", "MIXED_VEGETATION"], "#f59e0b",
            ["VEGETATION_DOMINANT", "STRONG_VEGETATION"], "#ef4444",
            ["RESOLUTION_LIMITED", "NODATA", "NOT_DETERMINABLE", "NOT_COMPUTED"], "#64748b",
            "#475569"
        ]
    ];

    // --- Multi-Region Pilot Configuration ---
    const REGION_CONFIGS = {
        bhopal: {
            name: "Bhopal (OpenCity KML)",
            badge: "Bhopal Pilot (85 Wards)",
            center: [77.4180, 23.2510],
            zoom: 15.2,
            pitch: 60,
            bearing: -15,
            parcelsUrl: "data/cadastral_parcels_valid.geojson",
            bldgsUrl: "data/buildings_3d.geojson"
        },
        bengaluru: {
            name: "Bengaluru Urban",
            badge: "Bengaluru Pilot",
            center: [77.6200, 12.9300],
            zoom: 15.0,
            pitch: 60,
            bearing: -20,
            parcelsUrl: "data/cadastral_parcels_valid.geojson",
            bldgsUrl: "data/buildings_3d.geojson"
        }
    };

    const urlParams = new URLSearchParams(window.location.search);
    const activeRegionKey = urlParams.get("region") || "bhopal";
    const activeRegion = REGION_CONFIGS[activeRegionKey] || REGION_CONFIGS.bhopal;

    // Synchronize Region Selector UI
    const regionSelectElem = document.getElementById("region-selector");
    if (regionSelectElem) {
        regionSelectElem.value = activeRegionKey;
        regionSelectElem.addEventListener("change", function(e) {
            const selected = e.target.value;
            window.location.href = window.location.pathname + "?region=" + selected;
        });
    }

    const cityBadgeElem = document.getElementById("city-badge");
    if (cityBadgeElem) {
        cityBadgeElem.innerText = activeRegion.badge;
    }

    // 1. Initialize MapLibre GL JS centered on active region
    const map = new maplibregl.Map({
        container: "map",
        style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        center: activeRegion.center,
        zoom: activeRegion.zoom,
        pitch: activeRegion.pitch,
        bearing: activeRegion.bearing,
        antialias: true
    });

    // Add navigation controls
    map.addControl(new maplibregl.NavigationControl(), "bottom-right");

    let totalParcels = 0;
    let totalBuildings = 0;
    let selectedMarker = null;

    map.on("load", async function () {
        try {
            // 2. Load GeoJSON Data for active region
            const [parcelsRes, bldgsRes] = await Promise.all([
                fetch(activeRegion.parcelsUrl),
                fetch(activeRegion.bldgsUrl)
            ]);

            if (!parcelsRes.ok || !bldgsRes.ok) throw new Error("Failed to load data.");

            parcelsData = await parcelsRes.json();
            bldgsData = await bldgsRes.json();

            totalParcels = parcelsData.features.length;
            totalBuildings = bldgsData.features.length;

            // Update stats panel
            const updateStats = function () {
                document.getElementById("stat-buildings").innerText = totalBuildings.toLocaleString();
                document.getElementById("stat-parcels").innerText = totalParcels.toLocaleString();
            };

            updateStats();
            renderFloorCoverage();

            const addCustomLayers = function () {
                if (!parcelsData || !bldgsData) return;

                if (!map.getSource("satellite")) {
                    map.addSource("satellite", {
                        "type": "raster",
                        "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                        "tileSize": 256,
                        "attribution": "Tiles &copy; Esri"
                    });
                }
                if (!map.getLayer("satellite-layer")) {
                    map.addLayer({
                        "id": "satellite-layer",
                        "type": "raster",
                        "source": "satellite",
                        "layout": { "visibility": isSatellite ? "visible" : "none" }
                    });
                }

                if (!map.getSource("parcels")) {
                    map.addSource("parcels", { type: "geojson", data: parcelsData });
                }
                if (!map.getLayer("parcels-layer")) {
                    map.addLayer({
                        "id": "parcels-layer",
                        "type": "fill",
                        "source": "parcels",
                        "paint": {
                            "fill-color": isSatellite ? "#fbbf24" : (isLightMode ? "#000000" : "#ffffff"),
                            "fill-opacity": isSatellite ? 0.15 : 0.05,
                            "fill-outline-color": isSatellite ? "#fbbf24" : (isLightMode ? "#000000" : "#ffffff")
                        }
                    });
                }
                if (!map.getLayer("parcels-line-layer")) {
                    map.addLayer({
                        "id": "parcels-line-layer",
                        "type": "line",
                        "source": "parcels",
                        "paint": {
                            "line-color": isSatellite ? "#fbbf24" : (isLightMode ? "#000000" : "#ffffff"),
                            "line-opacity": isSatellite ? 0.8 : 0.3,
                            "line-width": isSatellite ? 2 : 1,
                            "line-dasharray": [2, 2]
                        }
                    });
                }

                if (!map.getSource("buildings")) {
                    map.addSource("buildings", { type: "geojson", data: bldgsData, promoteId: "id" });
                }
                if (!map.getLayer("buildings-3d-layer")) {
                    const resToggle = document.getElementById("res-toggle");
                    const isSimulated = resToggle ? resToggle.checked : false;
                    const hField = isSimulated ? "building_height_m_simulated" : "building_height_m";
                    
                    map.addLayer({
                        "id": "buildings-3d-layer",
                        "type": "fill-extrusion",
                        "source": "buildings",
                        "paint": {
                            "fill-extrusion-color": [
                                "case",
                                ["==", ["feature-state", "reviewer_status"], "APPROVE"], "#10b981",
                                ["==", ["feature-state", "reviewer_status"], "CORRECT"], "#3b82f6",
                                ["==", ["feature-state", "reviewer_status"], "REJECT"], "#ef4444",
                                ["==", ["feature-state", "reviewer_status"], "UNRESOLVED"], "#f59e0b",
                                [
                                    "match",
                                    ["get", "3d_representation_status"],
                                    "EXACT STRUCTURED 3D", "#3b82f6",
                                    "HEIGHT-DERIVED MASS", "#10b981",
                                    "2D FOOTPRINT ONLY", "#f59e0b",
                                    [
                                        "match",
                                        ["get", "match_status_2d"],
                                        "CONTAINED", "#10b981",
                                        "MAJORITY", "#f59e0b",
                                        "BOUNDARY_OVERLAP", "#ef4444",
                                        "#64748b"
                                    ]
                                ]
                            ],
                            "fill-extrusion-height": [
                                "coalesce",
                                ["get", hField],
                                ["get", "building_height_m_simulated"],
                                ["get", "building_height_m"],
                                10
                            ],
                            "fill-extrusion-base": 0,
                            "fill-extrusion-opacity": 0.85
                        }
                    });
                }
            };

            addCustomLayers();

            const loaderEl = document.getElementById("loader");
            if (loaderEl) loaderEl.classList.add("hidden");

            // Interactivity: Click on Building
            map.on("click", "buildings-3d-layer", function (e) {
                if (!e.features.length) return;
                const feature = e.features[0];
                const props = feature.properties;

                if (selectedMarker) {
                    selectedMarker.setLngLat(e.lngLat);
                } else {
                    selectedMarker = new maplibregl.Marker({ color: "#ef4444" })
                        .setLngLat(e.lngLat)
                        .addTo(map);
                }

                currentFeatureId = props.id;
                document.getElementById("no-selection-msg").style.display = "none";

                const card = document.getElementById("property-card");
                card.style.display = "block";
                void card.offsetWidth;
                card.classList.remove("hidden");

                const isSimulated = document.getElementById("res-toggle").checked;
                const hField = isSimulated ? "building_height_m_simulated" : "building_height_m";

                document.getElementById("prop-ulpin").innerText = props.linked_parcel_id || "NOT AVAILABLE";

                const matchStatus = props.match_status_2d || "UNKNOWN";
                const msEl = document.getElementById("prop-match-status");
                msEl.innerText = matchStatus;

                if (matchStatus === "CONTAINED") {
                    msEl.style.color = "#10b981";
                } else if (matchStatus === "MAJORITY") {
                    msEl.style.color = "#f59e0b";
                } else {
                    msEl.style.color = "#ef4444";
                }

                const ground = props.ground_elevation_m;
                document.getElementById("prop-ground").innerText = ground ? ground + " m" : "NOT_DETERMINABLE";

                const h = props[hField] || props["building_height_m"] || props["building_height_m_simulated"];
                let fl = props.derived_floors;

                if (isSimulated && h != null) {
                    fl = Math.max(1, Math.round(h / 3.5));
                }

                if (h != null && fl != null && fl !== "NOT_DETERMINABLE") {
                    const isObs = props.floor_detection_status === "OBSERVED";
                    const estTag = isObs ? "Observed" : "EST.";
                    document.getElementById("prop-height-floors").innerText = h + "m (" + fl + " Floors · " + estTag + ")";
                } else if (h != null) {
                    document.getElementById("prop-height-floors").innerText = h + "m (Floors Unknown)";
                } else {
                    document.getElementById("prop-height-floors").innerText = "NOT_DETERMINABLE";
                }

                let prov = props.height_source || "NOT_DETERMINABLE";
                if (isSimulated) {
                    prov = "CartoDEM_1m_SIMULATED";
                } else if (prov === "REAL_DSM - BARE_EARTH_DEM") {
                    prov = "CartoDEM - BareEarth_DEM";
                } else if (prov === "GOOGLE_OPEN_BUILDINGS_2.5D") {
                    prov = "ESTIMATED (Urban Profile Model)";
                } else if (prov === "OSM_VERIFIED") {
                    prov = "OSM_VERIFIED (Observed Tag)";
                }
                document.getElementById("prop-source").innerText = prov;

                // --- Additive: NDVI vegetation evidence / building-height confidence ---
                // NDVI is an independent vegetation-evidence layer on top of the
                // Copernicus GLO-30 surface elevation. It is NOT a building-vs-tree
                // classifier and buildings are never hidden on low confidence.
                (function renderNdviEvidence() {
                    var vegRaw = props.vegetation_evidence || "NOT_COMPUTED";
                    var vegLabel = props.vegetation_evidence_label || ({
                        LOW_VEGETATION: "Low vegetation",
                        SURROUNDING_VEGETATION: "Surrounding vegetation",
                        EDGE_VEGETATION: "Edge vegetation",
                        INTERNAL_VEGETATION: "Internal vegetation",
                        MIXED_VEGETATION: "Mixed vegetation",
                        VEGETATION_DOMINANT: "Vegetation dominant within footprint",
                        RESOLUTION_LIMITED: "Resolution limited",
                        STRONG_VEGETATION: "Strong vegetation",
                        NODATA: "No valid NDVI data",
                        NOT_DETERMINABLE: "Not determinable",
                        NOT_COMPUTED: "Not available"
                    }[vegRaw] || "Not available");

                    var cat = props.building_height_confidence || "NOT_DETERMINABLE";
                    var score100 = props.building_height_confidence_score_100;
                    var vStatus = props.vertical_evidence_status || "NDVI_UNAVAILABLE";
                    var hv = props.ndvi_review_recommendation || "NONE";

                    var veEl = document.getElementById("prop-ndvi-evidence");
                    if (veEl) {
                        veEl.innerText = vegLabel;
                        // Colour-code the pattern: red = vegetation dominant (may not
                        // be a building), amber = edge/internal/mixed (verify),
                        // green = low/surrounding (surface clear), grey = unresolved.
                        var vegColor = ({
                            LOW_VEGETATION: "#10b981",
                            SURROUNDING_VEGETATION: "#10b981",
                            EDGE_VEGETATION: "#f59e0b",
                            INTERNAL_VEGETATION: "#f59e0b",
                            MIXED_VEGETATION: "#f59e0b",
                            VEGETATION_DOMINANT: "#ef4444",
                            STRONG_VEGETATION: "#ef4444"
                        })[vegRaw] || "#94a3b8";
                        veEl.style.color = vegColor;
                        veEl.style.fontWeight = (vegRaw === "VEGETATION_DOMINANT") ? "700" : "400";
                    }

                    var cEl = document.getElementById("prop-height-confidence");
                    if (cEl) {
                        cEl.innerText = (score100 !== null && score100 !== undefined)
                            ? (cat + " (" + score100 + "/100)") : cat;
                        cEl.style.color = cat === "HIGH" ? "#10b981"
                            : cat === "MEDIUM" ? "#f59e0b"
                            : cat === "LOW" ? "#ef4444" : "#94a3b8";
                    }

                    var vsEl = document.getElementById("prop-vertical-evidence");
                    if (vsEl) {
                        var nice = {
                            SUPPORTED: "SUPPORTED",
                            PROVISIONAL: "PROVISIONAL",
                            VEGETATION_POSSIBLE: "VEGETATION POSSIBLE",
                            NOT_DETERMINABLE: "NOT DETERMINABLE",
                            NDVI_UNAVAILABLE: "NDVI UNAVAILABLE"
                        }[vStatus] || vStatus;
                        vsEl.innerText = nice;
                        vsEl.style.color = vStatus === "SUPPORTED" ? "#10b981"
                            : vStatus === "PROVISIONAL" ? "#f59e0b" : "#ef4444";
                    }

                    var hvRow = document.getElementById("prop-row-ndvi-hv");
                    var hvEl = document.getElementById("prop-ndvi-hv");
                    if (hvRow && hvEl) {
                        if (hv === "HUMAN_VERIFICATION_REQUIRED") {
                            hvRow.style.display = "";
                            hvEl.innerText = "REQUIRED";
                        } else {
                            hvRow.style.display = "none";
                        }
                    }

                    if (props.ndvi_source) {
                        var srcEl = document.getElementById("prop-source");
                        if (srcEl && srcEl.innerText.indexOf("NDVI") === -1) {
                            srcEl.innerText = srcEl.innerText + " + NDVI";
                        }
                    }
                })();

                const anomalyFlag = props.ai_anomaly_flag;
                const anomalyScore = props.ai_anomaly_score || 0;
                const anomalyScoreFmt = props.ai_anomaly_score ? props.ai_anomaly_score.toFixed(4) : "0.0000";

                const aiEl = document.getElementById("prop-ai-status");
                if (anomalyFlag) {
                    aiEl.innerText = "ANOMALY DETECTED (" + anomalyScoreFmt + ")";
                    aiEl.style.color = "#ef4444";
                } else {
                    aiEl.innerText = "NORMAL (" + anomalyScoreFmt + ")";
                    aiEl.style.color = "#10b981";
                }

                const confidencePercent = ((1 - anomalyScore) * 100).toFixed(1);
                const confEl = document.getElementById("prop-confidence-score");
                if (confEl) confEl.innerText = confidencePercent + "%";

                const bIdNum = String(props.id || "0").replace(/\D/g, "");
                const pIdNum = (props.linked_parcel_id || "0000").replace(/\D/g, "");
                const proposedUlpin = "IN-KA-BLR-P" + pIdNum + "-B" + bIdNum;
                document.getElementById("prop-proposed-ulpin").innerText = props.linked_parcel_id ? proposedUlpin : "NOT_AVAILABLE";

                const gateEl = document.getElementById("prop-verification");
                const gate = props.final_verification_status || "NOT_VERIFIED";
                gateEl.innerText = gate;
                if (gate === "VERIFIED") gateEl.style.color = "#10b981";
                else if (gate === "PROVISIONAL") gateEl.style.color = "#f59e0b";
                else gateEl.style.color = "#ef4444";

                // --- Additive: approximate floor estimate (Phase 12) ---
                window.__selectedBuilding = { props: props, geometry: feature.geometry };
                renderFloorSection(props);
                if (!document.getElementById("floor-panel").hidden) {
                    renderFloorPanel(props, feature.geometry);   // refresh if already open
                }
            });

            // ============ Floor Detection & 3D Inspection (Phase 12 v3) ============
            var FLOOR_SRC = "floor-bands-src";
            var FLOOR_BANDS_LAYER = "floor-bands-layer";      // stacked floor bands of the selected building
            var FLOOR_OUT_LINE = "floor-outline-line";        // main map: outline of OBSERVED/PREDICTED
            var FLOOR_BADGE_LAYER = "floor-badge-layer";      // main map: floor-count badge
            var floorHoverPopup = null;
            var floorsMapOn = false;
            var floorHomeCam = null;
            var floorFocusId = null;
            var floorExploded = false;
            window.__floorSel = { id: null, floor: null };

            // green = observed/high, sky = medium estimate, amber = low estimate,
            // grey = not determinable. RED is NOT used here (reserved for conflict/HV).
            function floorStateColor(s) {
                return s === "HIGH" ? "#34d399" : s === "MEDIUM" ? "#38bdf8"
                    : s === "LOW" ? "#fbbf24" : "#94a3b8";
            }
            function floorJson(v) {
                if (Array.isArray(v)) return v;
                if (typeof v === "string" && v.length) { try { return JSON.parse(v); } catch (e) { return []; } }
                return [];
            }
            function floorDetected(p) { return (p.floor_detection_status || "NOT_DETERMINABLE") !== "NOT_DETERMINABLE"; }
            function floorNum(v) { var n = parseFloat(v); return isFinite(n) ? n : null; }
            function copyText(t, btn) {
                try {
                    navigator.clipboard.writeText(t);
                    if (btn) { var o = btn.innerText; btn.innerText = "copied"; setTimeout(function () { btn.innerText = o; }, 900); }
                } catch (e) { /* clipboard unavailable */ }
            }
            function logFloorAudit(action, ref) {
                var ts = new Date().toLocaleTimeString();
                auditLogs.unshift({ action: action, parcel: ref, timestamp: ts });
                var lc = document.getElementById("log-count"); if (lc) lc.innerText = auditLogs.length + " Entries";
                var cont = document.getElementById("logs-container");
                if (cont) cont.innerHTML = auditLogs.map(function (log) {
                    return '<div class="log-entry ' + log.action + '"><div class="log-meta"><span>' + log.timestamp + '</span>'
                        + '<span class="log-action ' + log.action + '">' + log.action + '</span></div>'
                        + '<div class="log-ulpin">' + log.parcel + '</div>'
                        + '<div style="color: var(--text-muted);">Logged from floor inspection</div></div>';
                }).join("");
            }

            // ---- coverage counter (real numbers from the loaded dataset) ----
            function renderFloorCoverage() {
                var box = document.getElementById("floor-coverage");
                if (!box || !bldgsData) return;
                var obs = 0, pred = 0, nd = 0, hi = 0, md = 0, lo = 0;
                bldgsData.features.forEach(function (f) {
                    var p = f.properties, s = p.floor_detection_status, c = p.floor_confidence_state;
                    if (s === "OBSERVED") obs++;
                    else if (s === "PREDICTED") { pred++; if (c === "HIGH") hi++; else if (c === "MEDIUM") md++; else lo++; }
                    else nd++;
                });
                box.innerHTML =
                    '<div class="fcov-title">FLOOR DETECTION</div>'
                    + '<div class="fcov-row"><span>Observed &middot; real OSM tag</span><b style="color:#34d399">' + obs + '</b></div>'
                    + '<div class="fcov-row"><span>Predicted &middot; ML model</span><b style="color:#38bdf8">' + pred + '</b></div>'
                    + '<div class="fcov-sub">high ' + hi + ' &middot; medium ' + md + ' &middot; low ' + lo + '</div>'
                    + '<div class="fcov-row"><span>Not determinable</span><b style="color:#94a3b8">' + nd + '</b></div>'
                    + '<div class="fcov-note">Predictions are calibrated model estimates (P within &plusmn;1 floor). LOW-confidence estimates get no proposed IDs. Every ML estimate is flagged for human verification.</div>';
            }

            // ---- property-card mini section ----
            function renderFloorSection(props) {
                var det = floorDetected(props);
                var st = props.floor_detection_status || "NOT_DETERMINABLE";
                var state = props.floor_confidence_state || "NOT_DETERMINABLE";
                var estEl = document.getElementById("prop-floor-est");
                if (estEl) {
                    if (!det) { estEl.innerText = "Not determinable"; estEl.style.color = "#94a3b8"; }
                    else {
                        var n = props.floor_count_estimated;
                        var rng = (props.floor_min != null && props.floor_max != null && props.floor_min !== props.floor_max)
                            ? " (" + props.floor_min + "–" + props.floor_max + ")" : "";
                        estEl.innerText = n + (n === 1 ? " floor" : " floors") + rng + (st === "PREDICTED" ? " · EST." : "");
                        estEl.style.color = floorStateColor(state);
                    }
                }
                var cEl = document.getElementById("prop-floor-conf");
                if (cEl) {
                    if (st === "OBSERVED") cEl.innerText = "Real OSM tag";
                    else if (st === "PREDICTED") cEl.innerText = (props.floor_confidence_pct || "?") + "% within ±1 · " + state;
                    else cEl.innerText = "—";
                    cEl.style.color = floorStateColor(state);
                }
                var evEl = document.getElementById("prop-floor-evidence");
                if (evEl) {
                    evEl.innerText = st === "OBSERVED" ? "OBSERVED · OSM building:levels"
                        : st === "PREDICTED" ? "PREDICTED · ML model"
                        : "NOT_DETERMINABLE · insufficient real evidence";
                }
                var hvRow = document.getElementById("prop-row-floor-hv");
                var hvEl = document.getElementById("prop-floor-hv");
                var needsHv = props.requires_human_verification === true || props.requires_human_verification === "true";
                if (hvRow && hvEl) {
                    if (needsHv) { hvRow.style.display = ""; hvEl.innerText = "REQUIRED"; } else hvRow.style.display = "none";
                }
                var btnRow = document.getElementById("prop-row-floor-btn");
                if (btnRow) btnRow.style.display = "";
            }

            // per-floor metadata for the 3D tooltip (i0 = 0-based floor index)
            function floorMetaText(props, i0) {
                var ids = floorJson(props.floor_level_ids);
                for (var k = 0; k < ids.length; k++) {
                    if (ids[k] && ids[k].floor_index === i0 + 1) return ids[k].proposed_floor_spatial_id;
                }
                if (props.floor_detection_status === "PREDICTED" && props.floor_confidence_state === "LOW")
                    return "LOW confidence — no proposed floor-level ID";
                if (!props.linked_parcel_id) return "No linked parcel — no proposed ID";
                return "Proposed ID not generated";
            }

            // ---- interactive 3D building model (falls back to the SVG schematic) ----
            function renderElevationDiagram(props) {
                var box = document.getElementById("floor-panel-diagram");
                if (box.__floor3d) box.__floor3d.dispose();
                if (!floorDetected(props)) { box.innerHTML = ""; box.hidden = true; return; }
                box.hidden = false;
                box.innerHTML = "";
                var isObs = props.floor_detection_status === "OBSERVED";
                var n = props.floor_count_estimated;
                var hM = floorNum(props.building_height_m) || n * 3.2;
                var g = floorNum(props.ground_elevation_m);
                var accent = isObs ? "#34d399" : floorStateColor(props.floor_confidence_state);
                var geom = window.__selectedBuilding && window.__selectedBuilding.geometry;
                var ring = null;
                try { ring = geom && geom.coordinates && geom.coordinates[0]; } catch (e) { ring = null; }
                var ctrl = null;
                try {
                    ctrl = window.Floor3D && window.Floor3D.mount(box, {
                        floors: n, heightM: hM, groundElev: (g == null ? null : g),
                        accentHex: accent, est: !isObs, ring: ring,
                        floorLabel: function (i0) { return (i0 === 0 ? "GND" : "F" + i0) + (isObs ? "" : " EST."); },
                        floorMeta: function (i0) { return floorMetaText(props, i0); },
                        onSelect: function (i0) { selectFloor(i0 + 1); }
                    });
                } catch (e) { ctrl = null; }
                if (!ctrl) { box.innerHTML = ""; renderElevationDiagramSVG(props); return; }
                reflectFloorSelection();
            }

            // ---- compact elevation schematic (SVG fallback when WebGL/three unavailable) ----
            function renderElevationDiagramSVG(props) {
                var box = document.getElementById("floor-panel-diagram");
                if (!floorDetected(props)) { box.innerHTML = ""; box.hidden = true; return; }
                box.hidden = false;
                var n = props.floor_count_estimated;
                var W = 260, H = 150, padL = 40, padT = 10, padB = 16;
                var innerH = H - padT - padB, bw = 78, bx = (W - bw) / 2 + 8;
                var hM = floorNum(props.building_height_m) || n * 3.2;
                var g = floorNum(props.ground_elevation_m);
                var isObs = props.floor_detection_status === "OBSERVED";
                var col = isObs ? "#34d399" : floorStateColor(props.floor_confidence_state);
                var band = innerH / n;
                var s = ['<svg viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg">'];
                s.push('<text class="fpd-axis" x="' + (padL - 8) + '" y="' + (padT + 6) + '" text-anchor="end">Roof ' + hM.toFixed(1) + ' m</text>');
                if (!isObs) s.push('<text class="fpd-est" x="' + (W - 8) + '" y="' + (padT + 8) + '" text-anchor="end">EST.</text>');
                s.push('<text class="fpd-axis" x="' + (padL - 8) + '" y="' + (padT + innerH + 12) + '" text-anchor="end">Ground' + (isFinite(g) ? ' (DEM ' + g.toFixed(0) + ')' : '') + '</text>');
                s.push('<line x1="' + (padL - 6) + '" y1="' + (padT + innerH) + '" x2="' + (W - 8) + '" y2="' + (padT + innerH) + '" stroke="#475569"/>');
                s.push('<rect x="' + bx + '" y="' + padT + '" width="' + bw + '" height="' + innerH + '" fill="rgba(56,189,248,0.05)" stroke="#38bdf8" stroke-width="1.4"/>');
                for (var i = 0; i < n; i++) {
                    var fy = padT + innerH - (i + 1) * band, fidx = i + 1;
                    s.push('<rect class="fpd-band" data-floor="' + fidx + '" x="' + bx + '" y="' + fy + '" width="' + bw + '" height="' + band + '" fill="' + col + '" fill-opacity="0.16"/>');
                    if (i > 0) s.push('<line x1="' + bx + '" y1="' + fy + '" x2="' + (bx + bw) + '" y2="' + fy + '" stroke="#94a3b8" stroke-width="0.5" stroke-dasharray="3 3"/>');
                    s.push('<text class="fpd-label" x="' + (bx + bw / 2) + '" y="' + (fy + band / 2 + 3) + '" text-anchor="middle">' + (fidx === 1 ? "GND" : "F" + (fidx - 1)) + (isObs ? "" : " EST.") + '</text>');
                }
                s.push('</svg>');
                box.innerHTML = s.join("");
                box.querySelectorAll(".fpd-band").forEach(function (b) {
                    b.addEventListener("click", function () { selectFloor(parseInt(b.getAttribute("data-floor"), 10)); });
                });
                reflectFloorSelection();
            }

            // ---- panel ----
            function renderFloorPanel(props, geometry) {
                var panel = document.getElementById("floor-panel");
                window.__selectedBuilding = { props: props, geometry: geometry };
                window.__floorSel = { id: props.id, floor: null };
                floorExploded = false;
                if (!floorHomeCam) floorHomeCam = { center: map.getCenter(), zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing() };
                document.getElementById("floor-panel-bldg").innerText = "Building " + (props.id || "-");
                document.getElementById("floor-panel-parcel").innerText = "Parcel " + (props.linked_parcel_id || "-");
                var summary = document.getElementById("floor-panel-summary");
                var actions = document.getElementById("floor-panel-actions");
                var body = document.getElementById("floor-panel-body");
                var diagram = document.getElementById("floor-panel-diagram");
                var st = props.floor_detection_status || "NOT_DETERMINABLE";
                var state = props.floor_confidence_state || "NOT_DETERMINABLE";
                var ids = floorJson(props.floor_level_ids);
                var hM = floorNum(props.building_height_m);
                var needsHv = props.requires_human_verification === true || props.requires_human_verification === "true";

                if (!floorDetected(props)) {
                    if (diagram.__floor3d) diagram.__floor3d.dispose();
                    diagram.innerHTML = ""; diagram.hidden = true;
                    summary.innerHTML = '<span class="floor-panel-state fp-state-NOT_DETERMINABLE">FLOOR DETECTION UNAVAILABLE</span>';
                    actions.innerHTML = '<button class="fp-btn" id="fp-whole" type="button">Show Entire Building</button>';
                    var miss = floorJson(props.floor_missing_evidence);
                    body.innerHTML =
                        '<div class="floor-panel-unavail">'
                        + '<b>The floor model did not have enough real evidence to detect floors here.</b>'
                        + (props.floor_detection_reason ? '<div style="margin-top:8px;">' + props.floor_detection_reason + '</div>' : '')
                        + '<div class="fu-kv"><span>Building height</span><b>' + (hM ? hM.toFixed(1) + ' m' : 'unavailable') + '</b></div>'
                        + '<div class="fu-kv"><span>Vertical evidence</span><b>Available</b></div>'
                        + '<div class="fu-kv"><span>Source</span><b>INSUFFICIENT REAL EVIDENCE</b></div>'
                        + '<div class="fu-kv"><span>Status</span><b style="color:#cbd5e1">NOT_DETERMINABLE</b></div>'
                        + (props.floor_vertical_context === "VEGETATION_CONTAMINATED_HEIGHT"
                            ? '<div style="color:#fbbf24;font-size:10px;margin-top:6px;">Vertical evidence may be vegetation-contaminated (NDVI vegetation-dominant).</div>' : '')
                        + '<div style="margin-top:8px;color:var(--text-main);">What would be required:</div>'
                        + '<ul>' + miss.map(function (x) { return '<li>' + x + '</li>'; }).join("") + '</ul>'
                        + '<button class="fp-btn" id="fp-require-hv" type="button">Human Verification</button>'
                        + '<div style="margin-top:8px;color:var(--text-muted);">No floor-level spatial IDs generated.</div>'
                        + '</div>';
                    document.getElementById("fp-whole").addEventListener("click", function () { showWholeBuilding(); });
                    var rq = document.getElementById("fp-require-hv");
                    if (rq) rq.addEventListener("click", function () {
                        logFloorAudit("FLOOR_VERIFICATION_REQUESTED", props.linked_parcel_id || props.id);
                        rq.textContent = "Human verification requested"; rq.disabled = true;
                    });
                    panel.hidden = false;
                    focusBuilding(props, geometry);
                    return;
                }

                // ---- OBSERVED or PREDICTED ----
                var isObs = st === "OBSERVED";
                renderElevationDiagram(props);
                var support = floorJson(props.floor_supporting_evidence);
                var srcChip = isObs
                    ? '<span class="fp-src fp-src-obs">OBSERVED &middot; REAL OSM TAG</span>'
                    : '<span class="fp-src fp-src-pred">MODEL-ESTIMATED &middot; ML PREDICTION</span>';
                var label = isObs ? "Observed Floors" : "Estimated Floors";
                summary.innerHTML =
                    srcChip
                    + '<div style="margin-top:6px;"><span class="fp-k">' + label + ':</span> <span class="fp-v" style="color:' + floorStateColor(state) + '">' + props.floor_count_estimated
                    + (!isObs ? ' <span class="fp-est">EST.</span>' : '')
                    + (props.floor_min != null && props.floor_min !== props.floor_max
                        ? ' <span style="font-weight:500;color:var(--text-muted)">(range ' + props.floor_min + '–' + props.floor_max + ')</span>' : '') + '</span></div>'
                    + (isObs
                        ? '<div><span class="fp-k">Confidence:</span> real OpenStreetMap building:levels tag <span style="color:var(--text-muted);font-size:10px;">(crowd-sourced, no probabilistic model)</span></div>'
                        : '<div><span class="fp-k">Model confidence:</span> <span class="fp-v">' + (props.floor_confidence_pct || '?') + '%</span> within &plusmn;1 floor '
                          + '<span class="floor-panel-state fp-state-' + state + '">' + state + '</span></div>')
                    + '<div><span class="fp-k">Status:</span> <span class="fp-v" style="color:' + floorStateColor(state) + '">' + (isObs ? "OBSERVED" : state === "LOW" ? "LOW-CONFIDENCE ESTIMATE" : "MODEL-ESTIMATED") + '</span></div>'
                    + (props.floor_ood_flag ? '<div style="color:#fbbf24;font-size:10px;margin-top:4px;">Outside the model reference range - treat with caution.</div>' : '')
                    + (props.floor_vertical_context === "VEGETATION_CONTAMINATED_HEIGHT"
                        ? '<div style="color:#fbbf24;font-size:10px;margin-top:4px;">Height context may be vegetation-contaminated (NDVI vegetation-dominant).</div>' : '')
                    + (needsHv ? '<div style="color:#fbbf24;font-size:10px;margin-top:6px;font-weight:700;">HUMAN VERIFICATION REQUIRED</div>' : '')
                    + (!isObs && state === "LOW" ? '<div style="color:var(--text-muted);font-size:10px;margin-top:4px;">Low confidence - shown for review; no proposed floor-level IDs generated.</div>' : '')
                    + (support.length
                        ? '<div class="fp-why"><div class="fp-why-h">Why this floor count?</div>'
                          + support.map(function (x) { return '<div class="fp-why-i">&#10003; ' + x + '</div>'; }).join("")
                          + '<div class="fp-why-i" style="color:var(--text-muted);margin-top:3px;">These are model inputs, not independent proof.</div></div>'
                        : '')
                    + '<div style="color:var(--text-muted);font-size:10px;margin-top:6px;">' + (isObs ? "Observed" : "Estimated") + ' floor levels - proportional divisions of the derived height, not measured architectural slabs. Not an official ULPIN.</div>';

                actions.innerHTML =
                    '<button class="fp-btn" id="fp-whole" type="button">Show Entire Building</button>'
                    + '<button class="fp-btn fp-btn-sm" id="fp-explode" type="button" title="Separate floor bands">Explode</button>'
                    + '<button class="fp-btn fp-btn-sm" id="fp-rotate" type="button" title="Rotate view">&#8635;</button>'
                    + '<button class="fp-btn fp-btn-sm" id="fp-reset" type="button" title="Reset view">Reset</button>';
                var diag = document.getElementById("floor-panel-diagram");
                document.getElementById("fp-whole").addEventListener("click", function () { showWholeBuilding(); });
                document.getElementById("fp-explode").addEventListener("click", function () {
                    floorExploded = !floorExploded;
                    this.classList.toggle("on", floorExploded);
                    drawFloorBands(props, geometry, window.__floorSel.floor);
                    if (diag.__floor3d) diag.__floor3d.explode(floorExploded);
                });
                document.getElementById("fp-rotate").addEventListener("click", function () {
                    map.easeTo({ bearing: (map.getBearing() + 40) % 360, duration: 500 });
                    if (diag.__floor3d) diag.__floor3d.spin();
                });
                document.getElementById("fp-reset").addEventListener("click", function () {
                    if (floorHomeCam) map.easeTo({ center: floorHomeCam.center, zoom: floorHomeCam.zoom, pitch: floorHomeCam.pitch, bearing: floorHomeCam.bearing, duration: 600 });
                    if (diag.__floor3d) diag.__floor3d.resetView();
                });

                if (ids.length) {
                    body.innerHTML = ids.slice().reverse().map(function (fl) {
                        return '<div class="floor-row" data-floor="' + fl.floor_index + '">'
                            + '<div class="fr-top"><span class="fr-name">' + fl.floor_name
                            + (isObs ? '' : ' <span class="fp-est">EST.</span>') + '</span>'
                            + '<span class="fr-tag ' + (isObs ? 'REFERENCE' : 'MODELLED') + '">' + (isObs ? 'OBSERVED' : 'PREDICTED &middot; EST.') + '</span></div>'
                            + '<div class="fr-id"><span>' + fl.proposed_floor_spatial_id + '</span>'
                            + '<button class="fr-copy" type="button" data-copy="' + fl.proposed_floor_spatial_id + '" title="Copy proposed spatial ID">copy</button></div>'
                            + '<div class="fr-meta">' + (isObs ? 'OSM tag' : 'model estimate ' + (props.floor_confidence_pct || '?') + '%') + ' &middot; ' + state + '</div>'
                            + '</div>';
                    }).join("");
                    body.querySelectorAll(".floor-row").forEach(function (row) {
                        row.addEventListener("click", function (e) {
                            if (e.target.classList.contains("fr-copy")) return;
                            selectFloor(parseInt(row.getAttribute("data-floor"), 10));
                        });
                    });
                    body.querySelectorAll(".fr-copy").forEach(function (b) {
                        b.addEventListener("click", function (e) { e.stopPropagation(); copyText(b.getAttribute("data-copy"), b); });
                    });
                } else if (!isObs && state === "LOW") {
                    body.innerHTML = '<div class="floor-panel-unavail">'
                        + '<b>LOW-confidence model estimate.</b>'
                        + '<div style="margin-top:8px;">This estimate (' + props.floor_count_estimated + ' floors &middot; EST.) is shown for human review only. '
                        + 'It did not clear the confidence bar for a proposed linkage, so <b>no floor-level spatial IDs are generated</b>.</div>'
                        + '<div style="margin-top:8px;color:var(--text-muted);">Verify on the ground or against a higher-resolution source before use.</div>'
                        + '</div>';
                } else {
                    body.innerHTML = '<div class="floor-panel-unavail">Floor count available, but this building has no linked '
                        + 'cadastral parcel, so no proposed floor-level spatial IDs are generated.</div>';
                }

                panel.hidden = false;
                focusBuilding(props, geometry);
                showWholeBuilding();
            }

            function selectFloor(n) {
                window.__floorSel.floor = n;
                reflectFloorSelection();
                var sb = window.__selectedBuilding;
                if (sb) drawFloorBands(sb.props, sb.geometry, n);
            }
            function reflectFloorSelection() {
                var n = window.__floorSel.floor;
                document.querySelectorAll("#floor-panel-body .floor-row").forEach(function (r) {
                    r.classList.toggle("selected", parseInt(r.getAttribute("data-floor"), 10) === n);
                });
                document.querySelectorAll("#floor-panel-diagram .fpd-band").forEach(function (bd) {
                    bd.classList.toggle("selected", parseInt(bd.getAttribute("data-floor"), 10) === n);
                });
                var box = document.getElementById("floor-panel-diagram");
                if (box && box.__floor3d) box.__floor3d.select(n ? n - 1 : null);
            }

            // dim every other building so the selected one reads as an isolated 3D model
            function focusBuilding(props, geometry) {
                floorFocusId = props.id;
                if (map.getLayer("buildings-3d-layer")) {
                    map.setPaintProperty("buildings-3d-layer", "fill-extrusion-opacity",
                        ["case", ["==", ["get", "id"], props.id], 0.95, 0.1]);
                }
                floorFlyTo(geometry);
            }
            function unfocusBuilding() {
                floorFocusId = null;
                if (map.getLayer("buildings-3d-layer")) {
                    map.setPaintProperty("buildings-3d-layer", "fill-extrusion-opacity", 0.85);
                }
            }

            // stacked floor bands over the real footprint (one geojson, one layer)
            function drawFloorBands(props, geometry, selected) {
                var n = props.floor_count_estimated;
                var h = floorNum(props.building_height_m);
                if (!geometry || !n || !h || h <= 0) return;
                var fh = h / n;
                var gap = floorExploded ? Math.max(fh * 0.5, 2.0) : 0;
                var sep = Math.min(fh * 0.12, 0.6);
                var feats = [];
                for (var i = 1; i <= n; i++) {
                    var base = (i - 1) * (fh + gap);
                    feats.push({ type: "Feature", geometry: geometry,
                        properties: { floor: i, base: base, top: base + fh - sep } });
                }
                var fc = { type: "FeatureCollection", features: feats };
                if (map.getSource(FLOOR_SRC)) map.getSource(FLOOR_SRC).setData(fc);
                else map.addSource(FLOOR_SRC, { type: "geojson", data: fc });
                if (!map.getLayer(FLOOR_BANDS_LAYER)) {
                    map.addLayer({
                        id: FLOOR_BANDS_LAYER, type: "fill-extrusion", source: FLOOR_SRC,
                        paint: {
                            "fill-extrusion-base": ["get", "base"],
                            "fill-extrusion-height": ["get", "top"],
                            "fill-extrusion-color": ["case", ["==", ["get", "floor"], selected || -1], "#38bdf8",
                                ["==", ["%", ["get", "floor"], 2], 0], "#7dd3fc", "#a5b4fc"],
                            "fill-extrusion-opacity": ["case", ["==", ["get", "floor"], selected || -1], 0.95, 0.55]
                        }
                    });
                } else {
                    map.setPaintProperty(FLOOR_BANDS_LAYER, "fill-extrusion-color",
                        ["case", ["==", ["get", "floor"], selected || -1], "#38bdf8",
                            ["==", ["%", ["get", "floor"], 2], 0], "#7dd3fc", "#a5b4fc"]);
                    map.setPaintProperty(FLOOR_BANDS_LAYER, "fill-extrusion-opacity",
                        ["case", ["==", ["get", "floor"], selected || -1], 0.95, 0.55]);
                }
            }
            function showWholeBuilding() {
                var sb = window.__selectedBuilding;
                if (!sb) return;
                window.__floorSel.floor = null;
                reflectFloorSelection();
                drawFloorBands(sb.props, sb.geometry, null);
                floorFlyTo(sb.geometry);
            }
            function floorFlyTo(geometry) {
                try {
                    var ring = geometry.coordinates[0], lng = 0, lat = 0;
                    ring.forEach(function (p) { lng += p[0]; lat += p[1]; });
                    map.easeTo({ center: [lng / ring.length, lat / ring.length], zoom: Math.max(map.getZoom(), 17.5), pitch: Math.max(map.getPitch(), 58), duration: 550 });
                } catch (e) { /* keep view */ }
            }
            function clearFloorBands() {
                if (map.getLayer(FLOOR_BANDS_LAYER)) map.removeLayer(FLOOR_BANDS_LAYER);
                if (map.getSource(FLOOR_SRC)) map.removeSource(FLOOR_SRC);
            }
            function closeFloorPanel() {
                document.getElementById("floor-panel").hidden = true;
                var d3 = document.getElementById("floor-panel-diagram");
                if (d3 && d3.__floor3d) d3.__floor3d.dispose();
                ["floor-panel-summary", "floor-panel-actions", "floor-panel-body", "floor-panel-diagram"].forEach(function (id) {
                    var el = document.getElementById(id); if (el) el.innerHTML = "";
                });
                window.__floorSel = { id: null, floor: null };
                floorExploded = false;
                clearFloorBands();
                unfocusBuilding();
            }

            // ---- main-map floor indicators (toggle) - OBSERVED + PREDICTED only ----
            function addFloorMapLayers() {
                if (!map.getSource("buildings")) return;
                var filt = ["match", ["get", "floor_detection_status"], ["OBSERVED", "PREDICTED"], true, false];
                if (!map.getLayer(FLOOR_OUT_LINE)) {
                    map.addLayer({
                        id: FLOOR_OUT_LINE, type: "line", source: "buildings", filter: filt,
                        layout: { visibility: "none" },
                        paint: {
                            // colour by confidence state, never red (red = conflict/verification only)
                            "line-color": ["match", ["get", "floor_confidence_state"],
                                "HIGH", "#34d399", "MEDIUM", "#38bdf8", "LOW", "#fbbf24", "#94a3b8"],
                            // OBSERVED reads as a solid line, ML estimates as dashed
                            "line-dasharray": ["match", ["get", "floor_source"],
                                "REAL_OSM_BUILDING_LEVELS", ["literal", [1]], ["literal", [2, 1.5]]],
                            "line-width": 2, "line-opacity": 0.9
                        }
                    });
                }
                if (!map.getLayer(FLOOR_BADGE_LAYER)) {
                    map.addLayer({
                        id: FLOOR_BADGE_LAYER, type: "symbol", source: "buildings", minzoom: 16, filter: filt,
                        layout: { visibility: "none",
                            // "4" for OBSERVED, "4*" for an ML estimate (EST. marker on the map)
                            "text-field": ["concat", ["to-string", ["get", "floor_count_estimated"]],
                                ["match", ["get", "floor_source"], "ML_MODEL", "*", ""]],
                            "text-size": 12, "text-allow-overlap": false, "text-optional": true },
                        paint: { "text-color": "#eafff6", "text-halo-color": "#0f172a", "text-halo-width": 1.6 }
                    });
                }
            }
            var btnFloors = document.getElementById("toggle-floors");
            if (btnFloors) btnFloors.addEventListener("click", function () {
                floorsMapOn = !floorsMapOn;
                btnFloors.classList.toggle("active-floors", floorsMapOn);
                var fl = document.getElementById("floor-legend"); if (fl) fl.hidden = !floorsMapOn;
                addFloorMapLayers();
                [FLOOR_OUT_LINE, FLOOR_BADGE_LAYER].forEach(function (l) {
                    if (map.getLayer(l)) map.setLayoutProperty(l, "visibility", floorsMapOn ? "visible" : "none");
                });
            });

            // ---- hover tooltip (high contrast) ----
            map.on("mousemove", "buildings-3d-layer", function (e) {
                if (!e.features.length) return;
                var p = e.features[0].properties;
                var st = p.floor_detection_status;
                var block;
                if (st === "OBSERVED") {
                    block = '<div class="ftt-k">FLOOR DETECTION</div><div class="ftt-v">' + p.floor_count_estimated
                        + (p.floor_count_estimated == 1 ? ' floor' : ' floors') + '</div>'
                        + '<div class="ftt-k">SOURCE</div><div class="ftt-v" style="font-size:10px;">Real OSM building:levels tag</div>';
                } else if (st === "PREDICTED") {
                    var rg = (p.floor_min != null && p.floor_max != null && p.floor_min !== p.floor_max) ? ' (' + p.floor_min + '–' + p.floor_max + ')' : '';
                    block = '<div class="ftt-k">FLOOR DETECTION</div><div class="ftt-v">' + p.floor_count_estimated + ' floors' + rg
                        + ' <span style="color:#fbbf24;font-weight:800;">EST.</span></div>'
                        + '<div class="ftt-k">MODEL CONFIDENCE</div><div class="ftt-v">' + (p.floor_confidence_pct || '?') + '% within ±1 · ' + (p.floor_confidence_state || '-') + '</div>'
                        + '<div class="ftt-k">SOURCE</div><div class="ftt-v" style="font-size:10px;">ML estimate (footprint shape + OSM tags + coarse DSM)</div>';
                } else {
                    block = '<div class="ftt-k">FLOOR DETECTION</div><div class="ftt-v" style="color:#cbd5e1;">NOT DETERMINABLE</div>'
                        + '<div class="ftt-k">REASON</div><div class="ftt-v" style="font-size:10px;">Insufficient real evidence / model abstained</div>';
                }
                var html = '<div class="ftt">'
                    + '<div class="ftt-h">Building ' + (p.id || "-") + '</div>'
                    + '<div class="ftt-s">Parcel ' + (p.linked_parcel_id || "-") + '</div>'
                    + '<div class="ftt-k">HEIGHT</div><div class="ftt-v">' + (p.building_height_m != null ? p.building_height_m + ' m' : '-') + '</div>'
                    + block
                    + '<div class="ftt-go">Click to inspect &rarr;</div></div>';
                if (!floorHoverPopup) floorHoverPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 14, className: "floor-tooltip" });
                floorHoverPopup.setLngLat(e.lngLat).setHTML(html).addTo(map);
            });
            map.on("mouseleave", "buildings-3d-layer", function () { if (floorHoverPopup) floorHoverPopup.remove(); });

            // ---- close controls ----
            var _fpc = document.getElementById("floor-panel-close");
            if (_fpc) _fpc.addEventListener("click", function (e) { e.stopPropagation(); closeFloorPanel(); });
            document.addEventListener("keydown", function (e) {
                if ((e.key === "Escape" || e.key === "Esc") && !document.getElementById("floor-panel").hidden) closeFloorPanel();
            });
            map.on("click", function (e) {
                if (document.getElementById("floor-panel").hidden) return;
                var hits = map.queryRenderedFeatures(e.point, { layers: ["buildings-3d-layer"] });
                if (!hits.length) closeFloorPanel();
            });
            var _bvf = document.getElementById("btn-view-floors");
            if (_bvf) _bvf.addEventListener("click", function () {
                if (window.__selectedBuilding) renderFloorPanel(window.__selectedBuilding.props, window.__selectedBuilding.geometry);
            });

            // Review Action Handler
            window.reviewAction = function (action) {
                const gateEl = document.getElementById("prop-verification");
                const parcel = document.getElementById("prop-ulpin").innerText;

                if (currentFeatureId) {
                    map.setFeatureState(
                        { source: "buildings", id: currentFeatureId },
                        { reviewer_status: action }
                    );
                }

                if (gateEl) {
                    if (action === "APPROVE") {
                        gateEl.innerText = "REVIEWER_APPROVED";
                        gateEl.style.color = "var(--color-contained)";
                    } else if (action === "CORRECT") {
                        gateEl.innerText = "REVIEWER_CORRECTED";
                        gateEl.style.color = "var(--accent-blue)";
                    } else if (action === "REJECT") {
                        gateEl.innerText = "REVIEWER_REJECTED";
                        gateEl.style.color = "var(--color-conflict)";
                    } else {
                        gateEl.innerText = "MARK_UNRESOLVED";
                        gateEl.style.color = "var(--color-majority)";
                    }
                }

                const timestamp = new Date().toLocaleTimeString();
                auditLogs.unshift({ action: action, parcel: parcel, timestamp: timestamp });

                document.getElementById("log-count").innerText = auditLogs.length + " Entries";

                const container = document.getElementById("logs-container");
                container.innerHTML = auditLogs.map(function (log) {
                    return (
                        '<div class="log-entry ' + log.action + '">' +
                        '<div class="log-meta">' +
                        '<span>' + log.timestamp + '</span>' +
                        '<span class="log-action ' + log.action + '">' + log.action + '</span>' +
                        '</div>' +
                        '<div class="log-ulpin">' + log.parcel + '</div>' +
                        '<div style="color: var(--text-muted);">Status updated by Surveyor</div>' +
                        '</div>'
                    );
                }).join("");
            };

            map.on("mouseenter", "buildings-3d-layer", function () {
                map.getCanvas().style.cursor = "pointer";
            });
            map.on("mouseleave", "buildings-3d-layer", function () {
                map.getCanvas().style.cursor = "";
            });

            // Resolution Toggle
            const resToggle = document.getElementById("res-toggle");
            if (resToggle) {
                resToggle.addEventListener("change", function (e) {
                    const isSimulated = e.target.checked;

                    document.getElementById("label-strict").classList.toggle("highlight", !isSimulated);
                    document.getElementById("label-sim").classList.toggle("highlight", isSimulated);

                    updateStats();

                    const heightField = isSimulated ? "building_height_m_simulated" : "building_height_m";
                    map.setPaintProperty("buildings-3d-layer", "fill-extrusion-height", [
                        "coalesce", ["get", heightField], ["get", "building_height_m_simulated"], ["get", "building_height_m"], 10
                    ]);

                    if (!document.getElementById("property-card").classList.contains("hidden")) {
                        document.getElementById("property-card").classList.add("hidden");
                    }
                });
            }

            // UI Toggles
            const btnTheme = document.getElementById("toggle-theme");
            const btnLeft = document.getElementById("toggle-left-sidebar");
            const btnRight = document.getElementById("toggle-right-sidebar");
            const btnMapStyle = document.getElementById("toggle-map-style");
            const btnCadastralBasemap = document.getElementById("toggle-cadastral-basemap");
            const btnVeg = document.getElementById("toggle-veg");

            // --- Additive: highlight buildings by NDVI vegetation evidence ---
            // Does NOT hide any building; only recolours the extrusions and shows
            // a legend so a reviewer can see where the surface elevation may be
            // vegetation rather than structure.
            if (btnVeg) {
                btnVeg.addEventListener("click", function () {
                    vegHighlightOn = !vegHighlightOn;
                    btnVeg.classList.toggle("active-veg", vegHighlightOn);
                    const vegLegend = document.getElementById("veg-legend");
                    if (vegLegend) vegLegend.hidden = !vegHighlightOn;
                    if (map.getLayer("buildings-3d-layer")) {
                        map.setPaintProperty(
                            "buildings-3d-layer",
                            "fill-extrusion-color",
                            vegHighlightOn ? VEG_COLOR_EXPR : BASE_COLOR_EXPR
                        );
                    }
                });
            }

            // Enhanced Cadastral Basemap Projection Toggle
            if (btnCadastralBasemap) {
                let isCadastralView = false;

                btnCadastralBasemap.addEventListener("click", function () {
                    isCadastralView = !isCadastralView;
                    btnCadastralBasemap.classList.toggle("active-cadastral", isCadastralView);

                    if (isCadastralView) {
                        // 1. Orthogonal top-down 2D camera
                        map.flyTo({
                            center: [77.6200, 12.9300],
                            zoom: 16.5,
                            pitch: 0,
                            bearing: 0,
                            duration: 1200
                        });

                        // 2. Flatten 3D extrusions into 2D footprint overlays
                        if (map.getLayer("buildings-3d-layer")) {
                            map.setPaintProperty("buildings-3d-layer", "fill-extrusion-height", 0);
                            map.setPaintProperty("buildings-3d-layer", "fill-extrusion-opacity", 0.15);
                        }

                        // 3. Subtle parcel fill tint
                        if (map.getLayer("parcels-layer")) {
                            map.setLayoutProperty("parcels-layer", "visibility", "visible");
                            map.setPaintProperty("parcels-layer", "fill-color", "#38bdf8");
                            map.setPaintProperty("parcels-layer", "fill-opacity", 0.08);
                        }

                        // 4. Neon cyan boundary lines
                        if (map.getLayer("parcels-line-layer")) {
                            map.setLayoutProperty("parcels-line-layer", "visibility", "visible");
                            map.setPaintProperty("parcels-line-layer", "line-color", "#00f2fe");
                            map.setPaintProperty("parcels-line-layer", "line-width", 2.5);
                            map.setPaintProperty("parcels-line-layer", "line-opacity", 0.95);
                        }
                    } else {
                        // Reset back to standard 3D view
                        map.flyTo({
                            pitch: 60,
                            bearing: -20,
                            zoom: 15,
                            duration: 1200
                        });

                        // Restore 3D Extrusions
                        const heightField = resToggle && resToggle.checked ? "building_height_m_simulated" : "building_height_m";

                        if (map.getLayer("buildings-3d-layer")) {
                            map.setPaintProperty("buildings-3d-layer", "fill-extrusion-height", [
                                "coalesce", ["get", heightField], ["get", "building_height_m_simulated"], ["get", "building_height_m"], 10
                            ]);
                            map.setPaintProperty("buildings-3d-layer", "fill-extrusion-opacity", 0.85);
                        }

                        // Restore default parcel styling
                        if (map.getLayer("parcels-layer")) {
                            map.setPaintProperty("parcels-layer", "fill-color", isLightMode ? "#000000" : "#ffffff");
                            map.setPaintProperty("parcels-layer", "fill-opacity", 0.05);
                        }
                        if (map.getLayer("parcels-line-layer")) {
                            map.setPaintProperty("parcels-line-layer", "line-color", isLightMode ? "#000000" : "#ffffff");
                            map.setPaintProperty("parcels-line-layer", "line-width", 1);
                            map.setPaintProperty("parcels-line-layer", "line-opacity", 0.3);
                        }
                    }
                });
            }

            if (btnTheme) {
                btnTheme.addEventListener("click", async function () {
                    document.body.classList.toggle("light-mode");
                    isLightMode = document.body.classList.contains("light-mode");
                    btnTheme.innerHTML = isLightMode ? '<i class="ph ph-moon"></i>' : '<i class="ph ph-sun"></i>';

                    try {
                        const targetUrl = isLightMode
                            ? "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                            : "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
                        const res = await fetch(targetUrl);
                        const styleJson = await res.json();

                        if (parcelsData && bldgsData) {
                            styleJson.sources["satellite"] = {
                                "type": "raster",
                                "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                                "tileSize": 256,
                                "attribution": "Tiles &copy; Esri"
                            };
                            styleJson.sources["parcels"] = { type: "geojson", data: parcelsData };
                            styleJson.sources["buildings"] = { type: "geojson", data: bldgsData, promoteId: "id" };

                            styleJson.layers.push({
                                "id": "satellite-layer",
                                "type": "raster",
                                "source": "satellite",
                                "layout": { "visibility": isSatellite ? "visible" : "none" }
                            });

                            styleJson.layers.push({
                                "id": "parcels-layer",
                                "type": "fill",
                                "source": "parcels",
                                "paint": {
                                    "fill-color": isSatellite ? "#fbbf24" : (isLightMode ? "#000000" : "#ffffff"),
                                    "fill-opacity": isSatellite ? 0.15 : 0.05,
                                    "fill-outline-color": isSatellite ? "#fbbf24" : (isLightMode ? "#000000" : "#ffffff")
                                }
                            });

                            styleJson.layers.push({
                                "id": "parcels-line-layer",
                                "type": "line",
                                "source": "parcels",
                                "paint": {
                                    "line-color": isSatellite ? "#fbbf24" : (isLightMode ? "#000000" : "#ffffff"),
                                    "line-opacity": isSatellite ? 0.8 : 0.3,
                                    "line-width": isSatellite ? 2 : 1,
                                    "line-dasharray": [2, 2]
                                }
                            });

                            const hField = resToggle && resToggle.checked ? "building_height_m_simulated" : "building_height_m";

                            styleJson.layers.push({
                                "id": "buildings-3d-layer",
                                "type": "fill-extrusion",
                                "source": "buildings",
                                "paint": {
                                    "fill-extrusion-color": [
                                        "case",
                                        ["==", ["feature-state", "reviewer_status"], "APPROVE"], "#10b981",
                                        ["==", ["feature-state", "reviewer_status"], "CORRECT"], "#3b82f6",
                                        ["==", ["feature-state", "reviewer_status"], "REJECT"], "#ef4444",
                                        ["==", ["feature-state", "reviewer_status"], "UNRESOLVED"], "#f59e0b",
                                        [
                                            "match",
                                            ["get", "3d_representation_status"],
                                            "EXACT STRUCTURED 3D", "#3b82f6",
                                            "HEIGHT-DERIVED MASS", "#10b981",
                                            "2D FOOTPRINT ONLY", "#f59e0b",
                                            [
                                                "match",
                                                ["get", "match_status_2d"],
                                                "CONTAINED", "#10b981",
                                                "MAJORITY", "#f59e0b",
                                                "BOUNDARY_OVERLAP", "#ef4444",
                                                "#64748b"
                                            ]
                                        ]
                                    ],
                                    "fill-extrusion-height": [
                                        "coalesce", ["get", hField], ["get", "building_height_m_simulated"], ["get", "building_height_m"], 10
                                    ],
                                    "fill-extrusion-base": 0,
                                    "fill-extrusion-opacity": 0.85
                                }
                            });
                        }

                        map.setStyle(styleJson);

                        // Re-apply the vegetation highlight after a theme swap rebuilds the layer.
                        if (vegHighlightOn) {
                            map.once("styledata", function () {
                                if (map.getLayer("buildings-3d-layer")) {
                                    map.setPaintProperty(
                                        "buildings-3d-layer",
                                        "fill-extrusion-color",
                                        VEG_COLOR_EXPR
                                    );
                                }
                            });
                        }
                    } catch (err) {
                        console.error("Failed to load style", err);
                    }
                });
            }

            if (btnMapStyle) {
                btnMapStyle.addEventListener("click", function () {
                    isSatellite = !isSatellite;
                    btnMapStyle.classList.toggle("active-satellite", isSatellite);

                    if (isSatellite) {
                        if (map.getLayer("satellite-layer")) {
                            map.setLayoutProperty("satellite-layer", "visibility", "visible");
                        }
                        if (map.getLayer("parcels-layer")) {
                            map.setPaintProperty("parcels-layer", "fill-color", "#fbbf24");
                            map.setPaintProperty("parcels-layer", "fill-opacity", 0.15);
                            map.setPaintProperty("parcels-layer", "fill-outline-color", "#fbbf24");
                        }
                        if (map.getLayer("parcels-line-layer")) {
                            map.setPaintProperty("parcels-line-layer", "line-color", "#fbbf24");
                            map.setPaintProperty("parcels-line-layer", "line-opacity", 0.8);
                            map.setPaintProperty("parcels-line-layer", "line-width", 2);
                        }
                    } else {
                        if (map.getLayer("satellite-layer")) {
                            map.setLayoutProperty("satellite-layer", "visibility", "none");
                        }
                        if (map.getLayer("parcels-layer")) {
                            map.setPaintProperty("parcels-layer", "fill-color", isLightMode ? "#000000" : "#ffffff");
                            map.setPaintProperty("parcels-layer", "fill-opacity", 0.05);
                            map.setPaintProperty("parcels-layer", "fill-outline-color", isLightMode ? "#000000" : "#ffffff");
                        }
                        if (map.getLayer("parcels-line-layer")) {
                            map.setPaintProperty("parcels-line-layer", "line-color", isLightMode ? "#000000" : "#ffffff");
                            map.setPaintProperty("parcels-line-layer", "line-opacity", 0.3);
                            map.setPaintProperty("parcels-line-layer", "line-width", 1);
                        }
                    }
                });
            }

            if (btnLeft) {
                btnLeft.addEventListener("click", function () {
                    document.querySelector(".sidebar").classList.toggle("hidden-bar");
                });
            }

            if (btnRight) {
                btnRight.addEventListener("click", function () {
                    document.querySelector(".right-sidebar").classList.toggle("hidden-bar");
                });
            }

            const tabInfo = document.getElementById("tab-info");
            const tabLogs = document.getElementById("tab-logs");
            const contentInfo = document.getElementById("content-info");
            const contentLogs = document.getElementById("content-logs");
            if (tabInfo && tabLogs) {
                tabInfo.addEventListener("click", function () {
                    tabInfo.classList.add("active");
                    tabLogs.classList.remove("active");
                    contentInfo.classList.remove("hidden");
                    contentLogs.classList.add("hidden");
                });
                tabLogs.addEventListener("click", function () {
                    tabLogs.classList.add("active");
                    tabInfo.classList.remove("active");
                    contentLogs.classList.remove("hidden");
                    contentInfo.classList.add("hidden");
                });
            }

        } catch (error) {
            console.error(error);
            const loaderEl = document.getElementById("loader");
            if (loaderEl) {
                loaderEl.innerHTML = '<p style="color: #ef4444;">Error loading GIS data. Check console.</p>';
            }
        }
    });
});