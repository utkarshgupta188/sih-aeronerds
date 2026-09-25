/* ============================================================================
 * floor3d.js  -  interactive 3D building model for the Floor-Level Spatial
 * Inspection panel. Vanilla Three.js (r128, global THREE + THREE.OrbitControls).
 *
 * Replaces the flat 2D elevation schematic with a real extruded building:
 *   - one lit, bevelled slab per ESTIMATED / OBSERVED floor
 *   - orbit (drag) + zoom (wheel / pinch), pointer events contained to canvas
 *   - each slab is a pickable mesh: hover highlights, click selects + reports
 *   - floor labels + EST. badge + ground/DEM reference stay visible in-scene
 *   - footprint outline comes from the real building geometry (data-bound)
 *
 * All dimensions are driven by the caller's model (floor count, height, ground
 * elevation, footprint ring) - nothing is hardcoded. If THREE is unavailable
 * (offline / CDN blocked) mount() returns null and the caller falls back to SVG.
 * ==========================================================================*/
(function () {
    "use strict";

    function has3d() {
        return typeof window.THREE !== "undefined" && typeof window.THREE.OrbitControls !== "undefined";
    }

    // ---- local equirectangular projection of a lng/lat ring to metres --------
    function projectRing(ring) {
        if (!ring || ring.length < 3) return null;
        var lat0 = 0, lon0 = 0, k = 0, i;
        for (i = 0; i < ring.length; i++) {
            if (!ring[i] || typeof ring[i][0] !== "number" || typeof ring[i][1] !== "number") continue;
            lon0 += ring[i][0]; lat0 += ring[i][1]; k++;
        }
        if (k < 3) return null;
        lat0 /= k; lon0 /= k;
        var mPerLat = 111320, mPerLon = 111320 * Math.cos(lat0 * Math.PI / 180);
        var pts = [];
        for (i = 0; i < ring.length; i++) {
            if (!ring[i] || typeof ring[i][0] !== "number" || typeof ring[i][1] !== "number") continue;
            pts.push([(ring[i][0] - lon0) * mPerLon, -(ring[i][1] - lat0) * mPerLat]);
        }
        // drop duplicate closing vertex
        if (pts.length > 3) {
            var a = pts[0], b = pts[pts.length - 1];
            if (Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6) pts.pop();
        }
        return pts.length >= 3 ? pts : null;
    }

    function makeTextSprite(THREE, text, colorHex, maxAniso) {
        var pr = 2, W = 320, H = 150;
        var c = document.createElement("canvas");
        c.width = W * pr; c.height = H * pr;
        var x = c.getContext("2d");
        x.scale(pr, pr);
        x.font = '700 44px Inter, system-ui, -apple-system, sans-serif';
        x.textAlign = "center"; x.textBaseline = "middle";
        x.shadowColor = "rgba(3,8,18,0.75)"; x.shadowBlur = 7; x.shadowOffsetY = 1;
        x.fillStyle = "#f4fbff";
        x.fillText(text, W / 2, H / 2);
        var tex = new THREE.CanvasTexture(c);
        tex.needsUpdate = true;
        tex.minFilter = THREE.LinearFilter;
        if (maxAniso) tex.anisotropy = maxAniso;
        var mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
        mat.color.set(colorHex || "#9fb4cc");
        var s = new THREE.Sprite(mat);
        s.scale.set(1.35, 0.63, 1);
        s.userData.tex = tex; s.userData.mat = mat;
        return s;
    }

    /**
     * mount(container, model) -> controller | null
     * model = {
     *   floors:int, heightM:number, groundElev:number|null,
     *   accentHex:string, est:boolean, ring:[[lng,lat]...]|null,
     *   floorLabel:function(i0)->string, floorMeta:function(i0)->string|null,
     *   onSelect:function(i0)   // fired only on user canvas click
     * }
     */
    function mount(container, model) {
        if (!has3d() || !container || !model) return null;
        var THREE = window.THREE;

        // tear down anything previously mounted here
        if (container.__floor3d) { try { container.__floor3d.dispose(); } catch (e) { /* noop */ } }

        var floors = Math.max(1, model.floors | 0);
        var heightM = (typeof model.heightM === "number" && model.heightM > 0)
            ? model.heightM : floors * 3.2;
        var accent = model.accentHex || "#38bdf8";

        // ---- DOM: wrap + overlay chips ------------------------------------
        var wrap = document.createElement("div");
        wrap.className = "f3d-wrap";
        var hint = document.createElement("div");
        hint.className = "f3d-hint";
        hint.textContent = "drag to rotate  ·  scroll to zoom";
        wrap.appendChild(hint);
        if (model.est) {
            var badge = document.createElement("div");
            badge.className = "f3d-badge";
            badge.textContent = "EST.";
            wrap.appendChild(badge);
        }
        var tip = document.createElement("div");
        tip.className = "f3d-tip";
        tip.hidden = true;
        wrap.appendChild(tip);
        container.appendChild(wrap);

        // ---- renderer / scene / camera ----------------------------------
        var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(1, 1, false);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        if ("outputEncoding" in renderer) renderer.outputEncoding = THREE.sRGBEncoding;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.15;
        renderer.domElement.className = "f3d-canvas";
        wrap.appendChild(renderer.domElement);
        var maxAniso = renderer.capabilities.getMaxAnisotropy
            ? renderer.capabilities.getMaxAnisotropy() : 0;

        var scene = new THREE.Scene();
        var camera = new THREE.PerspectiveCamera(42, 1, 0.05, 400);

        var controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.09;
        controls.enablePan = false;
        controls.rotateSpeed = 0.9;
        controls.zoomSpeed = 0.9;
        controls.autoRotateSpeed = 1.4;
        controls.maxPolarAngle = Math.PI * 0.495;   // never dip under the ground

        // ---- lighting (soft ambient + key + cool cyan fill) --------------
        scene.add(new THREE.HemisphereLight(0xbfe4ff, 0x0a1622, 0.55));
        var key = new THREE.DirectionalLight(0xffffff, 0.95);
        key.position.set(6, 11, 7);
        key.castShadow = true;
        key.shadow.mapSize.set(1024, 1024);
        key.shadow.bias = -0.00045;
        key.shadow.camera.near = 0.5;
        key.shadow.camera.far = 60;
        key.shadow.camera.left = -8; key.shadow.camera.right = 8;
        key.shadow.camera.top = 8; key.shadow.camera.bottom = -8;
        scene.add(key);
        var fill = new THREE.DirectionalLight(0x2fb8d8, 0.28);
        fill.position.set(-6, 4, -6);
        scene.add(fill);

        var root = new THREE.Group();
        scene.add(root);

        // ---- footprint shape (real geometry, else a plain rectangle) -----
        var proj = projectRing(model.ring);
        var minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, i;
        if (proj) {
            for (i = 0; i < proj.length; i++) {
                minX = Math.min(minX, proj[i][0]); maxX = Math.max(maxX, proj[i][0]);
                minZ = Math.min(minZ, proj[i][1]); maxZ = Math.max(maxZ, proj[i][1]);
            }
        } else {
            minX = -6; maxX = 6; minZ = -4.5; maxZ = 4.5;
        }
        var cX = (minX + maxX) / 2, cZ = (minZ + maxZ) / 2;
        var spanM = Math.max(maxX - minX, maxZ - minZ, 4);
        var unit = 3.2 / spanM;                       // world units per metre
        var shape = new THREE.Shape();
        if (proj) {
            shape.moveTo((proj[0][0] - cX) * unit, (proj[0][1] - cZ) * unit);
            for (i = 1; i < proj.length; i++) shape.lineTo((proj[i][0] - cX) * unit, (proj[i][1] - cZ) * unit);
            shape.closePath();
        } else {
            var hw = (maxX - minX) / 2 * unit, hd = (maxZ - minZ) / 2 * unit;
            shape.moveTo(-hw, -hd); shape.lineTo(hw, -hd);
            shape.lineTo(hw, hd); shape.lineTo(-hw, hd); shape.closePath();
        }
        var footW = (maxX - minX) * unit, footD = (maxZ - minZ) * unit;
        var totalH = heightM * unit;
        var floorH = totalH / floors;
        var bevel = Math.min(0.05, floorH * 0.18, footW * 0.06);
        var gap = Math.min(floorH * 0.06, 0.02);

        // ---- per-floor slabs -------------------------------------------
        var cAccent = new THREE.Color(accent);
        var cDark = new THREE.Color(0x0b1220);
        var baseA = cAccent.clone().lerp(cDark, 0.74);
        var baseB = cAccent.clone().lerp(cDark, 0.66);
        var slabs = [];
        var exploded = false;

        function slabY(idx) {
            var spread = exploded ? floorH * 0.55 : 0;
            return idx * (floorH + spread) + bevel;
        }

        for (i = 0; i < floors; i++) {
            var depth = Math.max(floorH - gap, floorH * 0.5);
            var gBevel = new THREE.ExtrudeGeometry(shape, {
                depth: depth, bevelEnabled: true, bevelThickness: bevel,
                bevelSize: bevel, bevelSegments: 2, steps: 1
            });
            gBevel.rotateX(-Math.PI / 2);            // extrude up +Y

            var mat = new THREE.MeshStandardMaterial({
                color: (i % 2 ? baseB : baseA).clone(),
                roughness: 0.5, metalness: 0.1,
                transparent: true, opacity: 0.94
            });
            var mesh = new THREE.Mesh(gBevel, mat);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            mesh.position.y = slabY(i);
            mesh.userData.floor = i;

            var gPlain = new THREE.ExtrudeGeometry(shape, { depth: depth, bevelEnabled: false, steps: 1 });
            gPlain.rotateX(-Math.PI / 2);
            var edges = new THREE.LineSegments(
                new THREE.EdgesGeometry(gPlain, 1),
                new THREE.LineBasicMaterial({ color: cAccent.clone(), transparent: true, opacity: 0.32 })
            );
            gPlain.dispose();
            mesh.add(edges);

            var label = makeTextSprite(THREE, model.floorLabel ? model.floorLabel(i) : ("F" + i),
                "#9fb4cc", maxAniso);
            label.position.set(0, depth / 2, Math.max(footD, footW) * 0.5 + 0.55);
            mesh.add(label);

            root.add(mesh);
            slabs.push({ mesh: mesh, mat: mat, edges: edges, label: label, base: baseA.clone(), depth: depth });
            if (i % 2) slabs[i].base = baseB.clone();
        }

        // ---- ground plane + DEM reference ------------------------------
        var gRad = Math.max(footW, footD) * 1.25 + 0.6;
        var ground = new THREE.Mesh(
            new THREE.CircleGeometry(gRad, 72),
            new THREE.MeshStandardMaterial({ color: 0x0c1a2b, roughness: 1, metalness: 0 })
        );
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = 0;
        ground.receiveShadow = true;
        scene.add(ground);

        var grid = new THREE.GridHelper(gRad * 2, 16, 0x2b4560, 0x1b2c40);
        grid.position.y = 0.004;
        if (grid.material) { grid.material.transparent = true; grid.material.opacity = 0.35; }
        scene.add(grid);

        var ringPts = [], RS = 72;
        for (i = 0; i <= RS; i++) {
            var ang = (i / RS) * Math.PI * 2;
            ringPts.push(Math.cos(ang) * gRad, 0, Math.sin(ang) * gRad);
        }
        var ringGeom = new THREE.BufferGeometry();
        ringGeom.setAttribute("position", new THREE.Float32BufferAttribute(ringPts, 3));
        var gRing = new THREE.LineLoop(ringGeom, new THREE.LineBasicMaterial({
            color: cAccent.clone(), transparent: true, opacity: 0.3
        }));
        gRing.position.y = 0.006;
        scene.add(gRing);

        var groundTxt = (typeof model.groundElev === "number")
            ? ("GROUND  ·  DEM " + Math.round(model.groundElev) + " m") : "GROUND LEVEL";
        var groundLabel = makeTextSprite(THREE, groundTxt, "#8aa0b8", maxAniso);
        groundLabel.scale.set(1.7, 0.5, 1);
        groundLabel.position.set(0, 0.14, gRad * 0.82);
        scene.add(groundLabel);

        // ---- camera framing ------------------------------------------
        var reach = Math.max(footW, footD, totalH);
        var dist = reach * 1.75 + 1.9;
        camera.position.set(dist * 0.62, totalH * 0.55 + dist * 0.42, dist * 0.86);
        controls.target.set(0, totalH * 0.46, 0);
        controls.minDistance = reach * 0.9 + 0.5;
        controls.maxDistance = dist * 3.0;
        controls.update();
        controls.saveState();

        // ---- selection / hover state -------------------------------
        var selected = null, hovered = null;

        function applyStyles() {
            for (var j = 0; j < slabs.length; j++) {
                var s = slabs[j], isSel = j === selected, isHov = j === hovered;
                s.mat.color.copy(s.base);
                s.mat.emissive.set(isSel ? accent : (isHov ? accent : 0x000000));
                s.mat.emissiveIntensity = isSel ? 0.55 : (isHov ? 0.22 : 0);
                s.mat.opacity = isSel ? 1 : (selected == null ? 0.94 : 0.5);
                s.edges.material.opacity = isSel ? 0.95 : (isHov ? 0.6 : 0.32);
                s.edges.material.color.set(isSel ? "#7dd3fc" : accent);
                var show = slabs.length <= 6 || isSel || isHov || j === 0 || j === slabs.length - 1;
                s.label.visible = show;
                s.label.material.color.set(isSel ? "#e6fbff" : "#9fb4cc");
                s.label.material.opacity = isSel ? 1 : (show ? 0.72 : 0);
            }
        }

        function updateTip() {
            if (selected == null) { tip.hidden = true; return; }
            var lab = model.floorLabel ? model.floorLabel(selected) : ("Floor " + selected);
            var meta = model.floorMeta ? model.floorMeta(selected) : null;
            tip.hidden = false;
            tip.innerHTML = '<div class="f3d-tip-lab">' + escapeHtml(lab) + "</div>"
                + (meta ? '<div class="f3d-tip-id">' + escapeHtml(meta) + "</div>" : "");
        }

        function escapeHtml(t) {
            return String(t == null ? "" : t).replace(/[&<>"']/g, function (ch) {
                return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
            });
        }

        function layoutSlabs() {
            for (var j = 0; j < slabs.length; j++) slabs[j].mesh.position.y = slabY(j);
        }

        // ---- picking -----------------------------------------------
        var ray = new THREE.Raycaster();
        var ndc = new THREE.Vector2();
        var meshes = slabs.map(function (s) { return s.mesh; });

        function pick(ev) {
            var r = renderer.domElement.getBoundingClientRect();
            if (r.width < 2 || r.height < 2) return null;
            ndc.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
            ndc.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
            ray.setFromCamera(ndc, camera);
            var hit = ray.intersectObjects(meshes, false);
            return hit.length ? hit[0].object.userData.floor : null;
        }

        var downPt = null;
        function onDown(ev) { downPt = { x: ev.clientX, y: ev.clientY }; }
        function onUp(ev) {
            if (!downPt) return;
            var moved = Math.hypot(ev.clientX - downPt.x, ev.clientY - downPt.y);
            downPt = null;
            if (moved > 5) return;                 // that was an orbit drag
            var f = pick(ev);
            if (f == null) return;
            selected = f; applyStyles(); updateTip();
            if (model.onSelect) model.onSelect(f);
        }
        function onMove(ev) {
            var f = pick(ev);
            if (f !== hovered) { hovered = f; applyStyles(); }
            renderer.domElement.style.cursor = f == null ? "" : "pointer";
        }
        function onLeave() { if (hovered !== null) { hovered = null; applyStyles(); } }
        function onWheel(ev) { ev.preventDefault(); }   // keep zoom off the panel scroll

        var dom = renderer.domElement;
        dom.addEventListener("pointerdown", onDown);
        dom.addEventListener("pointerup", onUp);
        dom.addEventListener("pointermove", onMove);
        dom.addEventListener("pointerleave", onLeave);
        dom.addEventListener("wheel", onWheel, { passive: false });

        // ---- resize + render loop ---------------------------------
        function resize() {
            var w = wrap.clientWidth || container.clientWidth;
            var h = wrap.clientHeight || container.clientHeight;
            if (w < 2 || h < 2) return;
            renderer.setSize(w, h, false);
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
        }
        var ro = (typeof ResizeObserver !== "undefined") ? new ResizeObserver(resize) : null;
        if (ro) ro.observe(container);
        window.addEventListener("resize", resize);
        requestAnimationFrame(resize);
        // the panel is often still display:none at mount time - catch it once shown
        var t1 = setTimeout(resize, 60), t2 = setTimeout(resize, 240);

        var raf = 0, alive = true;
        function loop() {
            if (!alive) return;
            raf = requestAnimationFrame(loop);
            controls.update();
            renderer.render(scene, camera);
        }
        loop();
        applyStyles();

        // ---- controller ------------------------------------------
        var controller = {
            select: function (i0) {
                selected = (i0 == null || i0 < 0) ? null : Math.min(i0 | 0, slabs.length - 1);
                applyStyles(); updateTip();
            },
            explode: function (on) { exploded = !!on; layoutSlabs(); },
            resetView: function () { controls.reset(); },
            spin: function () { controls.autoRotate = !controls.autoRotate; },
            resize: resize,
            dispose: function () {
                alive = false;
                if (raf) cancelAnimationFrame(raf);
                clearTimeout(t1); clearTimeout(t2);
                if (ro) ro.disconnect();
                window.removeEventListener("resize", resize);
                dom.removeEventListener("pointerdown", onDown);
                dom.removeEventListener("pointerup", onUp);
                dom.removeEventListener("pointermove", onMove);
                dom.removeEventListener("pointerleave", onLeave);
                dom.removeEventListener("wheel", onWheel);
                try { controls.dispose(); } catch (e) { /* noop */ }
                scene.traverse(function (o) {
                    if (o.geometry) o.geometry.dispose();
                    if (o.material) {
                        var m = Array.isArray(o.material) ? o.material : [o.material];
                        m.forEach(function (mm) {
                            if (mm.map) mm.map.dispose();
                            mm.dispose();
                        });
                    }
                });
                try { renderer.dispose(); } catch (e) { /* noop */ }
                if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
                if (container.__floor3d === controller) container.__floor3d = null;
            }
        };
        container.__floor3d = controller;
        return controller;
    }

    window.Floor3D = { available: has3d, mount: mount };
})();
