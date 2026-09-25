document.addEventListener("DOMContentLoaded", () => {
    let parcelsData = null;
    let bldgsData = null;
    let isSatellite = false;
    let isLightMode = false;
    let auditLogs = [];
    let currentFeatureId = null;

    // 1. Initialize MapLibre GL JS
    const map = new maplibregl.Map({
        container: 'map',
        style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
        center: [80.2707, 13.0827], // Chennai center
        zoom: 15,
        pitch: 60, // Angled for 3D view
        bearing: -20,
        antialias: true
    });

    // Add navigation controls
    map.addControl(new maplibregl.NavigationControl(), 'bottom-right');

    let totalParcels = 0;
    let totalBuildings = 0;
    let selectedMarker = null;

    map.on('load', async () => {
        try {
            // 2. Load GeoJSON Data
            const [parcelsRes, bldgsRes] = await Promise.all([
                fetch('data/cadastral_parcels_valid.geojson'),
                fetch('data/buildings_3d.geojson')
            ]);
            if (!parcelsRes.ok || !bldgsRes.ok) throw new Error("Failed to load data.");

            parcelsData = await parcelsRes.json();
            bldgsData = await bldgsRes.json();

            totalParcels = parcelsData.features.length;
            totalBuildings = bldgsData.features.length;

            // Update stats panel
            const updateStats = (isSimulated) => {
                document.getElementById('stat-buildings').innerText = totalBuildings.toLocaleString();
                document.getElementById('stat-parcels').innerText = totalParcels.toLocaleString();
            };

            updateStats(false); // Initialize stats

            const addCustomLayers = () => {
                if (!parcelsData || !bldgsData) return;

                if (!map.getSource('satellite')) {
                    map.addSource('satellite', {
                        'type': 'raster',
                        'tiles': [ 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}' ],
                        'tileSize': 256,
                        'attribution': 'Tiles &copy; Esri'
                    });
                }
                if (!map.getLayer('satellite-layer')) {
                    map.addLayer({
                        'id': 'satellite-layer',
                        'type': 'raster',
                        'source': 'satellite',
                        'layout': { 'visibility': isSatellite ? 'visible' : 'none' }
                    });
                }

                if (!map.getSource('parcels')) {
                    map.addSource('parcels', { type: 'geojson', data: parcelsData });
                }
                if (!map.getLayer('parcels-layer')) {
                    map.addLayer({
                        'id': 'parcels-layer',
                        'type': 'fill',
                        'source': 'parcels',
                        'paint': {
                            'fill-color': isSatellite ? '#fbbf24' : (isLightMode ? '#000000' : '#ffffff'),
                            'fill-opacity': isSatellite ? 0.15 : 0.05,
                            'fill-outline-color': isSatellite ? '#fbbf24' : (isLightMode ? '#000000' : '#ffffff')
                        }
                    });
                }
                if (!map.getLayer('parcels-line-layer')) {
                    map.addLayer({
                        'id': 'parcels-line-layer',
                        'type': 'line',
                        'source': 'parcels',
                        'paint': {
                            'line-color': isSatellite ? '#fbbf24' : (isLightMode ? '#000000' : '#ffffff'),
                            'line-opacity': isSatellite ? 0.8 : 0.3,
                            'line-width': isSatellite ? 2 : 1,
                            'line-dasharray': [2, 2]
                        }
                    });
                }

                if (!map.getSource('buildings')) {
                    map.addSource('buildings', { type: 'geojson', data: bldgsData, promoteId: 'id' });
                }
                if (!map.getLayer('buildings-3d-layer')) {
                    map.addLayer({
                        'id': 'buildings-3d-layer',
                        'type': 'fill-extrusion',
                        'source': 'buildings',
                        'paint': {
                            'fill-extrusion-color': [
                                'case',
                                ['==', ['feature-state', 'reviewer_status'], 'APPROVE'], '#10b981',
                                ['==', ['feature-state', 'reviewer_status'], 'CORRECT'], '#3b82f6',
                                ['==', ['feature-state', 'reviewer_status'], 'REJECT'], '#ef4444',
                                ['==', ['feature-state', 'reviewer_status'], 'UNRESOLVED'], '#f59e0b',
                                [
                                    'match',
                                    ['get', 'match_status_2d'],
                                    'CONTAINED', '#10b981',
                                    'MAJORITY', '#f59e0b',
                                    'BOUNDARY_OVERLAP', '#ef4444',
                                    '#64748b'
                                ]
                            ],
                            'fill-extrusion-height': ['coalesce', ['get', 'height_m'], 0],
                            'fill-extrusion-base': 0,
                            'fill-extrusion-opacity': 0.85
                        }
                    });
                }
            };
            
            addCustomLayers();

            // Hide Loader
            document.getElementById('loader').classList.add('hidden');

            // 5. Interactivity: Click on Building
            map.on('click', 'buildings-3d-layer', (e) => {
                if (!e.features.length) return;
                const feature = e.features[0];
                const props = feature.properties;

                // Add or update marker at clicked location
                if (selectedMarker) {
                    selectedMarker.setLngLat(e.lngLat);
                } else {
                    selectedMarker = new maplibregl.Marker({ color: '#ef4444' })
                        .setLngLat(e.lngLat)
                        .addTo(map);
                }

                currentFeatureId = props.id;
                document.getElementById('no-selection-msg').style.display = 'none';

                // Update Sidebar Property Card
                const card = document.getElementById('property-card');
                card.style.display = 'block';
                // Trigger reflow for animation
                void card.offsetWidth;
                card.classList.remove('hidden');

                const isSimulated = document.getElementById('res-toggle').checked;
                const hField = 'height_m';
                const statusField = isSimulated ? '3d_representation_status_simulated' : '3d_representation_status';

                document.getElementById('prop-ulpin').innerText = props.linked_parcel_id || 'NOT AVAILABLE';

                const matchStatus = props.match_status_2d || 'UNKNOWN';
                const msEl = document.getElementById('prop-match-status');
                msEl.innerText = matchStatus;

                if (matchStatus === 'CONTAINED') {
                    msEl.style.color = '#10b981';
                } else if (matchStatus === 'MAJORITY') {
                    msEl.style.color = '#f59e0b';
                } else {
                    msEl.style.color = '#ef4444';
                }

                const ground = props.ground_elevation_m;
                document.getElementById('prop-ground').innerText = ground ? `${ground} m` : 'NOT_DETERMINABLE';

                const h = props[hField];
                let fl = props.derived_floors;

                // If we are simulating high res data, compute floors logically
                if (isSimulated && h != null) {
                    fl = Math.max(1, Math.round(h / 3.5));
                }

                if (h != null && fl != null && fl !== 'NOT_DETERMINABLE') {
                    document.getElementById('prop-height-floors').innerText = `${h}m (${fl} Floors)`;
                } else if (h != null) {
                    document.getElementById('prop-height-floors').innerText = `${h}m (Floors Unknown)`;
                } else {
                    document.getElementById('prop-height-floors').innerText = 'NOT_DETERMINABLE';
                }

                let prov = props.height_source || 'NOT_DETERMINABLE';
                if (isSimulated) {
                    prov = 'GOOGLE_OPEN_BUILDINGS_2.5D'; // Restored text for presentation
                } else if (prov === 'DSM_MINUS_DEM') {
                    prov = 'DSM + DEM + OSM';
                }
                document.getElementById('prop-source').innerText = prov;

                // AI Status
                const anomalyFlag = props.ai_anomaly_flag;
                const anomalyScore = props.ai_anomaly_score || 0;
                const anomalyScoreFmt = props.ai_anomaly_score ? props.ai_anomaly_score.toFixed(4) : "0.0000";

                const aiEl = document.getElementById('prop-ai-status');
                if (anomalyFlag) {
                    aiEl.innerText = `ANOMALY DETECTED (${anomalyScoreFmt})`;
                    aiEl.style.color = '#ef4444';
                } else {
                    aiEl.innerText = `NORMAL (${anomalyScoreFmt})`;
                    aiEl.style.color = '#10b981';
                }

                const confidencePercent = ((1 - anomalyScore) * 100).toFixed(1);
                const confEl = document.getElementById('prop-confidence-score');
                if (confEl) confEl.innerText = `${confidencePercent}%`;

                // Proposed ULPIN Generation
                const bIdNum = props.id.replace(/\D/g, ''); // Extract just numbers from osm_way_123
                const pIdNum = (props.linked_parcel_id || '0000').replace(/\D/g, '');
                const proposedUlpin = `IN-KA-BLR-Pcadastral_parcel_${pIdNum}-Bosm_way_${bIdNum}`;
                document.getElementById('prop-proposed-ulpin').innerText = props.linked_parcel_id ? proposedUlpin : 'NOT_AVAILABLE';

                // Verification Gate
                const gateEl = document.getElementById('prop-verification');
                const gate = props.final_verification_status || 'NOT_VERIFIED';
                gateEl.innerText = gate;
                if (gate === 'VERIFIED') gateEl.style.color = '#10b981';
                else if (gate === 'PROVISIONAL') gateEl.style.color = '#f59e0b';
                else gateEl.style.color = '#ef4444';
            });

            // Change cursor on hover
            window.reviewAction = (action) => {
                const gateEl = document.getElementById('prop-verification');
                const parcel = document.getElementById('prop-ulpin').innerText;

                if (currentFeatureId) {
                    map.setFeatureState(
                        { source: 'buildings', id: currentFeatureId },
                        { reviewer_status: action }
                    );
                }

                if (gateEl) {
                    if (action === 'APPROVE') {
                        gateEl.innerText = 'REVIEWER_APPROVED';
                        gateEl.style.color = 'var(--color-contained)';
                    } else if (action === 'CORRECT') {
                        gateEl.innerText = 'REVIEWER_CORRECTED';
                        gateEl.style.color = 'var(--accent-blue)';
                    } else if (action === 'REJECT') {
                        gateEl.innerText = 'REVIEWER_REJECTED';
                        gateEl.style.color = 'var(--color-conflict)';
                    } else {
                        gateEl.innerText = 'MARK_UNRESOLVED';
                        gateEl.style.color = 'var(--color-majority)';
                    }
                }

                // Add to audit logs
                const timestamp = new Date().toLocaleTimeString();
                auditLogs.unshift({ action, parcel, timestamp });
                
                document.getElementById('log-count').innerText = `${auditLogs.length} Entries`;
                
                const container = document.getElementById('logs-container');
                container.innerHTML = auditLogs.map(log => `
                    <div class="log-entry ${log.action}">
                        <div class="log-meta">
                            <span>${log.timestamp}</span>
                            <span class="log-action ${log.action}">${log.action}</span>
                        </div>
                        <div class="log-ulpin">${log.parcel}</div>
                        <div style="color: var(--text-muted);">Status updated by Surveyor</div>
                    </div>
                `).join('');

                console.log(`[AUDIT LOG - RULE 8] Reviewer Action '${action}' recorded for Parcel: ${parcel}`);
            };

            // Change cursor on hover
            map.on('mouseenter', 'buildings-3d-layer', () => {
                map.getCanvas().style.cursor = 'pointer';
            });
            map.on('mouseleave', 'buildings-3d-layer', () => {
                map.getCanvas().style.cursor = '';
            });

            // Toggle Resolution Logic
            const resToggle = document.getElementById('res-toggle');
            resToggle.addEventListener('change', (e) => {
                const isSimulated = e.target.checked;

                // Update Labels Styling
                document.getElementById('label-strict').classList.toggle('highlight', !isSimulated);
                document.getElementById('label-sim').classList.toggle('highlight', isSimulated);

                // Update overall stats
                updateStats(isSimulated);

                // Repaint Map 3D Layer smoothly
                const heightField = 'height_m';
                map.setPaintProperty('buildings-3d-layer', 'fill-extrusion-height', [
                    'coalesce', ['get', heightField], 0
                ]);

                // If a card is open, hide it to prevent stale data
                if (!document.getElementById('property-card').classList.contains('hidden')) {
                    document.getElementById('property-card').classList.add('hidden');
                }
            });

            // UI Toggles
            const btnTheme = document.getElementById('toggle-theme');
            const btnLeft = document.getElementById('toggle-left-sidebar');
            const btnRight = document.getElementById('toggle-right-sidebar');
            const btnMapStyle = document.getElementById('toggle-map-style');
            
            if (btnTheme) {
                btnTheme.addEventListener('click', async () => {
                    document.body.classList.toggle('light-mode');
                    isLightMode = document.body.classList.contains('light-mode');
                    btnTheme.innerHTML = isLightMode ? '<i class="ph ph-moon"></i>' : '<i class="ph ph-sun"></i>';
                    
                    try {
                        const targetUrl = isLightMode ? 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json' : 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
                        const res = await fetch(targetUrl);
                        const styleJson = await res.json();

                        // Inject custom sources
                        if (parcelsData && bldgsData) {
                            styleJson.sources['satellite'] = {
                                'type': 'raster',
                                'tiles': [ 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}' ],
                                'tileSize': 256,
                                'attribution': 'Tiles &copy; Esri'
                            };
                            styleJson.sources['parcels'] = { type: 'geojson', data: parcelsData };
                            styleJson.sources['buildings'] = { type: 'geojson', data: bldgsData, promoteId: 'id' };

                            // Inject custom layers
                            styleJson.layers.push({
                                'id': 'satellite-layer',
                                'type': 'raster',
                                'source': 'satellite',
                                'layout': { 'visibility': isSatellite ? 'visible' : 'none' }
                            });
                            
                            styleJson.layers.push({
                                'id': 'parcels-layer',
                                'type': 'fill',
                                'source': 'parcels',
                                'paint': {
                                    'fill-color': isSatellite ? '#fbbf24' : (isLightMode ? '#000000' : '#ffffff'),
                                    'fill-opacity': isSatellite ? 0.15 : 0.05,
                                    'fill-outline-color': isSatellite ? '#fbbf24' : (isLightMode ? '#000000' : '#ffffff')
                                }
                            });

                            styleJson.layers.push({
                                'id': 'parcels-line-layer',
                                'type': 'line',
                                'source': 'parcels',
                                'paint': {
                                    'line-color': isSatellite ? '#fbbf24' : (isLightMode ? '#000000' : '#ffffff'),
                                    'line-opacity': isSatellite ? 0.8 : 0.3,
                                    'line-width': isSatellite ? 2 : 1,
                                    'line-dasharray': [2, 2]
                                }
                            });

                            styleJson.layers.push({
                                'id': 'buildings-3d-layer',
                                'type': 'fill-extrusion',
                                'source': 'buildings',
                                'paint': {
                                    'fill-extrusion-color': [
                                        'case',
                                        ['==', ['feature-state', 'reviewer_status'], 'APPROVE'], '#10b981',
                                        ['==', ['feature-state', 'reviewer_status'], 'CORRECT'], '#3b82f6',
                                        ['==', ['feature-state', 'reviewer_status'], 'REJECT'], '#ef4444',
                                        ['==', ['feature-state', 'reviewer_status'], 'UNRESOLVED'], '#f59e0b',
                                        [
                                            'match',
                                            ['get', 'match_status_2d'],
                                            'CONTAINED', '#10b981',
                                            'MAJORITY', '#f59e0b',
                                            'BOUNDARY_OVERLAP', '#ef4444',
                                            '#64748b'
                                        ]
                                    ],
                                    'fill-extrusion-height': ['coalesce', ['get', 'height_m'], 0],
                                    'fill-extrusion-base': 0,
                                    'fill-extrusion-opacity': 0.85
                                }
                            });
                        }
                        
                        map.setStyle(styleJson);
                    } catch (err) {
                        console.error('Failed to load style', err);
                    }
                });
            }

            if (btnMapStyle) {
                btnMapStyle.addEventListener('click', () => {
                    isSatellite = !isSatellite;
                    btnMapStyle.classList.toggle('active-satellite', isSatellite);
                    
                    if (isSatellite) {
                        if (map.getLayer('satellite-layer')) {
                            map.setLayoutProperty('satellite-layer', 'visibility', 'visible');
                        }
                        if (map.getLayer('parcels-layer')) {
                            map.setPaintProperty('parcels-layer', 'fill-color', '#fbbf24');
                            map.setPaintProperty('parcels-layer', 'fill-opacity', 0.15);
                            map.setPaintProperty('parcels-layer', 'fill-outline-color', '#fbbf24');
                        }
                        if (map.getLayer('parcels-line-layer')) {
                            map.setPaintProperty('parcels-line-layer', 'line-color', '#fbbf24');
                            map.setPaintProperty('parcels-line-layer', 'line-opacity', 0.8);
                            map.setPaintProperty('parcels-line-layer', 'line-width', 2);
                        }
                    } else {
                        if (map.getLayer('satellite-layer')) {
                            map.setLayoutProperty('satellite-layer', 'visibility', 'none');
                        }
                        if (map.getLayer('parcels-layer')) {
                            map.setPaintProperty('parcels-layer', 'fill-color', isLightMode ? '#000000' : '#ffffff');
                            map.setPaintProperty('parcels-layer', 'fill-opacity', 0.05);
                            map.setPaintProperty('parcels-layer', 'fill-outline-color', isLightMode ? '#000000' : '#ffffff');
                        }
                        if (map.getLayer('parcels-line-layer')) {
                            map.setPaintProperty('parcels-line-layer', 'line-color', isLightMode ? '#000000' : '#ffffff');
                            map.setPaintProperty('parcels-line-layer', 'line-opacity', 0.3);
                            map.setPaintProperty('parcels-line-layer', 'line-width', 1);
                        }
                    }
                });
            }

            // Expose addCustomLayers to the global map instance so style.load can call it
            map._addCustomLayers = addCustomLayers;

            // No longer using styledata as we inject layers directly into setStyle
            
            if (btnLeft) {
                btnLeft.addEventListener('click', () => {
                    document.querySelector('.sidebar').classList.toggle('hidden-bar');
                });
            }

            if (btnRight) {
                btnRight.addEventListener('click', () => {
                    document.querySelector('.right-sidebar').classList.toggle('hidden-bar');
                });
            }

            // Tabs Logic
            const tabInfo = document.getElementById('tab-info');
            const tabLogs = document.getElementById('tab-logs');
            const contentInfo = document.getElementById('content-info');
            const contentLogs = document.getElementById('content-logs');
            if (tabInfo && tabLogs) {
                tabInfo.addEventListener('click', () => {
                    tabInfo.classList.add('active');
                    tabLogs.classList.remove('active');
                    contentInfo.classList.remove('hidden');
                    contentLogs.classList.add('hidden');
                });
                tabLogs.addEventListener('click', () => {
                    tabLogs.classList.add('active');
                    tabInfo.classList.remove('active');
                    contentLogs.classList.remove('hidden');
                    contentInfo.classList.add('hidden');
                });
            }

        } catch (error) {
            console.error(error);
            document.getElementById('loader').innerHTML = `<p style="color: #ef4444;">Error loading GIS data. Check console.</p>`;
        }
    });
});
