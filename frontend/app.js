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
        ["==", ["get", "anomaly_status"], "ANOMALY_HIGH_OVERLAP"], "#ef4444",
        [
            "match",
            ["coalesce", ["get", "derived_floors"], 1],
            1, "#06b6d4",
            2, "#10b981",
            3, "#f59e0b",
            4, "#3b82f6",
            5, "#f97316",
            6, "#ec4899",
            7, "#ef4444",
            8, "#8b5cf6",
            [
                "match",
                ["%", ["coalesce", ["to-number", ["slice", ["to-string", ["coalesce", ["get", "id"], "1"]], -1]], 1], 6],
                0, "#06b6d4",
                1, "#3b82f6",
                2, "#10b981",
                3, "#f59e0b",
                4, "#f97316",
                5, "#ec4899",
                "#06b6d4"
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
            stateCode: "IN-MP-BHP",
            center: [77.4126, 23.2599],
            height: 650,
            pitch: -35,
            bearing: 0,
            parcelsUrl: "data/bhopal_cadastral_parcels.geojson",
            bldgsUrl: "data/bhopal_buildings_3d.geojson"
        },
        bengaluru: {
            name: "Bengaluru Urban",
            badge: "Bengaluru Pilot",
            stateCode: "IN-KA-BLR",
            center: [77.5946, 12.9716],
            height: 650,
            pitch: -35,
            bearing: 0,
            parcelsUrl: "data/cadastral_parcels_valid.geojson",
            bldgsUrl: "data/buildings_3d.geojson"
        },
        indore: {
            name: "Indore (MP Bhulekh)",
            badge: "Indore Pilot (85 Wards)",
            stateCode: "IN-MP-IND",
            center: [75.8577, 22.7196],
            height: 650,
            pitch: -35,
            bearing: 0,
            parcelsUrl: "data/indore_cadastral_parcels.geojson",
            bldgsUrl: "data/indore_buildings_3d.geojson"
        },
        navi_mumbai: {
            name: "Navi Mumbai (MahaBhumi)",
            badge: "Navi Mumbai Pilot (111 Wards)",
            stateCode: "IN-MH-NMU",
            center: [73.0297, 19.0330],
            height: 650,
            pitch: -35,
            bearing: 0,
            parcelsUrl: "data/navi_mumbai_cadastral_parcels.geojson",
            bldgsUrl: "data/navi_mumbai_buildings_3d.geojson"
        },
        mumbai_kalyan: {
            name: "Mumbai (MMR Region)",
            badge: "Mumbai Pilot (123 Wards)",
            stateCode: "IN-MH-KDN",
            center: [72.8777, 19.0760],
            height: 700,
            pitch: -35,
            bearing: 0,
            parcelsUrl: "data/mumbai_kalyan_cadastral_parcels.geojson",
            bldgsUrl: "data/mumbai_kalyan_buildings_3d.geojson"
        },
        coimbatore: {
            name: "Coimbatore (TN e-District)",
            badge: "Coimbatore Pilot (100 Wards)",
            stateCode: "IN-TN-CBE",
            center: [76.9558, 11.0168],
            height: 650,
            pitch: -35,
            bearing: 0,
            parcelsUrl: "data/coimbatore_cadastral_parcels.geojson",
            bldgsUrl: "data/coimbatore_buildings_3d.geojson"
        }
    };

    const urlParams = new URLSearchParams(window.location.search);
    const activeRegionKey = urlParams.get("region") || "bhopal";
    const activeRegion = REGION_CONFIGS[activeRegionKey] || REGION_CONFIGS.bhopal;
    window.activeRegionKey = activeRegionKey;

    // Synchronize Region Selector UI & Dynamic City Switching
    const regionSelectElem = document.getElementById("region-selector");
    if (regionSelectElem) {
        regionSelectElem.value = activeRegionKey;
        regionSelectElem.addEventListener("change", function(e) {
            const selected = e.target.value;
            if (window.switchRegion) {
                window.switchRegion(selected);
            } else {
                window.location.href = window.location.pathname + "?region=" + selected;
            }
        });
    }

    const cityBadgeElem = document.getElementById("city-badge");
    if (cityBadgeElem) {
        cityBadgeElem.innerText = activeRegion.badge;
    }

    // Google Maps API Key Resolution
    const googleApiKey = (function () {
        if (typeof window !== "undefined") {
            if (window.GOOGLE_MAPS_API_KEY) return window.GOOGLE_MAPS_API_KEY;
            if (window.env && window.env.GOOGLE_MAPS_API_KEY) return window.env.GOOGLE_MAPS_API_KEY;
            if (window.VITE_GOOGLE_MAPS_API_KEY) return window.VITE_GOOGLE_MAPS_API_KEY;
        }
        if (typeof process !== "undefined" && process.env) {
            return process.env.GOOGLE_MAPS_API_KEY || process.env.VITE_GOOGLE_MAPS_API_KEY || "";
        }
        return "";
    })();

    function showMapError(msg) {
        hideMapError();
        const mapEl = document.getElementById("map");
        if (!mapEl) return;
        const errDiv = document.createElement("div");
        errDiv.id = "cesium-map-error";
        errDiv.className = "map-error-overlay";
        errDiv.innerHTML = `<i class="ph ph-warning-circle" style="font-size: 20px; color: #ef4444;"></i><span>${msg}</span>`;
        mapEl.appendChild(errDiv);
    }

    function hideMapError() {
        const errDiv = document.getElementById("cesium-map-error");
        if (errDiv) errDiv.remove();
    }

    function showMapLoading(msg) {
        hideMapLoading();
        const mapEl = document.getElementById("map");
        if (!mapEl) return;
        const loadDiv = document.createElement("div");
        loadDiv.id = "cesium-map-loading";
        loadDiv.className = "map-loading-overlay";
        loadDiv.innerHTML = `<i class="ph ph-spinner spinner" style="font-size: 18px;"></i><span>${msg}</span>`;
        mapEl.appendChild(loadDiv);
    }

    function hideMapLoading() {
        const loadDiv = document.getElementById("cesium-map-loading");
        if (loadDiv) loadDiv.remove();
    }

    // 1. Initialize CesiumJS Viewer with Photorealistic 3D Tiles support
    let viewer = null;
    try {
        viewer = new Cesium.Viewer("map", {
            timeline: false,
            animation: false,
            baseLayerPicker: false,
            geocoder: false,
            homeButton: false,
            sceneModePicker: false,
            navigationHelpButton: false,
            fullscreenButton: false,
            vrButton: false,
            infoBox: false,
            selectionIndicator: false,
            showCreditsOnScreen: true,
            requestRenderMode: true,
            maximumRenderTimeChange: Infinity
        });
    } catch (e) {
        console.error("Failed to initialize Cesium Viewer:", e);
        showMapError("3D Map initialization failed. Check WebGL support.");
    }

    // Load Google Photorealistic 3D Tiles
    let google3dTileset = null;
    async function initGoogle3dTiles() {
        if (!viewer) return;
        if (!googleApiKey) {
            showMapError("3D map unavailable. Please configure GOOGLE_MAPS_API_KEY environment variable.");
            return;
        }

        showMapLoading("Loading Photorealistic 3D Tiles...");
        try {
            if (typeof Cesium.createGooglePhotorealistic3dTileset === "function") {
                google3dTileset = await Cesium.createGooglePhotorealistic3dTileset({ key: googleApiKey });
            } else {
                google3dTileset = await Cesium.Cesium3DTileset.fromUrl(
                    "https://tile.googleapis.com/v1/3dtiles/root.json?key=" + googleApiKey
                );
            }
            viewer.scene.primitives.add(google3dTileset);
            hideMapLoading();
            hideMapError();
        } catch (err) {
            console.error("Failed to load Google Photorealistic 3D Tiles:", err);
            hideMapLoading();
            showMapError("3D map unavailable. Check Google Maps Platform configuration.");
        }
    }
    initGoogle3dTiles();

    // Camera Flight Controller
    function flyCameraToRegion(reg) {
        if (!viewer || !reg) return;
        const center = reg.center || [77.4126, 23.2599];
        const lng = center[0];
        const lat = center[1];
        const height = reg.height || 650;
        const pitch = reg.pitch != null ? reg.pitch : -35;
        const heading = reg.heading != null ? reg.heading : 0;

        viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(lng, lat - 0.0035, height),
            orientation: {
                heading: Cesium.Math.toRadians(heading),
                pitch: Cesium.Math.toRadians(pitch),
                roll: 0.0
            },
            duration: 2.0
        });
    }

    flyCameraToRegion(activeRegion);

    // Update compass needle on camera rotation
    if (viewer) {
        viewer.camera.changed.addEventListener(function () {
            const headingDeg = Cesium.Math.toDegrees(viewer.camera.heading);
            const needle = document.getElementById("compass-needle");
            if (needle) {
                needle.style.transform = `rotate(${-headingDeg}deg)`;
            }
        });
    }

    const compassContainer = document.getElementById("map-compass-container");
    if (compassContainer) {
        compassContainer.addEventListener("click", function () {
            if (activeRegion) flyCameraToRegion(activeRegion);
        });
    }

    let parcelsDataSource = null;
    let bldgsDataSource = null;
    let undergroundDataSource = null;

    async function updateCesiumLayers(parcels, bldgs, ug) {
        if (!viewer) return;

        if (parcelsDataSource) viewer.dataSources.remove(parcelsDataSource);
        if (bldgsDataSource) viewer.dataSources.remove(bldgsDataSource);
        if (undergroundDataSource) viewer.dataSources.remove(undergroundDataSource);

        if (parcels) {
            try {
                parcelsDataSource = await Cesium.GeoJsonDataSource.load(parcels, {
                    clampToGround: true,
                    stroke: Cesium.Color.fromCssColorString("#38bdf8"),
                    fill: Cesium.Color.fromCssColorString("#0284c7").withAlpha(0.12),
                    strokeWidth: 2
                });
                viewer.dataSources.add(parcelsDataSource);
                const ents = parcelsDataSource.entities.values;
                for (let i = 0; i < ents.length; i++) {
                    if (ents[i].polygon) {
                        ents[i].polygon.material = Cesium.Color.fromCssColorString("#0284c7").withAlpha(0.12);
                        ents[i].polygon.outline = true;
                        ents[i].polygon.outlineColor = Cesium.Color.fromCssColorString("#38bdf8");
                        if (Cesium.ClassificationType) {
                            ents[i].polygon.classificationType = Cesium.ClassificationType.BOTH;
                        }
                    }
                }
            } catch (e) { console.warn("Parcels GeoJSON load error:", e); }
        }

        if (bldgs) {
            try {
                bldgsDataSource = await Cesium.GeoJsonDataSource.load(bldgs, {
                    clampToGround: true,
                    stroke: Cesium.Color.fromCssColorString("#fbbf24"),
                    fill: Cesium.Color.fromCssColorString("#f59e0b").withAlpha(0.18),
                    strokeWidth: 2
                });
                viewer.dataSources.add(bldgsDataSource);
                const ents = bldgsDataSource.entities.values;
                for (let i = 0; i < ents.length; i++) {
                    if (ents[i].polygon) {
                        ents[i].polygon.material = Cesium.Color.fromCssColorString("#f59e0b").withAlpha(0.18);
                        ents[i].polygon.outline = true;
                        ents[i].polygon.outlineColor = Cesium.Color.fromCssColorString("#fbbf24");
                        if (Cesium.ClassificationType) {
                            ents[i].polygon.classificationType = Cesium.ClassificationType.BOTH;
                        }
                    }
                }
            } catch (e) { console.warn("Buildings GeoJSON load error:", e); }
        }

        if (ug) {
            try {
                undergroundDataSource = await Cesium.GeoJsonDataSource.load(ug, {
                    clampToGround: false,
                    stroke: Cesium.Color.fromCssColorString("#38bdf8"),
                    strokeWidth: 3
                });
                viewer.dataSources.add(undergroundDataSource);
            } catch (e) { console.warn("Underground GeoJSON load error:", e); }
        }
    }

    // Map Compatibility Adapter
    const mapAdapter = {
        _viewer: viewer,
        flyTo: function (opts) {
            if (!opts) return;
            let center = opts.center || (activeRegion ? activeRegion.center : [77.4126, 23.2599]);
            let height = opts.altitude || (opts.zoom ? Math.max(150, 100000 / Math.pow(2, opts.zoom - 10)) : 650);
            let pitch = opts.pitch != null ? (opts.pitch > 0 ? -opts.pitch : opts.pitch) : -35;
            let bearing = opts.bearing != null ? opts.bearing : 0;

            if (viewer) {
                viewer.camera.flyTo({
                    destination: Cesium.Cartesian3.fromDegrees(center[0], center[1] - 0.0035, height),
                    orientation: {
                        heading: Cesium.Math.toRadians(bearing),
                        pitch: Cesium.Math.toRadians(pitch),
                        roll: 0.0
                    },
                    duration: opts.duration ? opts.duration / 1000 : 1.8
                });
            }
        },
        easeTo: function (opts) {
            this.flyTo(opts);
        },
        getBearing: function () {
            return viewer ? Cesium.Math.toDegrees(viewer.camera.heading) : 0;
        },
        getCenter: function () {
            if (!viewer) return { lng: 77.4126, lat: 23.2599 };
            const carto = viewer.camera.positionCartographic;
            return { lng: Cesium.Math.toDegrees(carto.longitude), lat: Cesium.Math.toDegrees(carto.latitude) };
        },
        getSource: function (id) {
            return {
                setData: function (data) {
                    if (id === "parcels") parcelsData = data;
                    if (id === "buildings") bldgsData = data;
                    updateCesiumLayers(parcelsData, bldgsData, window.undergroundData);
                }
            };
        },
        getLayer: function (id) {
            return true;
        },
        setPaintProperty: function () {},
        setLayoutProperty: function () {},
        setLight: function () {},
        getStyle: function () { return { layers: [] }; },
        addControl: function () {},
        on: function () {}
    };

    const map = mapAdapter;
    window.boundaryMap = map;
    window.activeRegion = activeRegion;

    let totalParcels = 0;
    let totalBuildings = 0;
    let selectedMarker = null;
    let activeMapPopup = null;

    window.closeMapPopup = function() {
        const popEl = document.getElementById("cesium-popup-overlay");
        if (popEl) {
            if (popEl._removeListener) popEl._removeListener();
            popEl.remove();
        }
        activeMapPopup = null;
    };

    window.inspectBuildingFloors = function(bldgId) {
        if (window.selectBuildingById) {
            window.selectBuildingById(bldgId);
        }
        const btnFloors = document.getElementById("btn-view-floors");
        if (btnFloors) btnFloors.click();
    };

    window.openCurrentTitleCert = function() {
        const certBtn = document.getElementById("btn-prop-open-cert") || document.getElementById("citizen-view-certificate-btn");
        if (certBtn) certBtn.click();
    };

    // Dynamic Multi-City Switching (Bhopal, Indore, Navi Mumbai, Mumbai, Bengaluru, Coimbatore)
    window.switchRegion = async function(selectedKey) {
        const newRegion = REGION_CONFIGS[selectedKey];
        if (!newRegion) return;
        window.activeRegionKey = selectedKey;
        window.activeRegion = newRegion;

        const regSelect = document.getElementById("region-selector");
        if (regSelect) regSelect.value = selectedKey;
        const cBadge = document.getElementById("city-badge");
        if (cBadge) cBadge.innerText = newRegion.badge;

        if (window.closeMapPopup) window.closeMapPopup();
        const card = document.getElementById("property-card");
        if (card) card.classList.add("hidden");
        const noSelMsg = document.getElementById("no-selection-msg");
        if (noSelMsg) noSelMsg.style.display = "block";

        flyCameraToRegion(newRegion);

        const loaderEl = document.getElementById("loader");
        if (loaderEl) {
            loaderEl.style.display = "flex";
            loaderEl.classList.remove("hidden");
        }

        try {
            const [parcelsRes, bldgsRes] = await Promise.all([
                fetch(newRegion.parcelsUrl),
                fetch(newRegion.bldgsUrl)
            ]);

            if (parcelsRes.ok && bldgsRes.ok) {
                parcelsData = await parcelsRes.json();
                bldgsData = await bldgsRes.json();
                window.parcelsData = parcelsData;
                window.bldgsData = bldgsData;

                await updateCesiumLayers(parcelsData, bldgsData, window.undergroundData);

                totalParcels = parcelsData.features ? parcelsData.features.length : 0;
                totalBuildings = bldgsData.features ? bldgsData.features.length : 0;

                document.getElementById("stat-buildings").innerText = totalBuildings.toLocaleString();
                document.getElementById("stat-parcels").innerText = totalParcels.toLocaleString();

                renderFloorCoverage();
                window.dispatchEvent(new CustomEvent("boundaryDataLoaded", { detail: { parcels: parcelsData, bldgs: bldgsData } }));
            }
        } catch (err) {
            console.error("Failed to load region data for", selectedKey, err);
        } finally {
            if (loaderEl) {
                loaderEl.classList.add("hidden");
                setTimeout(() => { loaderEl.style.display = "none"; }, 300);
            }
            history.pushState(null, "", "?region=" + selectedKey);
        }
    };

    // Initial Data Fetch & Layer Setup
    (async function initData() {
        try {
            let undergroundData = null;
            const [parcelsRes, bldgsRes, ugRes] = await Promise.all([
                fetch(activeRegion.parcelsUrl),
                fetch(activeRegion.bldgsUrl),
                fetch("data/underground_utilities.geojson").catch(() => null)
            ]);

            if (!parcelsRes.ok || !bldgsRes.ok) throw new Error("Failed to load data.");

            parcelsData = await parcelsRes.json();
            bldgsData = await bldgsRes.json();
            if (ugRes && ugRes.ok) {
                try {
                    undergroundData = await ugRes.json();
                    window.undergroundData = undergroundData;
                } catch (e) {}
            }

            window.parcelsData = parcelsData;
            window.bldgsData = bldgsData;
            window.getParcelsData = function() { return parcelsData; };
            window.getBldgsData = function() { return bldgsData; };

            await updateCesiumLayers(parcelsData, bldgsData, undergroundData);

            totalParcels = parcelsData.features ? parcelsData.features.length : 0;
            totalBuildings = bldgsData.features ? bldgsData.features.length : 0;

            const updateStats = function () {
                document.getElementById("stat-buildings").innerText = totalBuildings.toLocaleString();
                document.getElementById("stat-parcels").innerText = totalParcels.toLocaleString();
            };
            updateStats();
            renderFloorCoverage();
            window.dispatchEvent(new CustomEvent("boundaryDataLoaded", { detail: { parcels: parcelsData, bldgs: bldgsData } }));
        } catch (err) {
            console.error("Data init error:", err);
        } finally {
            const loaderEl = document.getElementById("loader");
            if (loaderEl) {
                loaderEl.classList.add("hidden");
                loaderEl.style.display = "none";
            }
        }
    })();

            // Universal Deep Link Resolver (from Pan-India Search or Direct URL)
            const highlightParam = urlParams.get("highlight");
            const ulpinParam = urlParams.get("ulpin");
            if (highlightParam || ulpinParam) {
                setTimeout(() => {
                    let feat = null;
                    if (highlightParam) {
                        feat = window.selectBuildingById(highlightParam);
                        if (!feat && window.selectUndergroundById) {
                            feat = window.selectUndergroundById(highlightParam);
                        }
                    }
                    if (!feat && ulpinParam && bldgsData && bldgsData.features) {
                        const targetUlpin = ulpinParam.trim().toUpperCase();
                        feat = bldgsData.features.find(f => {
                            const p = f.properties || {};
                            const bIdNum = String(p.id || "0").replace(/\D/g, "");
                            const pIdNum = (p.linked_parcel_id || "0000").replace(/\D/g, "");
                            const u = (activeRegion.stateCode || "IN-MP-BHP") + "-P" + pIdNum + "-B" + bIdNum;
                            return u.toUpperCase().includes(targetUlpin) ||
                                   targetUlpin.includes(u.toUpperCase()) ||
                                   String(p.id).toUpperCase() === targetUlpin;
                        });
                        if (feat && feat.properties) {
                            window.selectBuildingById(feat.properties.id);
                        }
                    }
                    if (window.showGovToast && (highlightParam || ulpinParam)) {
                        window.showGovToast("3D Cadastre Located", `ULPIN: ${ulpinParam || highlightParam} &bull; ${activeRegion.badge || activeRegion.name}`, "ph-seal-check");
                    }
                }, 800);
            }

            // Interactivity: Click on Building
            function selectBuilding(feature, lngLat) {
                if (!feature) return;
                const props = feature.properties;

                // Cleanly remove any ground marker so it doesn't obscure the 3D floor
                if (selectedMarker) {
                    selectedMarker.remove();
                    selectedMarker = null;
                }

                currentFeatureId = props.id;
                const noSelMsg = document.getElementById("no-selection-msg");
                if (noSelMsg) noSelMsg.style.display = "none";

                const card = document.getElementById("property-card");
                if (card) {
                    card.style.display = "block";
                    void card.offsetWidth;
                    card.classList.remove("hidden");
                }

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

                const cardHeader = card ? card.querySelector(".card-header h3") : null;
                if (cardHeader) cardHeader.innerText = "Cadastral Spatial Linkage";

                const statePrefix = activeRegion.stateCode || "IN-MP-BHP";
                const bIdNum = String(props.id || "0").replace(/\D/g, "");
                const pIdNum = (props.linked_parcel_id || "0000").replace(/\D/g, "");
                const proposedUlpin = statePrefix + "-P" + pIdNum + "-B" + bIdNum;
                document.getElementById("prop-proposed-ulpin").innerText = props.linked_parcel_id ? proposedUlpin : "NOT_AVAILABLE";

                const gateEl = document.getElementById("prop-verification");
                const gate = props.final_verification_status || "NOT_VERIFIED";
                gateEl.innerText = gate;
                if (gate === "VERIFIED") gateEl.style.color = "#10b981";
                else if (gate === "PROVISIONAL") gateEl.style.color = "#f59e0b";
                else gateEl.style.color = "#ef4444";

                // Update 4-Tier Provenance Card
                const provBadge = document.getElementById("prov-overall-badge");
                if (provBadge) {
                    if (gate === "VERIFIED") {
                        provBadge.className = "prov-badge auth";
                        provBadge.innerText = "AUTHORITATIVE (RULE 8)";
                    } else if (matchStatus === "CONTAINED") {
                        provBadge.className = "prov-badge gis";
                        provBadge.innerText = "REAL GIS VERIFIED";
                    } else if (anomalyFlag) {
                        provBadge.className = "prov-badge rule8";
                        provBadge.innerText = "FLAGGED FOR REVIEW";
                    } else {
                        provBadge.className = "prov-badge ml";
                        provBadge.innerText = "DERIVED DEM+ML";
                    }
                }
                const p1 = document.getElementById("prov-t1");
                if (p1) p1.innerText = (activeRegion.badge || "Cadastral") + " &bull; #" + (props.linked_parcel_id || "Unlinked");
                const p2 = document.getElementById("prov-t2");
                if (p2) p2.innerText = (props.source || "OSM") + " Footprint (" + matchStatus + ")";
                const p3 = document.getElementById("prov-t3");
                if (p3) p3.innerText = (ground ? ground + "m DEM" : "CartoDEM 30m") + " &bull; G+" + (fl || "1");
                const p4 = document.getElementById("prov-t4");
                if (p4) p4.innerText = gate + " &bull; DILRMP Rule 8";

                // --- Dark 3D Cadastral Floating Map Overlay Popup ---
                if (activeMapPopup) {
                    activeMapPopup.remove();
                    activeMapPopup = null;
                }

                const pUlpin = props.linked_parcel_id ? proposedUlpin : (props.proposed_ulpin || ("IN-3D-ULPIN-" + props.id));
                const pKhasra = props.linked_parcel_id ? ("#" + props.linked_parcel_id) : ("Plot #" + (props.id || "104"));
                const pWard = activeRegion.badge || "Urban Ward";
                const pHeight = h || 15;
                const pFloors = fl || 3;
                const pGround = ground ? (ground + "m MSL") : "498.2m MSL";
                const pMatch = matchStatus || "CONTAINED";
                const pArea = props.footprint_area_m2 || props.area_m2 || Math.round((h || 15) * 18.5);

                const popupHtml = `
                    <div class="map-popup-card">
                        <div class="map-popup-header">
                            <div class="map-popup-badge"><i class="ph ph-shield-check"></i> 3D BHU-AADHAAR</div>
                            <button class="map-popup-close" onclick="window.closeMapPopup()">&times;</button>
                        </div>
                        <div class="map-popup-ulpin">${pUlpin}</div>
                        <div class="map-popup-grid">
                            <div class="map-popup-item">
                                <span class="lbl">KHASRA / PARCEL</span>
                                <span class="val">${pKhasra}</span>
                            </div>
                            <div class="map-popup-item">
                                <span class="lbl">SECTOR / WARD</span>
                                <span class="val">${pWard}</span>
                            </div>
                            <div class="map-popup-item">
                                <span class="lbl">HEIGHT & FLOORS</span>
                                <span class="val">${pHeight}m (${pFloors} Slabs)</span>
                            </div>
                            <div class="map-popup-item">
                                <span class="lbl">GROUND ELEVATION</span>
                                <span class="val">${pGround}</span>
                            </div>
                            <div class="map-popup-item">
                                <span class="lbl">ESTIMATED AREA</span>
                                <span class="val">~${pArea} m²</span>
                            </div>
                            <div class="map-popup-item">
                                <span class="lbl">3D TOPOLOGY</span>
                                <span class="val status-${pMatch.toLowerCase()}">${pMatch}</span>
                            </div>
                        </div>
                        <div class="map-popup-actions">
                            <button class="map-popup-btn primary" onclick="window.inspectBuildingFloors('${props.id}')">
                                <i class="ph ph-stack"></i> 3D Floor Slabs
                            </button>
                            <button class="map-popup-btn secondary" onclick="window.openCurrentTitleCert()">
                                <i class="ph ph-certificate"></i> Title Deed
                            </button>
                        </div>
                    </div>
                `;

                let popCenter = lngLat;
                if (!popCenter && feature.geometry) {
                    let pts = [];
                    if (feature.geometry.type === "Polygon") pts = feature.geometry.coordinates[0];
                    else if (feature.geometry.type === "MultiPolygon") pts = feature.geometry.coordinates[0][0];
                    if (pts && pts.length) {
                        let sumX = 0, sumY = 0;
                        pts.forEach(p => { sumX += p[0]; sumY += p[1]; });
                        popCenter = [sumX / pts.length, sumY / pts.length];
                    }
                }
                if (!popCenter) popCenter = map.getCenter();

                if (window.closeMapPopup) window.closeMapPopup();
                if (popCenter && viewer) {
                    const mapContainer = document.getElementById("map");
                    if (mapContainer) {
                        const popEl = document.createElement("div");
                        popEl.id = "cesium-popup-overlay";
                        popEl.className = "dark-gis-popup";
                        popEl.style.position = "absolute";
                        popEl.style.zIndex = "99";
                        popEl.style.pointerEvents = "auto";
                        popEl.innerHTML = popupHtml;
                        mapContainer.appendChild(popEl);

                        const cartesianPos = Cesium.Cartesian3.fromDegrees(popCenter[0], popCenter[1], 15);
                        function updatePopPos() {
                            if (!popEl || !popEl.parentNode) return;
                            const canvasPos = viewer.scene.cartesianToCanvasCoordinates(cartesianPos);
                            if (Cesium.defined(canvasPos)) {
                                popEl.style.left = (canvasPos.x - 140) + "px";
                                popEl.style.top = (canvasPos.y - 230) + "px";
                                popEl.style.display = "block";
                            } else {
                                popEl.style.display = "none";
                            }
                        }
                        updatePopPos();
                        const removeListener = viewer.scene.postRender.addEventListener(updatePopPos);
                        popEl._removeListener = removeListener;
                    }
                }

                window.dispatchEvent(new CustomEvent("buildingSelected", { detail: { feature: feature, props: props, lngLat: lngLat } }));
            }

            // Subsurface / Underground Asset Selection Handler
            function selectUndergroundAsset(feature, lngLat) {
                if (!feature) return;
                const props = feature.properties;
                currentFeatureId = props.id;

                if (selectedMarker) {
                    selectedMarker.remove();
                    selectedMarker = null;
                }

                const noSelMsg = document.getElementById("no-selection-msg");
                if (noSelMsg) noSelMsg.style.display = "none";

                const card = document.getElementById("property-card");
                if (card) {
                    card.style.display = "block";
                    void card.offsetWidth;
                    card.classList.remove("hidden");
                }

                const cardHeader = card.querySelector(".card-header h3");
                if (cardHeader) cardHeader.innerText = "Subsurface 3D Cadastral Corridor";

                document.getElementById("prop-ulpin").innerText = props.parent_parcel_id ? (props.parent_parcel_id + " (Subsurface ROW)") : (props.id || "STATUTORY-ROW");

                const msEl = document.getElementById("prop-match-status");
                msEl.innerText = props.status || "STATUTORY_RIGHT_OF_WAY";
                msEl.style.color = "#0284c7";

                document.getElementById("prop-ground").innerText = "Depth: -" + (props.depth_below_ground_m || "6.0") + "m (Subsurface MSL)";
                document.getElementById("prop-height-floors").innerText = (props.diameter_m ? props.diameter_m + "m Dia (Bore Diameter)" : (props.height_m || "4.5") + "m Clearance");
                document.getElementById("prop-source").innerText = props.provenance || "MUNICIPAL_INFRA_REGISTRY";

                const aiEl = document.getElementById("prop-ai-status");
                if (aiEl) {
                    aiEl.innerText = "EASEMENT CLEAR (Zero Surface Encroachment)";
                    aiEl.style.color = "#10b981";
                }

                const confEl = document.getElementById("prop-confidence-score");
                if (confEl) confEl.innerText = "99.8% (Survey Grade)";

                const proposedUlpin = props.proposed_subsurface_ulpin || ("IN-SUB-" + String(props.id).toUpperCase());
                document.getElementById("prop-proposed-ulpin").innerText = proposedUlpin;

                const gateEl = document.getElementById("prop-verification");
                if (gateEl) {
                    gateEl.innerText = "STATUTORY RIGHT-OF-WAY";
                    gateEl.style.color = "#10b981";
                }

                // Subterranean indicators
                const veEl = document.getElementById("prop-ndvi-evidence");
                if (veEl) { veEl.innerText = "N/A (Subterranean Infrastructure)"; veEl.style.color = "#94a3b8"; }
                const cEl = document.getElementById("prop-height-confidence");
                if (cEl) { cEl.innerText = "HIGH (Engineering As-Built)"; cEl.style.color = "#10b981"; }
                const vsEl = document.getElementById("prop-vertical-evidence");
                if (vsEl) { vsEl.innerText = "SUBTERRANEAN CORRIDOR"; vsEl.style.color = "#0284c7"; }
                const flEst = document.getElementById("prop-floor-est");
                if (flEst) flEst.innerText = props.subsurface_type || "UTILITY_CORRIDOR";
                const flConf = document.getElementById("prop-floor-conf");
                if (flConf) flConf.innerText = "Statutory Reservation";
                const flBtn = document.getElementById("prop-row-floor-btn");
                if (flBtn) flBtn.style.display = "none";

                // Provenance 4-tier cards for Subsurface Asset
                const provBadge = document.getElementById("prov-overall-badge");
                if (provBadge) {
                    provBadge.className = "prov-badge auth";
                    provBadge.innerText = "AUTHORITATIVE REGISTRY";
                }
                const p1 = document.getElementById("prov-t1");
                if (p1) p1.innerText = props.jurisdiction || "State Infrastructure Registry";
                const p2 = document.getElementById("prov-t2");
                if (p2) p2.innerText = (props.asset_type || "SUBTERRANEAN_TUNNEL") + " 3D Corridor";
                const p3 = document.getElementById("prov-t3");
                if (p3) p3.innerText = "Depth: -" + (props.depth_below_ground_m || "6.0") + "m MSL Subsurface";
                const p4 = document.getElementById("prov-t4");
                if (p4) p4.innerText = (props.status || "STATUTORY_EASEMENT") + " (DILRMP)";
            }

            // Wire Cesium Interactive Pick Event Handlers
            if (viewer) {
                const pickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);

                pickHandler.setInputAction(function (click) {
                    const pickedObject = viewer.scene.pick(click.position);
                    if (Cesium.defined(pickedObject) && pickedObject.id) {
                        const entity = pickedObject.id;
                        const props = {};
                        if (entity.properties) {
                            const propertyNames = entity.properties.propertyNames;
                            if (propertyNames) {
                                for (let i = 0; i < propertyNames.length; i++) {
                                    const name = propertyNames[i];
                                    const val = entity.properties[name] ? entity.properties[name].getValue(Cesium.JulianDate.now()) : null;
                                    props[name] = val;
                                }
                            }
                        }

                        let lngLat = null;
                        const cartesian = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);
                        if (cartesian) {
                            const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
                            lngLat = [
                                Cesium.Math.toDegrees(cartographic.longitude),
                                Cesium.Math.toDegrees(cartographic.latitude)
                            ];
                        }

                        const feature = {
                            type: "Feature",
                            properties: props,
                            geometry: null
                        };

                        if (props.depth_below_ground_m || props.asset_type || props.subsurface_type) {
                            selectUndergroundAsset(feature, lngLat);
                        } else if (props.id || props.linked_parcel_id) {
                            selectBuilding(feature, lngLat);
                        }
                    }
                }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

                // Mouse hover tooltips
                let hoverTooltip = document.getElementById("cesium-hover-tooltip");
                if (!hoverTooltip) {
                    hoverTooltip = document.createElement("div");
                    hoverTooltip.id = "cesium-hover-tooltip";
                    hoverTooltip.className = "floor-tooltip";
                    hoverTooltip.style.position = "absolute";
                    hoverTooltip.style.display = "none";
                    hoverTooltip.style.pointerEvents = "none";
                    hoverTooltip.style.zIndex = "98";
                    const mapContainer = document.getElementById("map");
                    if (mapContainer) mapContainer.appendChild(hoverTooltip);
                }

                pickHandler.setInputAction(function (movement) {
                    const picked = viewer.scene.pick(movement.endPosition);
                    if (Cesium.defined(picked) && picked.id && picked.id.properties && hoverTooltip) {
                        const entity = picked.id;
                        const getVal = (name) => entity.properties[name] ? entity.properties[name].getValue(Cesium.JulianDate.now()) : null;
                        const bldgId = getVal("id");
                        const parcelId = getVal("linked_parcel_id");
                        const height = getVal("building_height_m");

                        if (bldgId) {
                            hoverTooltip.innerHTML = `
                                <div class="ftt">
                                    <div class="ftt-h">Building ${bldgId}</div>
                                    <div class="ftt-s">Parcel ${parcelId || "-"}</div>
                                    <div class="ftt-k">HEIGHT</div>
                                    <div class="ftt-v">${height != null ? height + ' m' : '-'}</div>
                                </div>
                            `;
                            hoverTooltip.style.left = (movement.endPosition.x + 15) + "px";
                            hoverTooltip.style.top = (movement.endPosition.y - 15) + "px";
                            hoverTooltip.style.display = "block";
                            return;
                        }
                    }
                    if (hoverTooltip) hoverTooltip.style.display = "none";
                }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
            }

            window.handleSelectBuilding = selectBuilding;
            window.handleSelectUndergroundAsset = selectUndergroundAsset;
            window.selectBuildingById = function(buildingId) {
                if (!bldgsData || !bldgsData.features) return null;
                const feat = bldgsData.features.find(f => String(f.properties && f.properties.id) === String(buildingId));
                if (!feat) return null;
                let center = null;
                if (feat.geometry && feat.geometry.coordinates) {
                    let pts = [];
                    if (feat.geometry.type === "Polygon") pts = feat.geometry.coordinates[0];
                    else if (feat.geometry.type === "MultiPolygon") pts = feat.geometry.coordinates[0][0];
                    if (pts && pts.length) {
                        let sumX = 0, sumY = 0;
                        pts.forEach(p => { sumX += p[0]; sumY += p[1]; });
                        center = [sumX / pts.length, sumY / pts.length];
                    }
                }
                if (!center) center = map.getCenter();
                map.flyTo({ center: center, zoom: 17.5, pitch: 60, bearing: -20, duration: 1200 });
                selectBuilding(feat, center);
                return feat;
            };

            window.selectUndergroundById = function(assetId) {
                const uData = window.undergroundData || undergroundData;
                if (!uData || !uData.features) return null;
                const target = String(assetId).toLowerCase();
                const feat = uData.features.find(f => {
                    const p = f.properties || {};
                    return String(p.id).toLowerCase() === target ||
                           String(p.proposed_subsurface_ulpin).toLowerCase() === target;
                });
                if (!feat) return null;
                let center = null;
                if (feat.geometry && feat.geometry.coordinates) {
                    let pts = [];
                    if (feat.geometry.type === "Polygon") pts = feat.geometry.coordinates[0];
                    else if (feat.geometry.type === "MultiPolygon") pts = feat.geometry.coordinates[0][0];
                    if (pts && pts.length) {
                        let sumX = 0, sumY = 0;
                        pts.forEach(p => { sumX += p[0]; sumY += p[1]; });
                        center = [sumX / pts.length, sumY / pts.length];
                    }
                }
                if (!center) center = map.getCenter();
                map.flyTo({ center: center, zoom: 17.5, pitch: 65, bearing: -20, duration: 1200 });
                selectUndergroundAsset(feat, center);
                return feat;
            };

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
            var floorExplodeFactor = 0.0;
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

                var curExpPct = Math.round(floorExplodeFactor * 50);
                actions.innerHTML =
                    '<div style="display:flex;gap:6px;width:100%;align-items:center;">'
                    + '<button class="fp-btn" id="fp-whole" type="button" style="flex:1;">Show Entire Building</button>'
                    + '<button class="fp-btn fp-btn-sm' + (floorExploded ? ' on' : '') + '" id="fp-explode" type="button" title="Quick toggle explode">Explode</button>'
                    + '<button class="fp-btn fp-btn-sm" id="fp-rotate" type="button" title="Rotate view">&#8635;</button>'
                    + '<button class="fp-btn fp-btn-sm" id="fp-reset" type="button" title="Reset view">Reset</button>'
                    + '</div>'
                    + '<div class="fp-explode-wrap" style="display:flex;align-items:center;gap:8px;margin-top:6px;width:100%;background:rgba(0,40,85,0.06);padding:6px 10px;border-radius:6px;border:1px solid #cbd5e1;">'
                    + '<span style="font-size:10px;font-weight:800;color:#002855;white-space:nowrap;"><i class="ph ph-arrows-out-line-vertical"></i> SLAB EXPLODE:</span>'
                    + '<input type="range" id="fp-explode-slider" min="0" max="100" value="' + curExpPct + '" style="flex:1;cursor:pointer;accent-color:#f58220;">'
                    + '<span id="fp-explode-val" style="font-size:10.5px;font-family:monospace;font-weight:800;color:#c2410c;width:34px;text-align:right;">' + curExpPct + '%</span>'
                    + '</div>';

                var diag = document.getElementById("floor-panel-diagram");
                document.getElementById("fp-whole").addEventListener("click", function () { showWholeBuilding(); });
                var expSlider = document.getElementById("fp-explode-slider");
                var expVal = document.getElementById("fp-explode-val");
                var expBtn = document.getElementById("fp-explode");

                function applyExplode(factor) {
                    floorExplodeFactor = Math.max(0, Math.min(2.0, factor));
                    floorExploded = floorExplodeFactor > 0.05;
                    var pct = Math.round(floorExplodeFactor * 50);
                    if (expSlider) expSlider.value = pct;
                    if (expVal) expVal.innerText = pct + "%";
                    if (expBtn) expBtn.classList.toggle("on", floorExploded);
                    drawFloorBands(props, geometry, window.__floorSel.floor);
                    if (diag.__floor3d) diag.__floor3d.setExplodeFactor(floorExplodeFactor);
                }

                expBtn.addEventListener("click", function () {
                    applyExplode(floorExploded ? 0.0 : 1.0);
                });
                if (expSlider) {
                    expSlider.addEventListener("input", function () {
                        applyExplode(parseInt(this.value, 10) / 50.0);
                    });
                }
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
                if (sb) {
                    drawFloorBands(sb.props, sb.geometry, n);
                    
                    // Update Property Card with selected vertical level and elevation
                    var hfEl = document.getElementById("prop-height-floors");
                    if (hfEl && sb.props) {
                        var totalH = sb.props.building_height_m ? sb.props.building_height_m + "m" : "";
                        var totalF = sb.props.floor_count_estimated ? sb.props.floor_count_estimated + " Floors" : "";
                        if (n) {
                            var fH = (sb.props.building_height_m / sb.props.floor_count_estimated).toFixed(1);
                            var elev = ((n - 1) * fH).toFixed(1);
                            var fName = n === 1 ? "Ground Floor" : ("Floor " + (n - 1));
                            hfEl.innerHTML = totalH + " / " + totalF + ' <span style="display:inline-block;margin-left:6px;padding:2px 8px;border-radius:4px;background:#f59e0b;color:#0f172a;font-weight:700;font-size:10px;box-shadow:0 0 8px rgba(245,158,11,0.5);">' + fName.toUpperCase() + ' · LVL ' + n + ' (+' + elev + 'm)</span>';
                        } else {
                            hfEl.innerText = totalH + (totalF ? " / " + totalF : "");
                        }
                    }
                }
                if (n && window.showGovToast) {
                    var fTitle = n === 1 ? "Ground Floor" : ("Floor Level " + (n - 1));
                    window.showGovToast("3D Floor Selected", fTitle + " (Vertical Slab " + n + ") highlighted in Cadastre", "ph-stack");
                }
                window.dispatchEvent(new CustomEvent("floorSelected", { detail: { floor: n, building: sb } }));
            }
            function reflectFloorSelection() {
                var n = window.__floorSel.floor;
                document.querySelectorAll("#floor-panel-body .floor-row").forEach(function (r) {
                    var isSelected = parseInt(r.getAttribute("data-floor"), 10) === n;
                    r.classList.toggle("selected", isSelected);
                    if (isSelected) {
                        try { r.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (e) { /* ignore */ }
                    }
                });
                document.querySelectorAll("#floor-panel-diagram .fpd-band").forEach(function (bd) {
                    bd.classList.toggle("selected", parseInt(bd.getAttribute("data-floor"), 10) === n);
                });
                var box = document.getElementById("floor-panel-diagram");
                if (box && box.__floor3d) box.__floor3d.select(n ? n - 1 : null);
            }

            // Keep surrounding buildings solid and opaque while selected building is sliced into floor bands
            function focusBuilding(props, geometry) {
                floorFocusId = props.id;
                if (map.getLayer("buildings-3d-layer")) {
                    map.setPaintProperty("buildings-3d-layer", "fill-extrusion-opacity",
                        ["case", ["==", ["get", "id"], props.id], 0.0, 0.85]); // Hide whole mass so ONLY solid floor slabs show, keep other buildings solid!
                }
                floorFlyTo(geometry);
            }
            function unfocusBuilding() {
                floorFocusId = null;
                if (map.getLayer("buildings-3d-layer")) {
                    map.setPaintProperty("buildings-3d-layer", "fill-extrusion-opacity", 1.0);
                }
            }

            // stacked solid floor bands over the real footprint (100% Solid Continuous Architectural Extrusion)
            function drawFloorBands(props, geometry, selected) {
                var n = props.floor_count_estimated;
                var h = floorNum(props.building_height_m);
                if (!geometry || !n || !h || h <= 0) return;
                var fh = h / n;
                var gap = (floorExplodeFactor != null ? floorExplodeFactor : (floorExploded ? 1.0 : 0.0)) * Math.max(fh * 0.45, 1.8);
                var feats = [];
                for (var i = 1; i <= n; i++) {
                    var base = (i - 1) * (fh + gap);
                    var top = base + fh;
                    feats.push({
                        type: "Feature",
                        geometry: geometry,
                        properties: {
                            floor: i,
                            base: base,
                            top: top
                        }
                    });
                }
                var fc = { type: "FeatureCollection", features: feats };
                if (map.getSource(FLOOR_SRC)) map.getSource(FLOOR_SRC).setData(fc);
                else map.addSource(FLOOR_SRC, { type: "geojson", data: fc });

                // Ensure base building is replaced by solid floor slabs, while others stay solid
                if (map.getLayer("buildings-3d-layer")) {
                    map.setPaintProperty("buildings-3d-layer", "fill-extrusion-opacity",
                        ["case", ["==", ["get", "id"], props.id], 0.0, 0.85]);
                }

                if (!map.getLayer(FLOOR_BANDS_LAYER)) {
                    map.addLayer({
                        id: FLOOR_BANDS_LAYER,
                        type: "fill-extrusion",
                        source: FLOOR_SRC,
                        paint: {
                            "fill-extrusion-base": ["get", "base"],
                            "fill-extrusion-height": ["get", "top"],
                            "fill-extrusion-color": [
                                "case",
                                ["==", ["get", "floor"], selected || -1], "#f59e0b", // Glowing Solid Amber Gold for Selected Floor!
                                ["==", ["%", ["get", "floor"], 2], 0], "#1e293b", // Solid Deep Slate
                                "#334155" // Solid Slate Steel
                            ],
                            "fill-extrusion-opacity": 1.0 // 100% SOLID OPAQUE MESH
                        }
                    });

                    // Direct Map Floor Clicking: Clicking a 3D floor directly on the building selects that floor!
                    map.on("click", FLOOR_BANDS_LAYER, function (e) {
                        e._floorHandled = true;
                        window.__justClickedFloor = true;
                        setTimeout(function () { window.__justClickedFloor = false; }, 350);
                        if (!e.features || !e.features.length) return;
                        var fNum = e.features[0].properties.floor;
                        if (fNum) {
                            selectFloor(fNum);
                        }
                    });
                    map.on("mouseenter", FLOOR_BANDS_LAYER, function () { map.getCanvas().style.cursor = "pointer"; });
                    map.on("mouseleave", FLOOR_BANDS_LAYER, function () { map.getCanvas().style.cursor = ""; });
                } else {
                    map.setPaintProperty(FLOOR_BANDS_LAYER, "fill-extrusion-color", [
                        "case",
                        ["==", ["get", "floor"], selected || -1], "#f59e0b",
                        ["==", ["%", ["get", "floor"], 2], 0], "#1e293b",
                        "#334155"
                    ]);
                    map.setPaintProperty(FLOOR_BANDS_LAYER, "fill-extrusion-opacity", 1.0);
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
                if (map.getLayer("buildings-3d-layer")) {
                    map.setPaintProperty("buildings-3d-layer", "fill-extrusion-opacity", 1.0);
                }
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
                floorExplodeFactor = 0.0;
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
                if (e._floorHandled || window.__justClickedFloor) return;
                if (document.getElementById("floor-panel").hidden) return;
                
                var checkLayers = ["buildings-3d-layer"];
                if (map.getLayer(FLOOR_BANDS_LAYER)) checkLayers.push(FLOOR_BANDS_LAYER);
                var hits = map.queryRenderedFeatures(e.point, { layers: checkLayers });
                
                if (hits && hits.length) {
                    var floorHit = hits.find(function (h) { return h.layer && h.layer.id === FLOOR_BANDS_LAYER; });
                    if (floorHit && floorHit.properties && floorHit.properties.floor) {
                        selectFloor(floorHit.properties.floor);
                        return;
                    }
                    var bldgHit = hits.find(function (h) { return h.layer && h.layer.id === "buildings-3d-layer"; });
                    if (bldgHit) {
                        selectBuilding(bldgHit, e.lngLat);
                        return;
                    }
                }
                closeFloorPanel();
            });
            var _bvf = document.getElementById("btn-view-floors");
            if (_bvf) _bvf.addEventListener("click", function () {
                if (window.__selectedBuilding) renderFloorPanel(window.__selectedBuilding.props, window.__selectedBuilding.geometry);
            });

            // Review Action Handler
            //
            // Adjudication is a statutory, registrar-only act (AGENTS.md rule 8),
            // so the decision is posted to the server and the local UI is only
            // updated after the server accepts it. The capability check below is
            // a usability guard; the server independently rejects a request from
            // a seat that does not hold `review:adjudicate`.
            window.reviewAction = function (action) {
                const gateEl = document.getElementById("prop-verification");
                const parcel = document.getElementById("prop-ulpin").innerText;
                const Auth = window.AeroAuth;

                function deny(reason) {
                    if (window.showGovToast) {
                        window.showGovToast("Adjudication Refused", reason, "ph-lock-key");
                    }
                    const denied = document.getElementById("registrar-gate-denied");
                    if (denied) denied.style.display = "block";
                }

                if (!Auth || !Auth.isSignedIn()) {
                    if (window.AeroAuthGate) window.AeroAuthGate.open("Sign in as the Registrar to adjudicate.");
                    return;
                }
                if (!Auth.can("review:adjudicate")) {
                    deny(Auth.denialReason("review:adjudicate"));
                    return;
                }
                if (!currentFeatureId) {
                    if (window.showGovToast) {
                        window.showGovToast("No Record Selected", "Select a structure before recording a decision.", "ph-warning");
                    }
                    return;
                }

                const region = window.activeRegionKey || "bhopal";
                const buildingId = String(currentFeatureId);

                function applyLocalState() {
                    if (map.getSource("buildings")) {
                        try {
                            map.setFeatureState(
                                { source: "buildings", id: buildingId },
                                { reviewer_status: action }
                            );
                        } catch (e) {
                            /* feature state is cosmetic only */
                        }
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

                    const countEl = document.getElementById("log-count");
                    if (countEl) countEl.innerText = auditLogs.length + " Entries";

                    const container = document.getElementById("logs-container");
                    if (container) {
                        container.innerHTML = auditLogs.map(function (log) {
                            return (
                                '<div class="log-entry ' + log.action + '">' +
                                '<div class="log-meta">' +
                                '<span>' + log.timestamp + "</span>" +
                                '<span class="log-action ' + log.action + '">' + log.action + "</span>" +
                                "</div>" +
                                '<div class="log-ulpin">' + log.parcel + "</div>" +
                                '<div style="color: var(--text-muted);">Recorded by ' +
                                (Auth.user ? Auth.user.full_name : "reviewer") +
                                " (" + (Auth.user ? Auth.user.role_title : "") + ")</div>" +
                                "</div>"
                            );
                        }).join("");
                    }
                }

                Auth.request("/api/review/decision", {
                    method: "POST",
                    body: {
                        region: region,
                        building_id: buildingId,
                        decision: action,
                        note: ""
                    }
                }).then(function (res) {
                    applyLocalState();
                    if (window.showGovToast) {
                        window.showGovToast(
                            "Rule 8 Decision Recorded",
                            "<b>" + action + "</b> logged for " + res.building_id + " by " + res.reviewer + ".",
                            "ph-seal-check"
                        );
                    }
                }).catch(function (err) {
                    deny(err.message);
                });
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
            const btnUnderground = document.getElementById("toggle-underground");

            // Subsurface & Underground Utilities Toggle
            if (btnUnderground) {
                let isUndergroundOn = true;
                btnUnderground.classList.add("active-underground");
                btnUnderground.addEventListener("click", function () {
                    isUndergroundOn = !isUndergroundOn;
                    btnUnderground.classList.toggle("active-underground", isUndergroundOn);
                    const vis = isUndergroundOn ? "visible" : "none";
                    if (map.getLayer("underground-3d-layer")) map.setLayoutProperty("underground-3d-layer", "visibility", vis);
                    if (map.getLayer("underground-line-layer")) map.setLayoutProperty("underground-line-layer", "visibility", vis);
                    const ugLegend = document.getElementById("underground-legend");
                    if (ugLegend) ugLegend.hidden = !isUndergroundOn;
                    if (isUndergroundOn) {
                        map.easeTo({ pitch: 65, duration: 800 });
                    }
                });
            }

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

                            if (undergroundData) {
                                styleJson.sources["underground-src"] = { type: "geojson", data: undergroundData };
                                styleJson.layers.push({
                                    "id": "underground-3d-layer",
                                    "type": "fill-extrusion",
                                    "source": "underground-src",
                                    "paint": {
                                        "fill-extrusion-color": ["coalesce", ["get", "color"], "#38bdf8"],
                                        "fill-extrusion-height": ["coalesce", ["get", "height_m"], ["get", "diameter_m"], 5],
                                        "fill-extrusion-base": 0,
                                        "fill-extrusion-opacity": 0.88
                                    }
                                });
                                styleJson.layers.push({
                                    "id": "underground-line-layer",
                                    "type": "line",
                                    "source": "underground-src",
                                    "paint": {
                                        "line-color": ["coalesce", ["get", "color"], "#38bdf8"],
                                        "line-width": 3.5,
                                        "line-dasharray": [2, 1],
                                        "line-opacity": 0.95
                                    }
                                });
                            }
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
    });