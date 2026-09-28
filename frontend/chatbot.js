/**
 * Bhumi Adhaar AI Assistant (Bhu-Mitra)
 * Self-contained intelligent offline assistant for the 3D Cadastre Digital Twin.
 * Guides users, explains technical architecture, and triggers interactive actions on the map.
 */

(function () {
    "use strict";

    // Knowledge Base with rich intents, keywords, answers, and actionable live triggers
    const KNOWLEDGE_BASE = [
        {
            id: "greeting",
            patterns: ["hi", "hello", "hey", "namaste", "greetings", "help", "who are you", "what can you do", "intro"],
            reply: "Hello! I am <b>Bhu-Mitra</b>, your interactive guide for the <b>Bhumi Adhaar 3D Cadastre & Digital Twin</b> platform. I can help you explore 3D property boundaries, floor level estimations, FSI compliance, Rule 8 adjudication, and navigate the portal features.",
            suggestions: ["What is 3D ULPIN?", "Show Floor Slabs", "Check FSI Violations", "Rule 8 Review"]
        },
        {
            id: "project_overview",
            patterns: ["project", "what is this", "about", "overview", "sih", "aeronerds", "objective", "purpose", "why 3d"],
            reply: "This project solves <b>Smart India Hackathon problem SIH26011</b> for the Department of Land Resources (DoLR) and SVAMITVA.<br><br>While traditional land records are 2D flat parcels (X, Y), high-rise apartments and multi-tier developments require <b>3D vertical spatial rights (Z-axis)</b>. Our system delineates 3D vertical parcels, detects floor levels, computes bare-earth DEM ground datums, and validates municipal FSI compliance.",
            suggestions: ["How does 3D ULPIN work?", "Show 3D Cadastral Map", "Explore Pilot Cities"]
        },
        {
            id: "ulpin",
            patterns: ["ulpin", "card", "pvc", "bhu card", "id", "14 digit", "unique parcel", "qr code", "passbook"],
            reply: "<b>3D ULPIN (Unique Land Parcel Identification Number)</b> extends the 14-digit national parcel ID vertically into individual floor-level property units.<br><br>Example format: <code>IN-MP-BHP-P104-B3-FL4-U402</code> denoting Country, State, District, Parcel, Building, Floor (+14.5m), and Unit.",
            action: { label: "Open 3D ULPIN Card", trigger: "open_pvc_card" },
            suggestions: ["Title Deed Certificate", "Floor Slabs", "Search Khasra"]
        },
        {
            id: "floor_slabs",
            patterns: ["floor", "slab", "slabs", "levels", "extrusion", "height", "3d model", "building model", "estimation"],
            reply: "Our automated <b>Floor Detection Engine</b> classifies building height into vertical floor slabs using DSM-DEM surface evidence and machine learning. Each floor slab is modeled in 3D Three.js with elevation, confidence status (Observed vs Predicted), and floor-level spatial bounds.",
            action: { label: "Inspect 3D Floor Slabs", trigger: "inspect_floors" },
            suggestions: ["Town Planning FSI", "Bare-Earth DEM", "3D Cadastral Map"]
        },
        {
            id: "fsi",
            patterns: ["fsi", "far", "zoning", "town planning", "violation", "municipal", "compliance", "height limit", "overbuilt"],
            reply: "The <b>Town Planning & FSI Audit Desk</b> checks building footprints and vertical heights against sanctioned master plan regulations. Structures exceeding sanctioned FSI or height limits are flagged in neon red for municipal enforcement.",
            action: { label: "Highlight FSI Violations", trigger: "check_fsi" },
            suggestions: ["Rule 8 Review", "Floor Slabs", "Export CSV"]
        },
        {
            id: "rule8",
            patterns: ["rule 8", "rule8", "adjudication", "registrar", "verify", "statutory", "legal", "approve", "reject"],
            reply: "<b>Rule 8 Adjudication</b> represents the statutory verification gate under land-record modernisation rules. The Chief Cadastral Surveyor (Registrar) reviews AI-detected vertical boundaries, validates containment against ground Khasra parcels, and issues <b>Approve, Correct, or Reject</b> decisions.",
            action: { label: "View Rule 8 Gate", trigger: "open_rule8" },
            suggestions: ["Title Deed Certificate", "Grievance Redressal", "3D ULPIN Card"]
        },
        {
            id: "title_deed",
            patterns: ["title", "deed", "certificate", "ownership", "record", "download", "print"],
            reply: "The <b>3D Title Deed Certificate</b> provides an official, tamper-evident digital record of vertical property ownership, including bare-earth ground datum, MSL elevation, built-up floor area, containment score, and an offline-verifiable QR code.",
            action: { label: "View Title Deed", trigger: "open_title_deed" },
            suggestions: ["3D ULPIN Card", "Rule 8 Review", "Grievance Redressal"]
        },
        {
            id: "grievance",
            patterns: ["grievance", "complaint", "dispute", "sdm", "magistrate", "mutation", "petition", "hearing"],
            reply: "The <b>Revenue Grievance Cell (SDM Desk)</b> enables citizens to file mutation appeals and boundary boundary dispute petitions. The Sub-Divisional Magistrate can examine 3D spatial evidence, review survey logs, and resolve petitions legally.",
            action: { label: "Open Grievance Desk", trigger: "open_grievance" },
            suggestions: ["Rule 8 Review", "3D ULPIN Card", "Search Khasra"]
        },
        {
            id: "dem",
            patterns: ["dem", "dsm", "elevation", "ground", "satellite", "drone", "soi", "survey of india", "msl", "datum"],
            reply: "We integrate <b>Copernicus 30m Global DEM</b> with high-resolution <b>1m Drone Survey elevation models</b>. This separates ground surface datum from structural heights, eliminating topographic elevation bias in hilly or uneven terrain.",
            action: { label: "Toggle 1m Drone DEM", trigger: "toggle_dem" },
            suggestions: ["NDVI Canopy Check", "Floor Slabs", "3D Cadastral Map"]
        },
        {
            id: "ndvi",
            patterns: ["ndvi", "vegetation", "canopy", "trees", "greenery", "canopy evidence"],
            reply: "<b>NDVI (Normalized Difference Vegetation Index)</b> evidence filtering ensures tree canopies and overhangs are not falsely counted as building structures or floor heights. Green-dominant pixels are filtered during vertical surface extraction.",
            action: { label: "Toggle NDVI Vegetation Layer", trigger: "toggle_ndvi" },
            suggestions: ["Bare-Earth DEM", "Floor Slabs", "FSI Compliance"]
        },
        {
            id: "cities",
            patterns: ["city", "cities", "region", "bhopal", "bengaluru", "bangalore", "indore", "mumbai", "kalyan", "coimbatore", "pilot"],
            reply: "Our digital twin covers <b>6 Pilot Urban Regions</b> across India:<br>• 📍 <b>Bhopal</b> (MP Bhulekh - 85 Wards)<br>• 📍 <b>Bengaluru</b> (Karnataka Bhoomi)<br>• 📍 <b>Indore</b> (MP Bhulekh)<br>• 📍 <b>Navi Mumbai</b> (MahaBhumi - 111 Wards)<br>• 📍 <b>Kalyan-Dombivli / Mumbai</b> (123 Wards)<br>• 📍 <b>Coimbatore</b> (TN e-District - 100 Wards)",
            action: { label: "Switch to Bhopal Pilot", trigger: "switch_bhopal" },
            suggestions: ["3D Cadastral Map", "Floor Slabs", "Check FSI Violations"]
        },
        {
            id: "map_controls",
            patterns: ["map", "3d map", "satellite", "basemap", "cadastre", "perspective", "tilt", "navigate"],
            reply: "You can freely navigate the map in full 3D! Hold right-click or Ctrl+drag to tilt/rotate, or use the quick buttons in the top ticker bar to toggle between Cadastral Basemap, Satellite imagery, 3D Floors, and Subsurface utility infrastructure.",
            action: { label: "Switch to 3D Cadastral View", trigger: "tilt_3d_map" },
            suggestions: ["Show Floor Slabs", "Check FSI Violations", "3D ULPIN Card"]
        }
    ];

    // Fallback response generator
    function getFallbackResponse(query) {
        return {
            reply: `I understand you are asking about "<b>${escapeHtml(query)}</b>".<br><br>I can help you explore any aspect of the Bhumi Adhaar 3D Cadastral platform, such as 3D floor slabs, ULPIN identification, municipal FSI audits, Rule 8 adjudication, and satellite DEM models. What would you like to see?`,
            suggestions: ["3D ULPIN Card", "Floor Slabs", "Town Planning FSI", "Rule 8 Review"]
        };
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.innerText = text || "";
        return div.innerHTML;
    }

    function getFormattedTimestamp() {
        var now = new Date();
        var date = now.toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" }).replace(/\//g, "-");
        var time = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true });
        return `${date} ${time}`;
    }

    // Match query against knowledge base
    function findBestMatch(query) {
        var clean = query.toLowerCase().trim();
        var best = null;
        var maxScore = 0;

        for (var i = 0; i < KNOWLEDGE_BASE.length; i++) {
            var item = KNOWLEDGE_BASE[i];
            var score = 0;
            for (var j = 0; j < item.patterns.length; j++) {
                var p = item.patterns[j];
                if (clean === p) {
                    score += 10;
                } else if (clean.includes(p)) {
                    score += p.length;
                }
            }
            if (score > maxScore) {
                maxScore = score;
                best = item;
            }
        }

        return maxScore >= 2 ? best : getFallbackResponse(query);
    }

    // Execute actions directly on the portal UI
    function executeBotAction(trigger) {
        if (typeof window.showGovToast === "function") {
            window.showGovToast("Assistant Action", "Executing: " + trigger, "ph-lightning");
        }

        switch (trigger) {
            case "open_pvc_card":
                var navCard = document.getElementById("nav-my-bhu");
                if (navCard) navCard.click();
                else if (typeof window.openBhuCardModal === "function") window.openBhuCardModal();
                break;

            case "inspect_floors":
                var navFloors = document.getElementById("nav-floors");
                if (navFloors) navFloors.click();
                break;

            case "check_fsi":
                var navFsi = document.getElementById("nav-fsi");
                if (navFsi) navFsi.click();
                break;

            case "open_rule8":
                var navRule8 = document.getElementById("nav-rule8");
                if (navRule8) navRule8.click();
                break;

            case "open_title_deed":
                var navTitle = document.getElementById("nav-title");
                if (navTitle) navTitle.click();
                else if (typeof window.openCertificateModal === "function") window.openCertificateModal();
                break;

            case "open_grievance":
                var navGrievance = document.getElementById("nav-grievance");
                if (navGrievance) navGrievance.click();
                break;

            case "tilt_3d_map":
                var nav3d = document.getElementById("nav-3d-map");
                if (nav3d) nav3d.click();
                break;

            case "toggle_dem":
                var resToggle = document.getElementById("res-toggle");
                if (resToggle) {
                    resToggle.checked = !resToggle.checked;
                    resToggle.dispatchEvent(new Event("change"));
                }
                break;

            case "toggle_ndvi":
                var btnVeg = document.getElementById("toggle-veg");
                if (btnVeg) btnVeg.click();
                break;

            case "switch_bhopal":
                var regSel = document.getElementById("region-selector");
                if (regSel) {
                    regSel.value = "bhopal";
                    regSel.dispatchEvent(new Event("change"));
                }
                break;

            default:
                console.log("[Chatbot] Unknown action trigger:", trigger);
        }
    }

    // Build the Chatbot DOM elements matching the user's screenshots
    function createChatbotUI() {
        if (document.getElementById("bhumi-chatbot-widget")) return;

        var container = document.createElement("div");
        container.id = "bhumi-chatbot-widget";
        container.className = "bhumi-chat-widget-root";

        container.innerHTML = `
            <!-- 1. Floating Circular Mascot Launcher matching screenshot -->
            <button id="btn-chat-launcher" class="bhumi-chat-launcher" aria-label="Open Ask Bhumi Adhaar Assistant" title="Ask Bhumi Adhaar">
                <div class="chat-launcher-badge">
                    <img src="images/ask_aadhaar_avatar.jpg" alt="Avatar" class="chat-launcher-avatar">
                </div>
                <div class="chat-launcher-pill">
                    <span>Ask Bhumi Adhaar</span>
                </div>
            </button>

            <!-- 2. Chatbot Dialog Window matching screenshot -->
            <div id="bhumi-chat-dialog" class="bhumi-chat-dialog" style="display: none;" role="dialog" aria-modal="true" aria-label="Ask Bhumi Adhaar">
                <!-- Header: Periwinkle blue with mascot & greeting -->
                <div class="chat-header">
                    <div class="chat-header-avatar-box">
                        <img src="images/ask_aadhaar_avatar.jpg" alt="Mascot" class="chat-header-avatar">
                    </div>
                    <div class="chat-header-title-box">
                        <div class="chat-greeting-name">Hi, I am Bhu-Mitra.</div>
                        <div class="chat-greeting-sub">How May I help you!!</div>
                    </div>
                    <button id="btn-chat-close" class="chat-close-btn" aria-label="Close dialog">&times;</button>
                </div>

                <!-- Top Quick Suggestion Pills -->
                <div class="chat-pills-section" id="chat-pills-bar">
                    <div class="chat-pills-scroll">
                        <button class="chat-quick-pill" data-query="3D ULPIN Card">3D ULPIN Card</button>
                        <button class="chat-quick-pill" data-query="Floor Slabs">Floor Slabs</button>
                        <button class="chat-quick-pill" data-query="Town Planning FSI">Town Planning FSI</button>
                        <button class="chat-quick-pill" data-query="Rule 8 Review">Rule 8 Review</button>
                        <button class="chat-quick-pill" data-query="Title Deed">Title Deed</button>
                        <button class="chat-quick-pill" data-query="Pilot Cities">Pilot Cities</button>
                    </div>
                    <button id="btn-toggle-pills" class="chat-pills-toggle-btn" title="Toggle quick options" aria-label="Toggle pills">
                        <i class="ph ph-caret-up" id="pills-caret-icon"></i>
                    </button>
                </div>

                <!-- Messages Log -->
                <div class="chat-messages-area" id="chat-messages-area">
                    <!-- Default Initial Message matching screenshot -->
                    <div class="chat-msg-row bot">
                        <div class="chat-bubble bot-bubble">
                            Greetings!!<br>Please enter your query in the text field below and click on 'Send' button
                        </div>
                        <div class="chat-msg-time">${getFormattedTimestamp()}</div>
                    </div>
                </div>

                <!-- Bottom Input Bar -->
                <form id="chat-input-form" class="chat-input-bar">
                    <span class="chat-lang-badge" title="Language: English">EN</span>
                    <input type="text" id="chat-text-input" class="chat-text-input" placeholder="Please start a conversation" autocomplete="off">
                    <button type="submit" id="btn-chat-send" class="chat-send-btn" aria-label="Send message" title="Send message">
                        <i class="ph ph-paper-plane-right"></i>
                    </button>
                </form>
            </div>
        `;

        document.body.appendChild(container);

        // Bind interactive events
        bindChatbotEvents();
    }

    function bindChatbotEvents() {
        var launcher = document.getElementById("btn-chat-launcher");
        var dialog = document.getElementById("bhumi-chat-dialog");
        var btnClose = document.getElementById("btn-chat-close");
        var form = document.getElementById("chat-input-form");
        var input = document.getElementById("chat-text-input");
        var messagesArea = document.getElementById("chat-messages-area");
        var togglePills = document.getElementById("btn-toggle-pills");
        var pillsBar = document.getElementById("chat-pills-bar");
        var caretIcon = document.getElementById("pills-caret-icon");

        function toggleChat() {
            var isHidden = dialog.style.display === "none";
            dialog.style.display = isHidden ? "flex" : "none";
            if (isHidden) {
                launcher.classList.add("chat-active");
                input.focus();
                scrollBottom();
            } else {
                launcher.classList.remove("chat-active");
            }
        }

        if (launcher) launcher.addEventListener("click", toggleChat);
        if (btnClose) btnClose.addEventListener("click", toggleChat);

        var homeLauncher = document.getElementById("floatingAskAadhaar");
        if (homeLauncher) {
            homeLauncher.addEventListener("click", toggleChat);
            if (launcher) launcher.style.display = "none";
        }

        // Toggle pills bar
        if (togglePills && pillsBar) {
            togglePills.addEventListener("click", function () {
                var isCollapsed = pillsBar.classList.toggle("collapsed");
                if (caretIcon) {
                    caretIcon.className = isCollapsed ? "ph ph-caret-down" : "ph ph-caret-up";
                }
            });
        }

        // Quick suggestion pills click
        document.querySelectorAll(".chat-quick-pill").forEach(function (pill) {
            pill.addEventListener("click", function () {
                var query = this.getAttribute("data-query") || this.innerText;
                handleUserQuery(query);
            });
        });

        // Form submit
        if (form && input) {
            form.addEventListener("submit", function (e) {
                e.preventDefault();
                var text = input.value.trim();
                if (!text) return;
                input.value = "";
                handleUserQuery(text);
            });
        }

        function scrollBottom() {
            if (messagesArea) {
                messagesArea.scrollTop = messagesArea.scrollHeight;
            }
        }

        function handleUserQuery(text) {
            appendMessage("user", text);
            scrollBottom();

            // Typing simulation for realistic feel
            var typingId = appendTypingIndicator();
            scrollBottom();

            setTimeout(function () {
                removeTypingIndicator(typingId);
                var match = findBestMatch(text);
                appendBotResponse(match);
                scrollBottom();
            }, 450);
        }

        function appendMessage(sender, text) {
            var row = document.createElement("div");
            row.className = "chat-msg-row " + sender;
            row.innerHTML = `
                <div class="chat-bubble ${sender}-bubble">${escapeHtml(text)}</div>
                <div class="chat-msg-time">${getFormattedTimestamp()}</div>
            `;
            messagesArea.appendChild(row);
        }

        function appendBotResponse(res) {
            var row = document.createElement("div");
            row.className = "chat-msg-row bot";

            var actionHtml = "";
            if (res.action) {
                actionHtml = `
                    <div class="chat-action-wrap">
                        <button type="button" class="chat-action-btn" data-action="${res.action.trigger}">
                            <i class="ph ph-arrow-circle-right"></i> ${res.action.label}
                        </button>
                    </div>
                `;
            }

            var suggHtml = "";
            if (res.suggestions && res.suggestions.length) {
                suggHtml = `
                    <div class="chat-sub-suggestions">
                        ${res.suggestions.map(s => `<button type="button" class="chat-sub-pill" data-query="${s}">${s}</button>`).join("")}
                    </div>
                `;
            }

            row.innerHTML = `
                <div class="chat-bubble bot-bubble">
                    ${res.reply}
                    ${actionHtml}
                    ${suggHtml}
                </div>
                <div class="chat-msg-time">${getFormattedTimestamp()}</div>
            `;

            messagesArea.appendChild(row);

            // Bind newly added action buttons & pills
            row.querySelectorAll(".chat-action-btn").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    var trig = this.getAttribute("data-action");
                    executeBotAction(trig);
                });
            });

            row.querySelectorAll(".chat-sub-pill").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    var q = this.getAttribute("data-query");
                    handleUserQuery(q);
                });
            });
        }

        function appendTypingIndicator() {
            var id = "typing-" + Date.now();
            var row = document.createElement("div");
            row.id = id;
            row.className = "chat-msg-row bot typing-row";
            row.innerHTML = `
                <div class="chat-bubble bot-bubble typing-bubble">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </div>
            `;
            messagesArea.appendChild(row);
            return id;
        }

        function removeTypingIndicator(id) {
            var el = document.getElementById(id);
            if (el) el.remove();
        }
    }

    // Auto-initialize when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", createChatbotUI);
    } else {
        createChatbotUI();
    }

    // Expose window API to open or query programmatically if needed
    window.openBhumiChat = function (initialQuery) {
        var dialog = document.getElementById("bhumi-chat-dialog");
        if (dialog && dialog.style.display === "none") {
            var launcher = document.getElementById("btn-chat-launcher");
            if (launcher) launcher.click();
        }
        if (initialQuery) {
            var input = document.getElementById("chat-text-input");
            if (input) {
                input.value = initialQuery;
                var form = document.getElementById("chat-input-form");
                if (form) form.dispatchEvent(new Event("submit"));
            }
        }
    };
})();
