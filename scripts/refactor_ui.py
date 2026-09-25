import re

for filepath, height_field in [('g:/Projects/BoundaryLens/frontend/app.js', 'building_height_m'), ('g:/Projects/BoundaryLens/frontend_chennai/app.js', 'height_m')]:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add global variables
    content = content.replace('const map = new maplibregl.Map({', 'let parcelsData = null;\n    let bldgsData = null;\n    let isSatellite = false;\n    let isLightMode = false;\n\n    const map = new maplibregl.Map({', 1)

    # 2. Extract layer logic
    layer_logic = '''
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
                    'fill-color': isLightMode ? '#000000' : '#ffffff',
                    'fill-opacity': 0.05,
                    'fill-outline-color': isLightMode ? '#000000' : '#ffffff'
                }
            });
        }
        if (!map.getLayer('parcels-line-layer')) {
            map.addLayer({
                'id': 'parcels-line-layer',
                'type': 'line',
                'source': 'parcels',
                'paint': {
                    'line-color': isLightMode ? '#000000' : '#ffffff',
                    'line-opacity': 0.3,
                    'line-width': 1,
                    'line-dasharray': [2, 2]
                }
            });
        }

        if (!map.getSource('buildings')) {
            map.addSource('buildings', { type: 'geojson', data: bldgsData });
        }
        if (!map.getLayer('buildings-3d-layer')) {
            const resToggle = document.getElementById('res-toggle');
            const isSimulated = resToggle ? resToggle.checked : false;
            const hField = isSimulated ? 'HFIELD_simulated' : 'HFIELD';
            map.addLayer({
                'id': 'buildings-3d-layer',
                'type': 'fill-extrusion',
                'source': 'buildings',
                'paint': {
                    'fill-extrusion-color': [
                        'match',
                        ['get', 'match_status_2d'],
                        'CONTAINED', '#10b981',
                        'MAJORITY', '#f59e0b',
                        'BOUNDARY_OVERLAP', '#ef4444',
                        '#64748b'
                    ],
                    'fill-extrusion-height': ['coalesce', ['get', hField], 0],
                    'fill-extrusion-base': 0,
                    'fill-extrusion-opacity': 0.85
                }
            });
        }
    };
'''
    layer_logic = layer_logic.replace('HFIELD', height_field)
    
    # insert addCustomLayers after NavigationControl
    content = content.replace("map.addControl(new maplibregl.NavigationControl(), 'bottom-right');", "map.addControl(new maplibregl.NavigationControl(), 'bottom-right');\n" + layer_logic)

    # replace the inline layer logic with a call to addCustomLayers()
    pattern_layers = re.compile(r'// Add Satellite Source & Layer.*?// Hide Loader', re.DOTALL)
    content = pattern_layers.sub('addCustomLayers();\n            // Hide Loader', content)

    # Note: we need to assign parcelsData and bldgsData without let/const in map.on('load')
    content = content.replace('const parcelsData = await parcelsRes.json();', 'parcelsData = await parcelsRes.json();')
    content = content.replace('const bldgsData = await bldgsRes.json();', 'bldgsData = await bldgsRes.json();')

    # Add style.load listener
    content = content.replace('map.on(\'load\', async () => {', 'map.on(\'style.load\', () => {\n        if (parcelsData && bldgsData) {\n            addCustomLayers();\n        }\n    });\n\n    map.on(\'load\', async () => {')

    # Update toggles
    # Remove old map style toggle listener
    pattern_old_toggle = re.compile(r'// Toggle Base Map Logic.*?}\s*// UI Toggles', re.DOTALL)
    content = pattern_old_toggle.sub('// UI Toggles', content)

    # Update UI toggles to handle map style swapping
    new_toggles = '''
            // UI Toggles
            const btnTheme = document.getElementById('toggle-theme');
            const btnLeft = document.getElementById('toggle-left-sidebar');
            const btnRight = document.getElementById('toggle-right-sidebar');
            const btnMapStyle = document.getElementById('toggle-map-style');
            
            if (btnTheme) {
                btnTheme.addEventListener('click', () => {
                    document.body.classList.toggle('light-mode');
                    isLightMode = document.body.classList.contains('light-mode');
                    btnTheme.innerHTML = isLightMode ? '<i class="ph ph-moon"></i>' : '<i class="ph ph-sun"></i>';
                    
                    // switch map base style
                    if (!isSatellite) {
                        map.setStyle(isLightMode ? 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json' : 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json');
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
                    } else {
                        if (map.getLayer('satellite-layer')) {
                            map.setLayoutProperty('satellite-layer', 'visibility', 'none');
                        }
                        // Ensure base style is correct based on theme
                        map.setStyle(isLightMode ? 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json' : 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json');
                    }
                });
            }
'''
    pattern_new_toggle = re.compile(r'// UI Toggles.*?if \(btnLeft\)', re.DOTALL)
    content = pattern_new_toggle.sub(new_toggles + '\n            if (btnLeft)', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Done")
