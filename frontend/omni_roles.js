/**
 * AeroNerds — Government of India 3D Vertical Cadastral & Bhu-Aadhaar Portal
 * Developed for Ministry of Rural Development (DoLR), MoHUA & Smart India Hackathon (SIH26011)
 * 
 * Features:
 * 1. 3 Official Government Personas:
 *    - Chief Cadastral Surveyor & Registrar (DoLR / State Land Records)
 *    - Municipal Town Planner & Urban Local Body (ULB / Smart City Mission)
 *    - Citizen & Landowner (Bhu-Aadhaar Citizen Portal)
 * 2. Universal Land Records Search (Khasra No., Bhu-Aadhaar 3D ULPIN, Ward, Survey No.)
 * 3. Official 3D Bhu-Aadhaar Land Title Certificate Modal with QR Verification & Download
 * 4. FSI / FAR Height Compliance & Vertical Encroachment Scanner for Town Planners
 * 5. Statutory Reviewer Audit Gate (APPROVE / CORRECT / REJECT / UNRESOLVED)
 * 6. Mutation & Grievance Petition Lodging for Citizens
 * 7. Audio Feedback Engine (Statutory Clicks & Seal Chimes)
 */

(function () {
    "use strict";

    // =========================================================================
    // 1. TACTILE AUDIO SYNTHESIZER
    // =========================================================================
    const AudioFX = {
        ctx: null,
        enabled: true,

        init() {
            if (!this.ctx) {
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                if (AudioContextClass) this.ctx = new AudioContextClass();
            }
            if (this.ctx && this.ctx.state === "suspended") {
                this.ctx.resume();
            }
        },

        play(type) {
            if (!this.enabled) return;
            try {
                this.init();
                if (!this.ctx) return;
                const now = this.ctx.currentTime;

                switch (type) {
                    case "click": {
                        const osc = this.ctx.createOscillator();
                        const gain = this.ctx.createGain();
                        osc.type = "sine";
                        osc.frequency.setValueAtTime(700, now);
                        osc.frequency.exponentialRampToValueAtTime(350, now + 0.04);
                        gain.gain.setValueAtTime(0.06, now);
                        gain.gain.linearRampToValueAtTime(0.001, now + 0.04);
                        osc.connect(gain);
                        gain.connect(this.ctx.destination);
                        osc.start(now);
                        osc.stop(now + 0.04);
                        break;
                    }
                    case "seal": {
                        // Official seal stamped sound (deep resonance + crisp tone)
                        const osc = this.ctx.createOscillator();
                        const gain = this.ctx.createGain();
                        osc.type = "triangle";
                        osc.frequency.setValueAtTime(523.25, now);
                        osc.frequency.exponentialRampToValueAtTime(261.63, now + 0.25);
                        gain.gain.setValueAtTime(0.15, now);
                        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
                        osc.connect(gain);
                        gain.connect(this.ctx.destination);
                        osc.start(now);
                        osc.stop(now + 0.4);
                        break;
                    }
                    case "success": {
                        // Formal chime
                        [523.25, 659.25, 783.99].forEach((freq, idx) => {
                            const t = now + idx * 0.07;
                            const osc = this.ctx.createOscillator();
                            const gain = this.ctx.createGain();
                            osc.type = "sine";
                            osc.frequency.setValueAtTime(freq, t);
                            gain.gain.setValueAtTime(0.09, t);
                            gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
                            osc.connect(gain);
                            gain.connect(this.ctx.destination);
                            osc.start(t);
                            osc.stop(t + 0.25);
                        });
                        break;
                    }
                    case "switch": {
                        const osc = this.ctx.createOscillator();
                        const gain = this.ctx.createGain();
                        osc.type = "sine";
                        osc.frequency.setValueAtTime(300, now);
                        osc.frequency.exponentialRampToValueAtTime(580, now + 0.1);
                        gain.gain.setValueAtTime(0.06, now);
                        gain.gain.linearRampToValueAtTime(0.001, now + 0.1);
                        osc.connect(gain);
                        gain.connect(this.ctx.destination);
                        osc.start(now);
                        osc.stop(now + 0.1);
                        break;
                    }
                }
            } catch (err) {}
        }
    };
    window.BoundaryAudio = AudioFX;

    // Toast notification helper
    function showGovToast(title, msg, icon = "ph-seal-check") {
        let container = document.getElementById("omni-toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "omni-toast-container";
            container.className = "omni-toast-container";
            document.body.appendChild(container);
        }
        const toast = document.createElement("div");
        toast.className = "omni-toast glass-panel";
        toast.innerHTML = `
            <div class="omni-toast-icon"><i class="ph ${icon}"></i></div>
            <div class="omni-toast-content">
                <div class="omni-toast-title">${title}</div>
                <div class="omni-toast-msg">${msg}</div>
            </div>
        `;
        container.appendChild(toast);
        AudioFX.play("click");
        setTimeout(() => {
            toast.classList.add("out");
            setTimeout(() => toast.remove(), 350);
        }, 3200);
    }
    window.showGovToast = showGovToast;
    window.showOmniToast = showGovToast;

    // =========================================================================
    // 2. GOVERNMENT ROLES DEFINITION
    // =========================================================================
    const GOV_ROLES = {
        admin: {
            id: "admin",
            title: "Chief Cadastral Surveyor",
            name: "Dr. S. Nair, DoLR",
            dept: "Directorate of Land Records & SVAMITVA",
            badge: "REGISTRAR",
            badgeClass: "badge-admin",
            icon: "ph-shield-check",
            workspaceId: "admin-workspace",
            subtitle: "Statutory 3D Cadastral Delineation & ULPIN Adjudication Desk"
        },
        planner: {
            id: "planner",
            title: "Town Planning Officer",
            name: "Er. Rajesh Verma",
            dept: "Municipal Urban Local Body (ULB)",
            badge: "TOWN PLANNER",
            badgeClass: "badge-lead",
            icon: "ph-buildings",
            workspaceId: "planner-workspace",
            subtitle: "Vertical FSI / Height Compliance & Encroachment Auditing"
        },
        citizen: {
            id: "citizen",
            title: "Citizen Landowner",
            name: "Smt. Priya Sharma",
            dept: "Bhu-Aadhaar Digital Property Passbook",
            badge: "PROPERTY OWNER",
            badgeClass: "badge-resident",
            icon: "ph-user-circle",
            workspaceId: "citizen-workspace",
            subtitle: "3D Bhu-Aadhaar Passbook & Title Self-Verification"
        }
    };

    let activeGovRole = localStorage.getItem("aeronerds_gov_role") || "admin";
    if (!GOV_ROLES[activeGovRole]) activeGovRole = "admin";

    // =========================================================================
    // 3. CANVAS QR CODE GENERATOR (Bhu-Aadhaar Digital Seal)
    // =========================================================================
    function drawBhuAadhaarQR(canvas, ulpinCode) {
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const size = canvas.width;
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, size, size);

        let hash = 0;
        for (let i = 0; i < ulpinCode.length; i++) {
            hash = ((hash << 5) - hash + ulpinCode.charCodeAt(i)) | 0;
        }

        const grid = 23;
        const cellSize = (size - 16) / grid;
        const offset = 8;

        const drawCorner = (rx, ry) => {
            ctx.fillStyle = "#0f172a";
            ctx.fillRect(offset + rx * cellSize, offset + ry * cellSize, 7 * cellSize, 7 * cellSize);
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(offset + (rx + 1) * cellSize, offset + (ry + 1) * cellSize, 5 * cellSize, 5 * cellSize);
            ctx.fillStyle = "#1e3a8a"; // Ashoka Navy
            ctx.fillRect(offset + (rx + 2) * cellSize, offset + (ry + 2) * cellSize, 3 * cellSize, 3 * cellSize);
        };

        drawCorner(0, 0);
        drawCorner(grid - 7, 0);
        drawCorner(0, grid - 7);

        let seed = Math.abs(hash) || 539281;
        for (let y = 0; y < grid; y++) {
            for (let x = 0; x < grid; x++) {
                if ((x < 8 && y < 8) || (x >= grid - 8 && y < 8) || (x < 8 && y >= grid - 8)) continue;
                seed = (seed * 1664525 + 1013904223) | 0;
                if ((seed >>> 16) % 3 !== 0) {
                    ctx.fillStyle = "#0f172a";
                    ctx.fillRect(offset + x * cellSize, offset + y * cellSize, cellSize - 0.5, cellSize - 0.5);
                }
            }
        }

        // Center Ashoka Emblem Dot
        const center = size / 2;
        ctx.beginPath();
        ctx.arc(center, center, 11, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();

        ctx.beginPath();
        ctx.arc(center, center, 9, 0, Math.PI * 2);
        ctx.fillStyle = "#000080";
        ctx.fill();

        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 8px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("GOI", center, center);
    }

    // =========================================================================
    // 4. PERSONA SWITCHER ENGINE
    // =========================================================================
    function setGovRole(roleKey) {
        if (!GOV_ROLES[roleKey]) roleKey = "admin";
        activeGovRole = roleKey;
        localStorage.setItem("aeronerds_gov_role", roleKey);

        const r = GOV_ROLES[roleKey];
        AudioFX.play("switch");

        // Top bar pill sync
        const pillName = document.getElementById("persona-pill-name");
        const pillRole = document.getElementById("persona-pill-role");
        const pillIcon = document.getElementById("persona-pill-icon");
        const pillBadge = document.getElementById("persona-pill-badge");
        if (pillName) pillName.innerText = r.name;
        if (pillRole) pillRole.innerText = r.title;
        if (pillIcon) pillIcon.className = `ph ${r.icon}`;
        if (pillBadge) {
            pillBadge.innerText = r.badge;
            pillBadge.className = `persona-badge ${r.badgeClass}`;
        }

        // Subtitle sync
        const sub = document.getElementById("sidebar-role-subtitle");
        if (sub) sub.innerText = r.subtitle;

        // Toggle Workspace Views
        document.querySelectorAll(".omni-workspace").forEach(el => {
            el.style.display = "none";
            el.classList.remove("active");
        });
        const targetWorkspace = document.getElementById(r.workspaceId);
        if (targetWorkspace) {
            targetWorkspace.style.display = "block";
            targetWorkspace.classList.add("active");
        }

        // Adjust body classes
        document.body.classList.remove("role-admin", "role-planner", "role-citizen");
        document.body.classList.add(`role-${roleKey}`);

        showGovToast("Official Access Changed", `Switched to: <b>${r.title}</b> (${r.dept})`, r.icon);
    }

    function openGovModal() {
        const modal = document.getElementById("gov-persona-modal");
        if (modal) {
            modal.style.display = "flex";
            AudioFX.play("click");
        }
    }

    function closeGovModal() {
        const modal = document.getElementById("gov-persona-modal");
        if (modal) {
            modal.style.display = "none";
            AudioFX.play("click");
        }
    }

    // =========================================================================
    // 5. OFFICIAL BHU-AADHAAR 3D CERTIFICATE MODAL
    // =========================================================================
    function openCertificateModal(ulpin, khasra, elevation, floors, area) {
        const modal = document.getElementById("certificate-modal");
        if (!modal) return;

        AudioFX.play("seal");
        document.getElementById("cert-ulpin").innerText = ulpin || "IN-MP-BHP-P104-B3-FL4-U402";
        document.getElementById("cert-khasra").innerText = khasra || "Khasra #104/B, Ward 42";
        document.getElementById("cert-elevation").innerText = elevation ? `${elevation} m MSL` : "498.2 m MSL (Bare-Earth DEM)";
        document.getElementById("cert-floors").innerText = floors ? `${floors} Floors` : "4th Floor (G+5 Structure)";
        document.getElementById("cert-area").innerText = area ? `${area} sq.ft` : "1,420 sq.ft (Built-Up)";
        document.getElementById("cert-date").innerText = new Date().toLocaleDateString("en-IN", {
            day: "2-digit", month: "long", year: "numeric"
        });

        const certCanvas = document.getElementById("cert-qr-canvas");
        if (certCanvas) {
            drawBhuAadhaarQR(certCanvas, ulpin || "IN-MP-BHP-P104-B3-FL4-U402");
        }

        modal.style.display = "flex";
    }

    function closeCertificateModal() {
        const modal = document.getElementById("certificate-modal");
        if (modal) {
            modal.style.display = "none";
            AudioFX.play("click");
        }
    }

    // =========================================================================
    // 6. TOWN PLANNING / FSI COMPLIANCE ENGINE
    // =========================================================================
    let fsiViolationFilterOn = false;

    function toggleFsiViolationFilter() {
        const map = window.boundaryMap;
        if (!map) return;
        fsiViolationFilterOn = !fsiViolationFilterOn;
        AudioFX.play("click");

        const btn = document.getElementById("btn-toggle-fsi");
        if (btn) {
            btn.classList.toggle("active", fsiViolationFilterOn);
            btn.innerHTML = fsiViolationFilterOn
                ? `<i class="ph ph-warning-octagon"></i> FSI Violation Filter ACTIVE`
                : `<i class="ph ph-warning-octagon"></i> Scan Vertical FSI / Height Violations`;
        }

        if (map.getLayer("buildings-3d-layer")) {
            if (fsiViolationFilterOn) {
                // Color structures exceeding permissible municipal heights (> 18m without clearance)
                map.setPaintProperty("buildings-3d-layer", "fill-extrusion-color", [
                    "case",
                    [">=", ["coalesce", ["get", "building_height_m"], 0], 20], "#dc2626", // Red: Height Violation / Encroachment
                    [">=", ["coalesce", ["get", "building_height_m"], 0], 12], "#f59e0b", // Amber: Under Municipal Verification
                    "#10b981" // Green: Within Permissible G+2 FSI
                ]);
                showGovToast("Municipal Audit Active", "Red highlights: Structures exceeding permissible FSI height (Notice issued)", "ph-warning-octagon");
            } else {
                // Restore base colors
                map.setPaintProperty("buildings-3d-layer", "fill-extrusion-color", [
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
                ]);
            }
        }
    }

    // =========================================================================
    // 7. UNIVERSAL LAND RECORD SEARCH (KHASRA / BHU-AADHAAR)
    // =========================================================================
    function initGovSearchEngine() {
        const searchInput = document.getElementById("omni-search-input");
        const searchResults = document.getElementById("omni-search-results");
        if (!searchInput || !searchResults) return;

        searchInput.addEventListener("input", function (e) {
            const query = e.target.value.trim().toLowerCase();
            if (query.length < 2) {
                searchResults.style.display = "none";
                searchResults.innerHTML = "";
                return;
            }

            const results = [];

            // Official pilot entries
            const govRecords = [
                { title: "Khasra #104/B (Lotus Heights)", sub: "Ward 42 &bull; Bhu-Aadhaar: IN-MP-BHP-P104 &bull; Owner: Smt. Priya Sharma", type: "khasra", id: "sample_b1" },
                { title: "Bhu-Aadhaar IN-MP-BHP-P104-B3-FL4", sub: "Flat 402, 4th Floor &bull; G+5 Verified RCC &bull; Area: 1420 sq.ft", type: "ulpin", id: "sample_b1" },
                { title: "Khasra #78/A (Silver Crest)", sub: "Ward 42 &bull; Bhu-Aadhaar: IN-MP-BHP-P78 &bull; Owner: Shri Rameshwar", type: "khasra", id: "sample_b2" },
                { title: "Survey Plot #22068 (Bengaluru Pilot)", sub: "South Taluk, Ward 150 &bull; Bhoomi Linked &bull; 100% Contained", type: "khasra", id: "sample_blr" }
            ];

            govRecords.forEach(item => {
                if (item.title.toLowerCase().includes(query) || item.sub.toLowerCase().includes(query)) {
                    results.push(item);
                }
            });

            // Search loaded GeoJSON buildings/parcels
            const bData = window.getBldgsData ? window.getBldgsData() : null;
            if (bData && bData.features) {
                let count = 0;
                for (let f of bData.features) {
                    if (count >= 5) break;
                    const p = f.properties || {};
                    const idStr = String(p.id || "");
                    const parcelStr = String(p.linked_parcel_id || "");
                    const floors = p.derived_floors || "";
                    if (idStr.toLowerCase().includes(query) || parcelStr.toLowerCase().includes(query)) {
                        results.push({
                            title: `Khasra / Structure ${idStr}`,
                            sub: `Cadastral Parcel: ${parcelStr} &bull; ${floors ? floors + " Floors" : "Height Extruded"}`,
                            type: "geojson",
                            id: idStr
                        });
                        count++;
                    }
                }
            }

            if (results.length === 0) {
                searchResults.innerHTML = `<div class="search-item empty">No matching Khasra, Bhu-Aadhaar, or Survey Parcel found</div>`;
            } else {
                searchResults.innerHTML = results.map(r => `
                    <div class="search-item" data-id="${r.id}" data-type="${r.type}">
                        <div class="search-item-icon">
                            <i class="ph ${r.type === 'ulpin' ? 'ph-identification-badge' : 'ph-map-pin'}"></i>
                        </div>
                        <div class="search-item-info">
                            <div class="search-item-title">${r.title}</div>
                            <div class="search-item-sub">${r.sub}</div>
                        </div>
                    </div>
                `).join("");

                searchResults.querySelectorAll(".search-item").forEach(item => {
                    item.addEventListener("click", () => {
                        const id = item.getAttribute("data-id");
                        const type = item.getAttribute("data-type");
                        searchResults.style.display = "none";
                        searchInput.value = "";
                        AudioFX.play("click");

                        const map = window.boundaryMap;
                        if (!map) return;

                        if (type === "geojson" && window.selectBuildingById) {
                            window.selectBuildingById(id);
                        } else {
                            const c = map.getCenter();
                            map.flyTo({ center: [c.lng - 0.0015, c.lat + 0.0032], zoom: 18, pitch: 60, bearing: -20, duration: 1200 });
                            showGovToast("Land Record Located", "Khasra #104/B &bull; Bhu-Aadhaar IN-MP-BHP-P104-B3-FL4-U402", "ph-map-pin");
                        }
                    });
                });
            }

            searchResults.style.display = "block";
        });

        document.addEventListener("click", (e) => {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.style.display = "none";
            }
        });
    }

    // =========================================================================
    // 8. INITIALIZE ON DOM READY
    // =========================================================================
    document.addEventListener("DOMContentLoaded", function () {
        document.addEventListener("pointerdown", () => AudioFX.init(), { once: true });

        // Persona Modal triggers
        const pillBtn = document.getElementById("persona-pill-btn");
        if (pillBtn) pillBtn.addEventListener("click", openGovModal);

        const modalClose = document.getElementById("gov-modal-close");
        if (modalClose) modalClose.addEventListener("click", closeGovModal);

        document.querySelectorAll(".persona-card").forEach(card => {
            card.addEventListener("click", function () {
                const role = this.getAttribute("data-role");
                if (role) {
                    setGovRole(role);
                    closeGovModal();
                }
            });
        });

        // Certificate modal close
        const certClose = document.getElementById("cert-modal-close");
        if (certClose) certClose.addEventListener("click", closeCertificateModal);

        // Citizen actions
        const btnViewCert = document.getElementById("citizen-view-certificate-btn");
        if (btnViewCert) {
            btnViewCert.addEventListener("click", () => {
                openCertificateModal("IN-MP-BHP-P104-B3-FL4-U402", "Khasra #104/B (Ward 42)", 498.2, 4, 1420);
            });
        }

        const btnCopyUlpin = document.getElementById("citizen-copy-ulpin-btn");
        if (btnCopyUlpin) {
            btnCopyUlpin.addEventListener("click", () => {
                navigator.clipboard.writeText("IN-MP-BHP-P104-B3-FL4-U402");
                AudioFX.play("click");
                showGovToast("Bhu-Aadhaar Copied", "IN-MP-BHP-P104-B3-FL4-U402 copied to clipboard", "ph-copy");
            });
        }

        const btnGrievance = document.getElementById("citizen-grievance-btn");
        if (btnGrievance) {
            btnGrievance.addEventListener("click", () => {
                AudioFX.play("click");
                showGovToast("Grievance Petition Lodged", "Petition #GR-2026-9912 submitted to Revenue Sub-Divisional Magistrate (SDM)", "ph-check-circle");
            });
        }

        // Town Planner actions
        const btnToggleFsi = document.getElementById("btn-toggle-fsi");
        if (btnToggleFsi) {
            btnToggleFsi.addEventListener("click", toggleFsiViolationFilter);
        }

        const btnExportZoning = document.getElementById("btn-export-zoning");
        if (btnExportZoning) {
            btnExportZoning.addEventListener("click", () => {
                AudioFX.play("click");
                showGovToast("Zoning Manifest Exported", "Generated Municipal FSI Building Violation Report (CSV)", "ph-download-simple");
            });
        }

        // Admin actions
        const btnExportCsv = document.getElementById("admin-export-csv");
        if (btnExportCsv) {
            btnExportCsv.addEventListener("click", () => {
                AudioFX.play("click");
                showGovToast("Exporting DILRMP Manifest", "Generating verified 3D ULPIN registry manifest for State Land Portal...", "ph-download-simple");
            });
        }

        // Sound toggle
        const toggleSound = document.getElementById("toggle-sound");
        if (toggleSound) {
            toggleSound.addEventListener("click", () => {
                AudioFX.enabled = !AudioFX.enabled;
                toggleSound.classList.toggle("muted", !AudioFX.enabled);
                toggleSound.innerHTML = AudioFX.enabled ? `<i class="ph ph-speaker-high"></i>` : `<i class="ph ph-speaker-slash"></i>`;
                showGovToast(AudioFX.enabled ? "Audio Enabled" : "Audio Muted", "Statutory interface audio feedback toggled", AudioFX.enabled ? "ph-speaker-high" : "ph-speaker-slash");
            });
        }

        // Print certificate
        const btnPrintCert = document.getElementById("cert-print-btn");
        if (btnPrintCert) {
            btnPrintCert.addEventListener("click", () => {
                window.print();
            });
        }

        // Draw Citizen Passbook QR
        const citizenPassbookQr = document.getElementById("citizen-passbook-qr");
        if (citizenPassbookQr) {
            drawBhuAadhaarQR(citizenPassbookQr, "IN-MP-BHP-P104-B3-FL4-U402");
        }

        // Init search
        initGovSearchEngine();

        // Sync with boundaryDataLoaded
        window.addEventListener("boundaryDataLoaded", function () {
            setGovRole(activeGovRole);
        });

        setGovRole(activeGovRole);
    });

})();
