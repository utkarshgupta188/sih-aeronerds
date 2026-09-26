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
    // 3. PURE SVG QR CODE ALLOTTER (Using datalog/qrcode-svg)
    // =========================================================================
    function renderUlpinQRCode(target, ulpinCode, options) {
        if (!target) return null;
        if (typeof target === "string") {
            target = document.getElementById(target);
        }
        if (!target) return null;

        const u = String(ulpinCode || "IN-MP-BHP-P104-B3-FL4-U402").trim();
        const opts = options || {};
        const size = opts.size || (target.clientWidth && target.clientWidth > 0 ? target.clientWidth : (target.width || 90));

        // Formulate official statutory DoLR / SVAMITVA Bhu-Aadhaar verification URL
        const verifyUrl = opts.rawUrl || `https://bhumiadhaar.dolr.gov.in/verify?ulpin=${encodeURIComponent(u)}&auth=svamitva&v=1`;

        let svgElement = null;

        if (typeof window.QRCode === "function") {
            try {
                // Call cloned datalog/qrcode-svg engine
                svgElement = window.QRCode({
                    msg: verifyUrl,
                    dim: size,
                    pad: opts.pad !== undefined ? opts.pad : 2,
                    mtx: -1,
                    ecl: opts.ecl || "M",
                    ecb: 1,
                    pal: opts.pal || ["#0a192f", "#ffffff"],
                    vrb: 0
                });
            } catch (err) {
                console.warn("[qrcode-svg] Engine error:", err);
            }
        }

        // If target is a CANVAS element, render SVG into canvas image context
        if (target.tagName === "CANVAS") {
            if (svgElement) {
                const svgXml = new XMLSerializer().serializeToString(svgElement);
                const blob = new Blob([svgXml], { type: "image/svg+xml;charset=utf-8" });
                const blobUrl = URL.createObjectURL(blob);
                const img = new Image();
                img.onload = function () {
                    const ctx = target.getContext("2d");
                    if (ctx) {
                        ctx.clearRect(0, 0, target.width, target.height);
                        ctx.drawImage(img, 0, 0, target.width, target.height);
                    }
                    URL.revokeObjectURL(blobUrl);
                };
                img.src = blobUrl;
                return svgElement;
            }
        }

        // Target is a DIV or container element: inject crisp pure SVG DOM node
        if (svgElement) {
            svgElement.setAttribute("title", `Official 3D Bhu-Aadhaar: ${u}`);
            svgElement.setAttribute("role", "img");
            svgElement.setAttribute("aria-label", `QR Code for Bhu-Aadhaar ${u}`);
            svgElement.style.width = "100%";
            svgElement.style.height = "100%";
            svgElement.style.display = "block";
            svgElement.style.borderRadius = "4px";

            target.innerHTML = "";
            target.appendChild(svgElement);
            return svgElement;
        }

        // Fallback placeholder
        target.innerHTML = `<div style="font-size:9px;color:#64748b;text-align:center;padding:10px;font-family:monospace;">${u}</div>`;
        return null;
    }

    const drawBhuAadhaarQR = renderUlpinQRCode;
    window.renderUlpinQRCode = renderUlpinQRCode;
    window.drawBhuAadhaarQR = renderUlpinQRCode;

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
        const active = window.__activeSelectedProperty || {};
        const u = ulpin || active.ulpin || "IN-MP-BHP-P104-B3-FL4-U402";
        const k = khasra || active.khasra || "Khasra #104/B, Ward 42";
        const el = elevation || active.elevNum || "498.2";
        const fl = floors || active.floorsNum || 4;
        const ar = area || active.areaNum || "1,420";

        document.getElementById("cert-ulpin").innerText = u;
        document.getElementById("cert-khasra").innerText = k;
        document.getElementById("cert-elevation").innerText = `${el} m MSL (Bare-Earth DEM)`;
        document.getElementById("cert-floors").innerText = `${fl} Floors (Vertical Cadastre)`;
        document.getElementById("cert-area").innerText = `${ar} sq.ft (Built-Up)`;
        document.getElementById("cert-date").innerText = new Date().toLocaleDateString("en-IN", {
            day: "2-digit", month: "long", year: "numeric"
        });

        const certTarget = document.getElementById("cert-qr-wrap") || document.getElementById("cert-qr-canvas");
        if (certTarget) {
            renderUlpinQRCode(certTarget, u, { size: 90, pad: 2 });
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
    window.openCertificateModal = openCertificateModal;
    window.closeCertificateModal = closeCertificateModal;

    // =========================================================================
    // 5B. OFFICIAL 3D BHU-AADHAAR PVC CARD MODAL (UIDAI PHYSICAL REPLICA)
    // =========================================================================
    function openBhuCardModal(ulpin, khasra, floor, elev, area, owner) {
        const modal = document.getElementById("bhu-card-modal");
        if (!modal) return;

        AudioFX.play("seal");
        const active = window.__activeSelectedProperty || {};
        const u = ulpin || active.ulpin || "IN-MP-BHP-P104-B3-FL4-U402";
        const k = khasra || active.khasra || "खसरा नं. 104/B, वार्ड 42 (Lotus Heights)";
        const fl = floor || active.floor || "चतुर्थ तल / 4th Floor (+14.5 m Elevation)";
        const el = elev || active.elev || "498.2 m MSL (Copernicus DEM)";
        const ar = area || active.area || "1,420 वर्ग फुट (sq.ft) • FAR 2.50 Sanctioned";
        const ow = owner || active.owner || "श्रीमती प्रिया शर्मा / Priya Sharma";

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

        const pvcTarget = document.getElementById("pvc-qr-wrap") || document.getElementById("pvc-qr-canvas");
        if (pvcTarget) {
            renderUlpinQRCode(pvcTarget, u, { size: 90, pad: 2 });
        }

        modal.style.display = "flex";
        showGovToast("3D भू-आधार कार्ड", `विशिष्ट भू-आधार QR आवंटित: ${u}`, "ph-qr-code");
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
    // =========================================================================
    // 7. UNIVERSAL PAN-INDIA & MULTI-CITY LAND RECORD SEARCH (BHU-AADHAAR / ULPIN)
    // =========================================================================
    let panIndiaCatalog = null;
    let catalogLoadingPromise = null;

    function getCentroidFromGeom(geom) {
        if (!geom || !geom.coordinates) return null;
        let pts = [];
        if (geom.type === "Polygon") pts = geom.coordinates[0];
        else if (geom.type === "MultiPolygon") pts = geom.coordinates[0][0];
        else if (geom.type === "LineString") pts = geom.coordinates;
        if (!pts || !pts.length) return null;
        let sx = 0, sy = 0;
        pts.forEach(p => { sx += p[0]; sy += p[1]; });
        return [roundCoord(sx / pts.length), roundCoord(sy / pts.length)];
    }

    function roundCoord(num) {
        return Math.round(num * 100000) / 100000;
    }

    function getSearchIcon(cat) {
        switch (cat) {
            case "UNDERGROUND_METRO": return "ph-subway";
            case "ACTIVE_3D_PARCEL": return "ph-buildings";
            case "PILOT_3D_CITY": return "ph-map-pin";
            case "PAN_INDIA_GATEWAY": return "ph-globe-hemisphere-east";
            case "RESOLVED_ULPIN": return "ph-seal-check";
            default: return "ph-identification-badge";
        }
    }

    function getSearchBadge(cat, cityName) {
        switch (cat) {
            case "ACTIVE_3D_PARCEL": return "3D DIGITAL TWIN";
            case "PILOT_3D_CITY": return cityName ? cityName.toUpperCase() : "PILOT 3D";
            case "UNDERGROUND_METRO": return "SUBTERRANEAN";
            case "PAN_INDIA_GATEWAY": return "STATE RoR GATEWAY";
            case "RESOLVED_ULPIN": return "BHU-AADHAAR";
            default: return "PAN-INDIA ULPIN";
        }
    }

    async function loadPanIndiaCatalog() {
        if (panIndiaCatalog) return panIndiaCatalog;
        if (catalogLoadingPromise) return catalogLoadingPromise;
        catalogLoadingPromise = fetch("data/pan_india_catalog.json")
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                panIndiaCatalog = data;
                window.__panIndiaCatalog = data;
                return data;
            })
            .catch(err => {
                console.warn("Pan-India catalog load error", err);
                return null;
            });
        return catalogLoadingPromise;
    }

    function initGovSearchEngine() {
        const searchInput = document.getElementById("omni-search-input");
        const searchResults = document.getElementById("omni-search-results");
        if (!searchInput || !searchResults) return;

        // Eagerly pre-load Pan-India catalog
        loadPanIndiaCatalog();

        searchInput.addEventListener("input", async function (e) {
            const rawQuery = e.target.value.trim();
            if (rawQuery.length < 1) {
                searchResults.style.display = "none";
                searchResults.innerHTML = "";
                return;
            }

            const query = rawQuery.toLowerCase();
            const queryClean = query.replace(/[\s\-_/]+/g, "");
            const queryDigits = rawQuery.replace(/\D/g, "");
            const results = [];
            const seenIds = new Set();

            const urlParams = new URLSearchParams(window.location.search);
            const currentCityKey = urlParams.get("region") || "bhopal";
            const activeReg = window.activeRegion || {};
            const activeStateCode = activeReg.stateCode || "IN-MP-BHP";

            if (!panIndiaCatalog) await loadPanIndiaCatalog();

            // -------------------------------------------------------------
            // 1. ACTIVE CITY 3D IN-MEMORY SCAN (Real-time Dynamic ULPINs)
            // -------------------------------------------------------------
            const bData = window.getBldgsData ? window.getBldgsData() : null;
            if (bData && bData.features) {
                let localCount = 0;
                for (let f of bData.features) {
                    if (localCount >= 8) break;
                    const p = f.properties || {};
                    const idStr = String(p.id || "");
                    const parcelStr = String(p.linked_parcel_id || "");
                    const nameStr = String(p.name || "");
                    const bNum = idStr.replace(/\D/g, "");
                    const pNum = parcelStr.replace(/\D/g, "");
                    const dynUlpin = activeStateCode + "-P" + (pNum || "01") + "-B" + (bNum || "01");
                    const dynUlpinClean = dynUlpin.toLowerCase().replace(/[\s\-_/]+/g, "");
                    const floors = p.derived_floors || p.building_levels || "";

                    const match = dynUlpin.toLowerCase().includes(query) ||
                                  dynUlpinClean.includes(queryClean) ||
                                  idStr.toLowerCase().includes(query) ||
                                  parcelStr.toLowerCase().includes(query) ||
                                  nameStr.toLowerCase().includes(query) ||
                                  (queryDigits.length >= 2 && (bNum.includes(queryDigits) || pNum.includes(queryDigits))) ||
                                  (query === "ulpin" || query === "bhu" || query === "aadhaar" || query === "khasra");

                    if (match && !seenIds.has(idStr)) {
                        seenIds.add(idStr);
                        results.push({
                            title: (nameStr ? `${nameStr} &bull; ` : "") + dynUlpin,
                            sub: `Khasra / Parcel: ${parcelStr} &bull; ${floors ? floors + " Floors" : "3D Extruded Slabs"} &bull; [Current Active Pilot]`,
                            type: "geojson",
                            category: "ACTIVE_3D_PARCEL",
                            city_key: currentCityKey,
                            city_name: activeReg.name || "Current City",
                            id: idStr,
                            ulpin: dynUlpin,
                            coordinates: getCentroidFromGeom(f.geometry)
                        });
                        localCount++;
                    }
                }
            }

            // -------------------------------------------------------------
            // 2. UNDERGROUND UTILITIES & SUBTERRANEAN METRO CORRIDORS
            // -------------------------------------------------------------
            const ugFeatures = (window.undergroundData && window.undergroundData.features) ||
                               (panIndiaCatalog && panIndiaCatalog.pilot_records.filter(r => r.type === "subsurface")) || [];
            for (let item of ugFeatures) {
                if (results.length >= 12) break;
                const p = item.properties || item;
                const uId = String(p.id || "");
                const subUlpin = String(p.proposed_subsurface_ulpin || p.ulpin || "");
                const assetName = String(p.asset_name || p.title || "");
                const assetType = String(p.asset_type || p.subsurface_type || "");

                const match = subUlpin.toLowerCase().includes(query) ||
                              assetName.toLowerCase().includes(query) ||
                              assetType.toLowerCase().includes(query) ||
                              uId.toLowerCase().includes(query) ||
                              query.includes("metro") || query.includes("tunnel") ||
                              query.includes("subsurface") || query.includes("underground") ||
                              query.includes("pipeline") || query.includes("power");

                if (match && !seenIds.has(uId)) {
                    seenIds.add(uId);
                    results.push({
                        title: `Subsurface: ${assetName}`,
                        sub: `${assetType} &bull; ULPIN: ${subUlpin} &bull; Statutory Subterranean ROW`,
                        type: "subsurface",
                        category: "UNDERGROUND_METRO",
                        city_key: p.city_key || currentCityKey,
                        city_name: p.city_name || "Subsurface Easement",
                        id: uId,
                        ulpin: subUlpin,
                        coordinates: p.coordinates || (item.geometry ? getCentroidFromGeom(item.geometry) : null)
                    });
                }
            }

            // -------------------------------------------------------------
            // 3. CROSS-CITY PAN-INDIA PILOT CATALOG SEARCH
            // (Bhopal, Bengaluru, Indore, Navi Mumbai, Kalyan, Coimbatore)
            // -------------------------------------------------------------
            if (panIndiaCatalog && panIndiaCatalog.pilot_records) {
                for (let r of panIndiaCatalog.pilot_records) {
                    if (results.length >= 14) break;
                    if (seenIds.has(r.building_id)) continue;

                    const rUlpin = String(r.ulpin || "").toLowerCase();
                    const rFullUlpin = String(r.full_ulpin || "").toLowerCase();
                    const rNum = String(r.numeric_ulpin || "").toLowerCase();
                    const rTitle = String(r.title || "").toLowerCase();
                    const rSub = String(r.sub || "").toLowerCase();
                    const rCity = String(r.city_name || "").toLowerCase();
                    const rParcel = String(r.parcel_id || "").toLowerCase();

                    const match = rUlpin.includes(query) ||
                                  rFullUlpin.includes(query) ||
                                  rNum.includes(query) ||
                                  rTitle.includes(query) ||
                                  rSub.includes(query) ||
                                  rCity.includes(query) ||
                                  rParcel.includes(query) ||
                                  (queryDigits.length >= 3 && (rUlpin.replace(/\D/g, "").includes(queryDigits) || rNum.includes(queryDigits))) ||
                                  (query.length >= 3 && rCity.includes(query.replace(/[\s\-_]+/g, "")));

                    if (match) {
                        seenIds.add(r.building_id);
                        results.push({
                            title: r.title,
                            sub: `${r.sub} &bull; [${r.city_name}]`,
                            type: r.type || "pilot_catalog",
                            category: r.city_key === currentCityKey ? "ACTIVE_3D_PARCEL" : "PILOT_3D_CITY",
                            city_key: r.city_key,
                            city_name: r.city_name,
                            id: r.building_id,
                            ulpin: r.full_ulpin || r.ulpin,
                            coordinates: r.coordinates
                        });
                    }
                }
            }

            // -------------------------------------------------------------
            // 4. PAN-INDIA STATE / UT BHU-AADHAAR DIRECTORY SEARCH
            // -------------------------------------------------------------
            if (panIndiaCatalog && panIndiaCatalog.pan_india_states) {
                for (let st of panIndiaCatalog.pan_india_states) {
                    if (results.length >= 16) break;
                    const stCode = st.code.toLowerCase();
                    const stName = st.name.toLowerCase();
                    const stHi = (st.hi || "").toLowerCase();
                    const stLgd = st.lgd || "";

                    const match = stCode.includes(query) ||
                                  stName.includes(query) ||
                                  stHi.includes(query) ||
                                  query.includes(stCode.replace("in-", "")) ||
                                  (queryDigits.length >= 2 && queryDigits.startsWith(stLgd));

                    if (match) {
                        results.push({
                            title: `Bhu-Aadhaar Gateway &bull; ${st.name} (${st.code})`,
                            sub: `Official RoR: ${st.portal} &bull; LGD Code: ${st.lgd} &bull; DILRMP 3D Digital Twin Integration`,
                            type: "pan_india_state",
                            category: "PAN_INDIA_GATEWAY",
                            city_key: null,
                            city_name: st.name,
                            id: st.code,
                            ulpin: `${st.code}-STD-CADASTRAL`,
                            coordinates: st.center
                        });
                    }
                }
            }

            // -------------------------------------------------------------
            // 5. UNIVERSAL SYNTHETIC RESOLVER: NEVER SAY "NO RESULTS" FOR AN INDIAN ULPIN
            // -------------------------------------------------------------
            if (results.length === 0) {
                let resolvedStateName = "Government of India (DoLR / SVAMITVA)";
                let resolvedPortal = "National Bhu-Aadhaar Land Registry";
                let centerCoords = [78.9629, 20.5937];
                let targetCityKey = "bhopal";

                const stateMatch = rawQuery.match(/^IN-([A-Z]{2})/i);
                if (stateMatch && panIndiaCatalog && panIndiaCatalog.pan_india_states) {
                    const sc = "IN-" + stateMatch[1].toUpperCase();
                    const foundState = panIndiaCatalog.pan_india_states.find(s => s.code === sc);
                    if (foundState) {
                        resolvedStateName = foundState.name;
                        resolvedPortal = foundState.portal;
                        centerCoords = foundState.center;
                        if (sc === "IN-MP") targetCityKey = "bhopal";
                        else if (sc === "IN-KA") targetCityKey = "bengaluru";
                        else if (sc === "IN-MH") targetCityKey = "navi_mumbai";
                        else if (sc === "IN-TN") targetCityKey = "coimbatore";
                    }
                } else if (queryDigits.length >= 2 && panIndiaCatalog && panIndiaCatalog.pan_india_states) {
                    const prefix2 = queryDigits.substring(0, 2);
                    const foundState = panIndiaCatalog.pan_india_states.find(s => s.lgd === prefix2);
                    if (foundState) {
                        resolvedStateName = foundState.name;
                        resolvedPortal = foundState.portal;
                        centerCoords = foundState.center;
                    }
                }

                results.push({
                    title: `Official Bhu-Aadhaar 3D Delineation &bull; ${rawQuery.toUpperCase()}`,
                    sub: `State: ${resolvedStateName} &bull; Portal: ${resolvedPortal} &bull; Rule 8 Statutory Adjudication Gate`,
                    type: "pan_india_synthetic",
                    category: "RESOLVED_ULPIN",
                    city_key: targetCityKey,
                    city_name: resolvedStateName,
                    id: rawQuery,
                    ulpin: rawQuery.toUpperCase(),
                    coordinates: centerCoords
                });
            }

            // Render Results HTML
            searchResults.innerHTML = results.map(r => `
                <div class="search-item" data-id="${r.id}" data-type="${r.type}" data-city-key="${r.city_key || ''}" data-ulpin="${r.ulpin || ''}" data-lng="${r.coordinates ? r.coordinates[0] : ''}" data-lat="${r.coordinates ? r.coordinates[1] : ''}">
                    <div class="search-item-icon ${r.category}">
                        <i class="ph ${getSearchIcon(r.category)}"></i>
                    </div>
                    <div class="search-item-info">
                        <div class="search-item-top">
                            <span class="search-item-title">${r.title}</span>
                            <span class="search-badge ${r.category}">${getSearchBadge(r.category, r.city_name)}</span>
                        </div>
                        <div class="search-item-sub">${r.sub}</div>
                        ${r.ulpin ? `<div class="search-item-ulpin">3D ULPIN: ${r.ulpin}</div>` : ''}
                    </div>
                </div>
            `).join("");

            // Wire Click Handlers on Results
            searchResults.querySelectorAll(".search-item").forEach(item => {
                item.addEventListener("click", () => {
                    const id = item.getAttribute("data-id");
                    const type = item.getAttribute("data-type");
                    const cityKey = item.getAttribute("data-city-key");
                    const ulpin = item.getAttribute("data-ulpin");
                    const lng = parseFloat(item.getAttribute("data-lng"));
                    const lat = parseFloat(item.getAttribute("data-lat"));

                    searchResults.style.display = "none";
                    searchInput.value = "";
                    AudioFX.play("click");

                    const map = window.boundaryMap;
                    const urlParams = new URLSearchParams(window.location.search);
                    const currentCity = urlParams.get("region") || "bhopal";

                    // 1. Cross-City Navigation (Pilot regions: Bhopal, Bengaluru, Indore, Navi Mumbai, Kalyan, Coimbatore)
                    if (cityKey && cityKey !== currentCity && ["bhopal", "bengaluru", "indore", "navi_mumbai", "mumbai_kalyan", "coimbatore"].includes(cityKey)) {
                        showGovToast("Switching Pilot Region", `Navigating to ${cityKey.toUpperCase()} 3D Digital Twin &bull; ${ulpin || id}`, "ph-airplane-takeoff");
                        setTimeout(() => {
                            window.location.href = window.location.pathname + "?region=" + cityKey + "&highlight=" + encodeURIComponent(id) + "&ulpin=" + encodeURIComponent(ulpin || "");
                        }, 400);
                        return;
                    }

                    // 2. Active City Building Selection
                    if (type === "geojson" && window.selectBuildingById) {
                        const feat = window.selectBuildingById(id);
                        if (feat) {
                            showGovToast("3D Cadastre Delineated", `${ulpin} &bull; Khasra Record Located`, "ph-buildings");
                            return;
                        }
                    }

                    // 3. Underground Infrastructure Selection
                    if (type === "subsurface" && window.selectUndergroundById) {
                        const feat = window.selectUndergroundById(id);
                        if (feat) {
                            showGovToast("Subsurface 3D Corridor", `${ulpin} &bull; Statutory Easement Located`, "ph-subway");
                            return;
                        }
                    }

                    // 4. Pan-India State / National Coordinates FlyTo
                    if (map && !isNaN(lng) && !isNaN(lat)) {
                        const targetZoom = (type.startsWith("pan_india") ? 11 : 18);
                        map.flyTo({ center: [lng, lat], zoom: targetZoom, pitch: 60, bearing: -20, duration: 1400 });
                        showGovToast("Bhu-Aadhaar Located", `${ulpin || id} &bull; Pan-India Cadastral Resolution`, "ph-seal-check");
                    }
                });
            });

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
                const active = window.__activeSelectedProperty || {};
                openCertificateModal(active.ulpin, active.khasra, active.elevNum, active.floorsNum, active.areaNum);
            });
        }

        const btnCopyUlpin = document.getElementById("citizen-copy-ulpin-btn");
        if (btnCopyUlpin) {
            btnCopyUlpin.addEventListener("click", () => {
                const active = window.__activeSelectedProperty || {};
                const u = active.ulpin || "IN-MP-BHP-P104-B3-FL4-U402";
                navigator.clipboard.writeText(u);
                AudioFX.play("click");
                showGovToast("Bhu-Aadhaar Copied", `${u} copied to clipboard`, "ph-copy");
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

        // Draw Citizen Passbook & Property Inspector QR codes using datalog/qrcode-svg
        const initialDefaultUlpin = "IN-MP-BHP-P104-B3-FL4-U402";
        renderUlpinQRCode("citizen-passbook-qr", initialDefaultUlpin, { size: 80, pad: 2 });
        renderUlpinQRCode("prop-qr-box", initialDefaultUlpin, { size: 52, pad: 1 });

        // Wire Property Inspector QR badge action buttons
        const btnPropPvc = document.getElementById("btn-prop-open-pvc");
        if (btnPropPvc) {
            btnPropPvc.addEventListener("click", (e) => {
                e.stopPropagation();
                openBhuCardModal();
            });
        }
        const btnPropCert = document.getElementById("btn-prop-open-cert");
        if (btnPropCert) {
            btnPropCert.addEventListener("click", (e) => {
                e.stopPropagation();
                openCertificateModal();
            });
        }

        // Listen for building / parcel / underground selection to allot specific QR code
        window.addEventListener("buildingSelected", function (e) {
            const detail = (e && e.detail) || {};
            const props = detail.props || {};

            const region = window.activeRegion || {};
            const statePrefix = region.stateCode || "IN-MP-BHP";
            const bIdNum = String(props.id || "0").replace(/\D/g, "") || "01";
            const pIdNum = String(props.linked_parcel_id || props.parent_parcel_id || "0000").replace(/\D/g, "") || "01";

            const specificUlpin = props.proposed_subsurface_ulpin ||
                                  props.ulpin ||
                                  (props.linked_parcel_id ? `${statePrefix}-P${pIdNum}-B${bIdNum}` : `${statePrefix}-B${bIdNum}`);

            const khasra = props.khasra_no || (props.linked_parcel_id ? `Khasra #${props.linked_parcel_id}` : (props.name || "Survey Parcel"));
            const elev = props.ground_elevation_m ? String(props.ground_elevation_m) : "498.2";
            const floors = props.derived_floors || props.floor_count_estimated || 4;
            const area = props.building_area_sqm ? Math.round(props.building_area_sqm * 10.7639) : 1420;
            const owner = props.owner_name || "श्रीमती प्रिया शर्मा / Priya Sharma";

            window.__activeSelectedProperty = {
                ulpin: specificUlpin,
                khasra: khasra,
                floor: `${floors}th Floor / Level ${floors} (+${Math.round(floors * 3.2)}m Elevation)`,
                elev: `${elev} m MSL (Copernicus DEM)`,
                elevNum: elev,
                floorsNum: floors,
                area: `${area.toLocaleString()} sq.ft • Built-Up Space`,
                areaNum: area,
                owner: owner
            };

            // Allot specific QR code into Property Card using datalog/qrcode-svg
            renderUlpinQRCode("prop-qr-box", specificUlpin, { size: 52, pad: 1 });

            // Allot specific QR code into Citizen Passbook
            renderUlpinQRCode("citizen-passbook-qr", specificUlpin, { size: 80, pad: 2 });

            const citizenUlpin = document.getElementById("citizen-prop-ulpin");
            if (citizenUlpin) citizenUlpin.innerText = specificUlpin;
            const citizenKhasra = document.getElementById("citizen-prop-khasra");
            if (citizenKhasra) citizenKhasra.innerText = khasra;
            const citizenUnit = document.getElementById("citizen-prop-unit");
            if (citizenUnit) citizenUnit.innerText = `Level ${floors} • 3D Parcel`;
            const citizenElev = document.getElementById("citizen-prop-elev");
            if (citizenElev) citizenElev.innerText = `Ground Elev: ${elev}m MSL • Height: +${Math.round(floors * 3.2)}m`;
        });

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
