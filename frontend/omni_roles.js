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
    // 5B. OFFICIAL 3D BHU-AADHAAR PVC CARD MODAL (UIDAI PHYSICAL REPLICA)
    // =========================================================================
    function openBhuCardModal(ulpin, khasra, floor, elev, area, owner) {
        const modal = document.getElementById("bhu-card-modal");
        if (!modal) return;

        AudioFX.play("seal");
        const u = ulpin || "IN-MP-BHP-P104-B3-FL4-U402";
        const k = khasra || "खसरा नं. 104/B, वार्ड 42 (Lotus Heights)";
        const fl = floor || "चतुर्थ तल / 4th Floor (+14.5 m Elevation)";
        const el = elev || "498.2 m MSL (Copernicus DEM)";
        const ar = area || "1,420 वर्ग फुट (sq.ft) • FAR 2.50 Sanctioned";
        const ow = owner || "श्रीमती प्रिया शर्मा / Priya Sharma";

        const elUlpin = document.getElementById("pvc-ulpin");
        const elKhasra = document.getElementById("pvc-khasra");
        const elFloor = document.getElementById("pvc-floor");
        const elElev = document.getElementById("pvc-elev");
        const elArea = document.getElementById("pvc-area");
        const elOwner = document.getElementById("pvc-owner-name");

        if (elUlpin) elUlpin.innerText = u;
        if (elKhasra) elKhasra.innerText = k;
        if (elFloor) elFloor.innerText = fl;
        if (elElev) elElev.innerText = el;
        if (elArea) elArea.innerText = ar;
        if (elOwner) elOwner.innerText = ow;

        const qrCanvas = document.getElementById("pvc-qr-canvas");
        if (qrCanvas) {
            drawBhuAadhaarQR(qrCanvas, u);
        }

        modal.style.display = "flex";
        showGovToast("3D भू-आधार कार्ड", "आधिकारिक 3D भू-आधार पीवीसी कार्ड प्रस्तुत किया गया", "ph-identification-card");
    }

    function closeBhuCardModal() {
        const modal = document.getElementById("bhu-card-modal");
        if (modal) {
            modal.style.display = "none";
            AudioFX.play("click");
        }
    }
    window.openBhuCardModal = openBhuCardModal;
    window.closeBhuCardModal = closeBhuCardModal;

    // =========================================================================
    // 5C. BILINGUAL TRANSLATION ENGINE (HINDI DEFAULT / ENGLISH TOGGLE)
    // =========================================================================
    let currentLang = localStorage.getItem("aeronerds_lang") || "hi";

    const I18N = {
        hi: {
            gov_name: "भारत सरकार",
            dept_name: "ग्रामीण विकास मंत्रालय | भूमि संसाधन विभाग (DoLR)",
            brand_title: "भू-आधार 3D",
            sidebar_title: "भू-आधार 3D",
            brand_sub: "भूमि संसाधन विभाग • ग्रामीण विकास मंत्रालय, भारत सरकार",
            skip_link: "मुख्य सामग्री पर जाएं",
            screen_reader: "स्क्रीन रीडर",
            nav_home: "मुख्य पृष्ठ",
            nav_my_bhu: "मेरा भू-आधार कार्ड",
            nav_3d_map: "3D भू-नक्शा",
            nav_floors: "मंजिल विभाजन",
            nav_fsi: "नगर नियोजन FSI",
            nav_rule8: "नियम 8 समीक्षा",
            nav_title: "भू-अधिकार प्रमाण-पत्र",
            nav_grievance: "शिकायत निवारण",
            ticker_label: "नवीनतम सूचना",
            ticker_msg: "डिजिटल भारत भूमि रिकॉर्ड आधुनिकीकरण कार्यक्रम (DILRMP) के अंतर्गत 3D बहुमंजिला भवनों के लिए भू-आधार (ULPIN) जारी किए जा रहे हैं।",
            search_ph: "खसरा नं., 14-अंकीय भू-आधार (ULPIN), वार्ड संख्या खोजें...",
            tqa_soi: "SoI 1मी ड्रोन DEM",
            tqa_dilrmp: "DILRMP निर्यात",
            tqa_pvc: "मेरा भू-आधार कार्ड",
            role_admin_sub: "वैधानिक 3D भू-सीमांकन व भू-आधार अधिनिर्णय पटल",
            role_planner_sub: "ऊर्ध्वाधर FSI / ऊंचाई अनुपालन एवं अतिक्रमण ऑडिट",
            role_citizen_sub: "3D भू-आधार पासबुक एवं डिजिटल स्व-सत्यापन",
            stat_bldgs: "3D संरचनाएं",
            stat_parcels: "खसरा भूखंड",
            elev_title: "भू-स्थानिक ऊंचाई मॉडल",
            elev_strict: "30मी उपग्रह (सख्त)",
            elev_sim: "1मी ड्रोन सर्वेक्षण",
            tab_info: "भू-अभिलेख",
            tab_logs: "पंजीयक लॉग",
            no_sel: "ऊपर किसी भी 3D संरचना का चयन करें या खसरा / भू-आधार खोजें।",
            prop_spatial_link: "भूकर स्थानिक लिंकेज",
            prop_khasra: "खसरा / भूखंड आईडी",
            prop_topology: "सीमा टोपोलॉजी",
            prop_conf: "विश्वसनीयता स्कोर",
            prop_ground: "भू-तल ऊंचाई (DEM)",
            prop_height: "ऊंचाई (मी) / मंजिलें",
            prop_source: "सर्वेक्षण स्रोत",
            prop_ai: "एआई अतिक्रमण स्थिति",
            prop_canopy: "वृक्ष आवरण (NDVI)",
            prop_height_conf: "ऊंचाई विश्वसनीयता",
            prop_vert_prov: "ऊर्ध्वाधर साक्ष्य",
            prop_floor_est: "मंजिल सीमांकन",
            prop_est_conf: "अनुमान विश्वसनीयता",
            prop_view_floors: "मंजिल स्तर देखें (3D निरीक्षण)",
            prop_prop_ulpin: "प्रस्तावित 3D भू-आधार",
            prop_verif: "सत्यापन द्वार",
            prop_gate_title: "पंजीयक वैधानिक अधिनिर्णय द्वार (नियम 8)",
            btn_approve: "स्वीकृत (APPROVE)",
            btn_correct: "संशोधित (CORRECT)",
            btn_reject: "अस्वीकृत (REJECT)",
            btn_unresolved: "अनिर्णीत (UNRESOLVED)",
            planner_title: "नगर निगम जोनिंग एवं FSI ऑडिट",
            planner_desc: "वार्ड 42 नगर विकास प्राधिकरण। स्वीकृत मास्टर प्लान के विरुद्ध बहुमंजिला भवनों का सत्यापन।",
            fsi_sanc: "स्वीकृत FSI",
            fsi_max_h: "अधिकतम ऊंचाई सीमा",
            fsi_perm_fl: "अनुमति प्राप्त मंजिलें",
            fsi_compliance: "जोन अनुपालन",
            btn_scan_fsi: "ऊर्ध्वाधर FSI / ऊंचाई उल्लंघन जांचें",
            btn_export_zoning: "नगर निगम उल्लंघन रिपोर्ट (CSV)",
            citizen_card_title: "भू-आधार डिजिटल संपत्ति अधिकार",
            citizen_verified: "सत्यापित",
            citizen_view_cert: "3D अधिकार प्रमाण-पत्र देखें",
            citizen_copy_ulpin: "भू-आधार कॉपी करें",
            citizen_registry_status: "आधिकारिक भूमि रजिस्ट्री स्थिति",
            citizen_owner: "मुख्य स्वामी",
            citizen_reg_no: "पंजीकरण संख्या",
            citizen_tax: "भू-राजस्व कर",
            citizen_encumb: "भारमुक्ति स्थिति",
            citizen_grievance: "नामांतरण / सर्वेक्षण शिकायत दर्ज करें",
            legend_title: "भूकर संकेत (Legend)",
            legend_parcel: "खसरा भूखंड (कडैस्ट्रल)",
            legend_footprint: "भवन पदचिह्न",
            legend_vert_class: "3D ऊर्ध्वाधर वर्गीकरण",
            legend_contained: "धरातल-व्युत्पन्न 3D (सटीक)",
            legend_structured: "संरचित 3D भूकर",
            legend_2d_only: "केवल 2D पदचिह्न",
            legend_overlap: "सीमा अतिच्छादन",
            legend_conflict: "वैधानिक समीक्षा आवश्यक"
        },
        en: {
            gov_name: "GOVERNMENT OF INDIA",
            dept_name: "Ministry of Rural Development | Department of Land Resources (DoLR)",
            brand_title: "Bhumi Adhaar 3D",
            sidebar_title: "Bhumi Adhaar",
            brand_sub: "Department of Land Resources • Ministry of Rural Development, Govt. of India",
            skip_link: "Skip to Main Content",
            screen_reader: "Screen Reader",
            nav_home: "Home",
            nav_my_bhu: "My Bhu-Aadhaar Card",
            nav_3d_map: "3D Cadastral Map",
            nav_floors: "Floor Slabs",
            nav_fsi: "Town Planning FSI",
            nav_rule8: "Rule 8 Review",
            nav_title: "3D Title Deed",
            nav_grievance: "Grievance",
            ticker_label: "LATEST NOTICE",
            ticker_msg: "3D ULPIN (Bhu-Aadhaar) roll-out active for multi-storey high-rise parcels under Digital India Land Records Modernization Programme (DILRMP).",
            search_ph: "Search Khasra No., 14-digit Bhu-Aadhaar (ULPIN), Ward No...",
            tqa_soi: "SoI 1m Drone DEM",
            tqa_dilrmp: "DILRMP Export",
            tqa_pvc: "My Bhu-Aadhaar Card",
            role_admin_sub: "Statutory 3D Cadastral Delineation & ULPIN Adjudication Desk",
            role_planner_sub: "Vertical FSI / Height Compliance & Encroachment Auditing",
            role_citizen_sub: "3D Bhu-Aadhaar Passbook & Title Self-Verification",
            stat_bldgs: "3D STRUCTURES",
            stat_parcels: "KHASRA PARCELS",
            elev_title: "Cartographic Elevation Model",
            elev_strict: "30m Satellite (Strict)",
            elev_sim: "1m Drone Survey",
            tab_info: "Cadastral Record",
            tab_logs: "Registrar Log",
            no_sel: "Select any 3D structure or search Khasra / Bhu-Aadhaar above.",
            prop_spatial_link: "Cadastral Spatial Linkage",
            prop_khasra: "Khasra / Parcel ID",
            prop_topology: "Boundary Topology",
            prop_conf: "Confidence Score",
            prop_ground: "Ground Elev (DEM)",
            prop_height: "Height (m) / Floors",
            prop_source: "Survey Source",
            prop_ai: "AI Encroachment Status",
            prop_canopy: "Canopy Evidence",
            prop_height_conf: "Height Confidence",
            prop_vert_prov: "Vertical Provenance",
            prop_floor_est: "Floor Delineation",
            prop_est_conf: "Estimation Confidence",
            prop_view_floors: "View Floor Levels (3D Inspection)",
            prop_prop_ulpin: "Proposed 3D Bhu-Aadhaar",
            prop_verif: "Verification Gate",
            prop_gate_title: "REGISTRAR STATUTORY ADJUDICATION GATE (RULE 8)",
            btn_approve: "APPROVE",
            btn_correct: "CORRECT",
            btn_reject: "REJECT",
            btn_unresolved: "UNRESOLVED",
            planner_title: "MUNICIPAL ZONING & FSI AUDIT",
            planner_desc: "Ward 42 Urban Development Authority. Audits vertical floor compliance against sanctioned master plans.",
            fsi_sanc: "SANCTIONED FSI",
            fsi_max_h: "MAX HEIGHT LIMIT",
            fsi_perm_fl: "PERMITTED FLOORS",
            fsi_compliance: "ZONE COMPLIANCE",
            btn_scan_fsi: "Scan Vertical FSI / Height Violations",
            btn_export_zoning: "Export Municipal Violation Report (CSV)",
            citizen_card_title: "BHU-AADHAAR DIGITAL TITLE",
            citizen_verified: "VERIFIED",
            citizen_view_cert: "View 3D Title Certificate",
            citizen_copy_ulpin: "Copy Bhu-Aadhaar",
            citizen_registry_status: "Official Land Registry Status",
            citizen_owner: "Primary Owner",
            citizen_reg_no: "Registration No.",
            citizen_tax: "Land Revenue Tax",
            citizen_encumb: "Encumbrance Status",
            citizen_grievance: "File Mutation / Survey Grievance",
            legend_title: "Cadastral Legend",
            legend_parcel: "Cadastral Parcel (Khasra)",
            legend_footprint: "Building Footprint",
            legend_vert_class: "3D VERTICAL CLASSIFICATION",
            legend_contained: "SURFACE-DERIVED 3D (CONTAINED)",
            legend_structured: "STRUCTURED 3D CADASTRE",
            legend_2d_only: "2D ONLY FOOTPRINT",
            legend_overlap: "BOUNDARY OVERLAP / MAJORITY",
            legend_conflict: "STATUTORY REVIEW REQUIRED"
        }
    };

    function setLanguage(lang) {
        if (!I18N[lang]) lang = "hi";
        currentLang = lang;
        localStorage.setItem("aeronerds_lang", lang);
        const t = I18N[lang];

        // Language Buttons Active state
        const btnHi = document.getElementById("btn-lang-hi");
        const btnEn = document.getElementById("btn-lang-en");
        if (btnHi) btnHi.classList.toggle("active", lang === "hi");
        if (btnEn) btnEn.classList.toggle("active", lang === "en");

        // Top strip
        const brandText = document.querySelector(".uidai-hindi-brand");
        if (brandText) brandText.innerText = t.brand_title;

        const subDept = document.querySelector(".uidai-sub-dept");
        if (subDept) subDept.innerHTML = t.brand_sub;

        // Sidebar Product Title
        const sidebarTitle = document.getElementById("sidebar-app-title") || document.querySelector(".sidebar-header .logo h1");
        if (sidebarTitle) sidebarTitle.innerText = t.sidebar_title || "Bhumi Adhaar";

        // Nav Links
        const mapNav = {
            "nav-home": t.nav_home,
            "nav-my-bhu": t.nav_my_bhu,
            "nav-3d-map": t.nav_3d_map,
            "nav-floors": t.nav_floors,
            "nav-fsi": t.nav_fsi,
            "nav-rule8": t.nav_rule8,
            "nav-title": t.nav_title,
            "nav-grievance": t.nav_grievance
        };
        for (const [id, label] of Object.entries(mapNav)) {
            const el = document.getElementById(id);
            if (el) {
                const icon = el.querySelector("i");
                const iconHtml = icon ? icon.outerHTML : "";
                el.innerHTML = `${iconHtml}<span>${label}</span>`;
            }
        }

        // Ticker
        const tickerBadge = document.querySelector(".ticker-badge");
        if (tickerBadge) tickerBadge.innerHTML = `<i class="ph ph-bell-ringing"></i> ${t.ticker_label}`;

        const tickerMarquee = document.querySelector(".ticker-marquee");
        if (tickerMarquee) tickerMarquee.innerText = t.ticker_msg;

        // Quick Actions
        const tqaSoi = document.getElementById("tqa-soi-elev");
        if (tqaSoi) tqaSoi.innerHTML = `<i class="ph ph-mountains"></i> ${tqa_soi ? t.tqa_soi : ""}`;

        const tqaDilrmp = document.getElementById("tqa-dilrmp");
        if (tqaDilrmp) tqaDilrmp.innerHTML = `<i class="ph ph-file-arrow-down"></i> ${t.tqa_dilrmp}`;

        const tqaPvc = document.getElementById("tqa-pvc-card");
        if (tqaPvc) tqaPvc.innerHTML = `<i class="ph ph-identification-card"></i> ${t.tqa_pvc}`;

        // Search Input
        const searchInput = document.getElementById("omni-search-input");
        if (searchInput) searchInput.setAttribute("placeholder", t.search_ph);

        // Sidebar tabs & stats
        const tabInfo = document.getElementById("tab-info");
        if (tabInfo) tabInfo.innerText = t.tab_info;

        const tabLogs = document.getElementById("tab-logs");
        if (tabLogs) tabLogs.innerText = t.tab_logs;

        const noSelMsg = document.getElementById("no-selection-msg");
        if (noSelMsg) noSelMsg.innerText = t.no_sel;

        const statBldgsLbl = document.querySelector("#stat-buildings + .stat-label");
        if (statBldgsLbl) statBldgsLbl.innerText = t.stat_bldgs;

        const statParcelsLbl = document.querySelector("#stat-parcels + .stat-label");
        if (statParcelsLbl) statParcelsLbl.innerText = t.stat_parcels;

        // Subtitle according to active role
        const sub = document.getElementById("sidebar-role-subtitle");
        if (sub) {
            if (activeGovRole === "admin") sub.innerText = t.role_admin_sub;
            else if (activeGovRole === "planner") sub.innerText = t.role_planner_sub;
            else sub.innerText = t.role_citizen_sub;
        }

        AudioFX.play("click");
        showGovToast(lang === "hi" ? "भाषा बदली गई" : "Language Changed", lang === "hi" ? "हिन्दी भाषा सक्रिय की गई है।" : "English language activated.", "ph-translate");
    }
    window.setLanguage = setLanguage;

    // =========================================================================
    // 5D. ACCESSIBILITY FONT RESIZER ENGINE
    // =========================================================================
    let currentFontScale = 100;
    function setFontScale(scale) {
        currentFontScale = Math.max(85, Math.min(125, scale));
        document.documentElement.style.fontSize = `${(currentFontScale / 100) * 14}px`;
        AudioFX.play("click");
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

        // PVC Card modal listeners
        const pvcCloseBtn = document.getElementById("pvc-close-btn");
        if (pvcCloseBtn) pvcCloseBtn.addEventListener("click", closeBhuCardModal);

        const bhuModalBackdrop = document.getElementById("bhu-card-modal");
        if (bhuModalBackdrop) {
            bhuModalBackdrop.addEventListener("click", (e) => {
                if (e.target === bhuModalBackdrop) closeBhuCardModal();
            });
        }

        const pvcCopyBtn = document.getElementById("pvc-copy-btn");
        if (pvcCopyBtn) {
            pvcCopyBtn.addEventListener("click", () => {
                const code = document.getElementById("pvc-ulpin")?.innerText || "IN-MP-BHP-P104-B3-FL4-U402";
                navigator.clipboard.writeText(code);
                AudioFX.play("click");
                showGovToast("3D भू-आधार संख्या कॉपी हुई", `${code} क्लिपबोर्ड पर कॉपी किया गया`, "ph-copy");
            });
        }

        const pvcPrintBtn = document.getElementById("pvc-print-btn");
        if (pvcPrintBtn) {
            pvcPrintBtn.addEventListener("click", () => {
                AudioFX.play("click");
                window.print();
            });
        }

        // Language buttons
        const btnLangHi = document.getElementById("btn-lang-hi");
        if (btnLangHi) btnLangHi.addEventListener("click", () => setLanguage("hi"));

        const btnLangEn = document.getElementById("btn-lang-en");
        if (btnLangEn) btnLangEn.addEventListener("click", () => setLanguage("en"));

        // Font resizer
        const btnFontDec = document.getElementById("btn-font-dec");
        if (btnFontDec) btnFontDec.addEventListener("click", () => setFontScale(currentFontScale - 5));

        const btnFontReset = document.getElementById("btn-font-reset");
        if (btnFontReset) btnFontReset.addEventListener("click", () => setFontScale(100));

        const btnFontInc = document.getElementById("btn-font-inc");
        if (btnFontInc) btnFontInc.addEventListener("click", () => setFontScale(currentFontScale + 5));

        // UIDAI Main Navigation Bar Handlers
        const navHome = document.getElementById("nav-home");
        if (navHome) {
            navHome.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".uidai-nav-link").forEach(l => l.classList.remove("active"));
                navHome.classList.add("active");
                const map = window.boundaryMap;
                if (map) {
                    map.flyTo({ center: [77.4126, 23.2599], zoom: 16.5, pitch: 45, bearing: -15, duration: 1500 });
                }
                showGovToast("मुख्य पृष्ठ / Home", "कडैस्ट्रल दृश्य रीसेट किया गया", "ph-house");
            });
        }

        const navMyBhu = document.getElementById("nav-my-bhu");
        if (navMyBhu) {
            navMyBhu.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".uidai-nav-link").forEach(l => l.classList.remove("active"));
                navMyBhu.classList.add("active");
                openBhuCardModal();
            });
        }

        const nav3dMap = document.getElementById("nav-3d-map");
        if (nav3dMap) {
            nav3dMap.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".uidai-nav-link").forEach(l => l.classList.remove("active"));
                nav3dMap.classList.add("active");
                const btn3d = document.getElementById("btn-3d");
                if (btn3d) btn3d.click();
            });
        }

        const navFloors = document.getElementById("nav-floors");
        if (navFloors) {
            navFloors.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".uidai-nav-link").forEach(l => l.classList.remove("active"));
                navFloors.classList.add("active");
                const toggleFloors = document.getElementById("toggle-floors");
                if (toggleFloors) toggleFloors.click();
            });
        }

        const navFsi = document.getElementById("nav-fsi");
        if (navFsi) {
            navFsi.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".uidai-nav-link").forEach(l => l.classList.remove("active"));
                navFsi.classList.add("active");
                setGovRole("planner");
                toggleFsiViolationFilter();
            });
        }

        const navRule8 = document.getElementById("nav-rule8");
        if (navRule8) {
            navRule8.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".uidai-nav-link").forEach(l => l.classList.remove("active"));
                navRule8.classList.add("active");
                setGovRole("admin");
            });
        }

        const navTitle = document.getElementById("nav-title");
        if (navTitle) {
            navTitle.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".uidai-nav-link").forEach(l => l.classList.remove("active"));
                navTitle.classList.add("active");
                openCertificateModal("IN-MP-BHP-P104-B3-FL4-U402", "Khasra #104/B (Lotus Heights)", 498.2, 4, 1420);
            });
        }

        const navGrievance = document.getElementById("nav-grievance");
        if (navGrievance) {
            navGrievance.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".uidai-nav-link").forEach(l => l.classList.remove("active"));
                navGrievance.classList.add("active");
                setGovRole("citizen");
                const btnGrievance = document.getElementById("citizen-grievance-btn");
                if (btnGrievance) btnGrievance.click();
            });
        }

        // Ticker Quick Action triggers
        const tqaSoi = document.getElementById("tqa-soi-elev");
        if (tqaSoi) {
            tqaSoi.addEventListener("click", () => {
                const resToggle = document.getElementById("res-toggle");
                if (resToggle) {
                    resToggle.checked = !resToggle.checked;
                    resToggle.dispatchEvent(new Event("change"));
                }
            });
        }

        const tqaDilrmp = document.getElementById("tqa-dilrmp");
        if (tqaDilrmp) {
            tqaDilrmp.addEventListener("click", () => {
                const btnExportCsv = document.getElementById("admin-export-csv");
                if (btnExportCsv) btnExportCsv.click();
            });
        }

        const tqaPvc = document.getElementById("tqa-pvc-card");
        if (tqaPvc) {
            tqaPvc.addEventListener("click", () => {
                openBhuCardModal();
            });
        }

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

        // Set initial language (Hindi default)
        setLanguage(currentLang);

        // Sync with boundaryDataLoaded
        window.addEventListener("boundaryDataLoaded", function () {
            setGovRole(activeGovRole);
        });

        setGovRole(activeGovRole);
    });

})();
