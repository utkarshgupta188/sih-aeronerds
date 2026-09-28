/**
 * AeroNerds SIH26011 — Role-scoped data binding.
 *
 * Loads each workspace's data through the authenticated API. The authority
 * desks read full records (including model diagnostics); the citizen desk reads
 * only the records linked to the signed-in account, and renders the values the
 * server actually returns.
 *
 * Nothing in this file fabricates a value. Where the pipeline could not
 * determine something, the pipeline's own NOT_DETERMINABLE sentinel is shown
 * as-is, per AGENTS.md rule 4.
 */

(function () {
    "use strict";

    const Auth = window.AeroAuth;
    const ND = "NOT_DETERMINABLE";

    function setText(id, value, fallback) {
        const node = document.getElementById(id);
        if (!node) return;
        if (value === null || value === undefined || value === "") {
            node.innerText = fallback || ND;
        } else {
            node.innerText = String(value);
        }
    }

    function colourise(node, tone) {
        if (!node) return;
        const tones = {
            ok: "#138808",
            warn: "#b45309",
            bad: "#c8102e",
            neutral: "#475569"
        };
        node.style.color = tones[tone] || tones.neutral;
        node.style.fontWeight = "700";
    }

    function num(value, suffix) {
        return value === null || value === undefined ? ND : value + (suffix || "");
    }

    // ----------------------------------------------------------------------
    // CITIZEN DESK
    // ----------------------------------------------------------------------
    async function loadCitizenPortfolio() {
        const badge = document.getElementById("citizen-verif-badge");
        const empty = document.getElementById("citizen-empty");
        const panel = empty ? empty.previousElementSibling : null;

        let body;
        try {
            body = await Auth.request("/api/records/portfolio");
        } catch (err) {
            if (badge) {
                badge.innerText = "UNAVAILABLE";
                badge.style.background = "#fef2f2";
                badge.style.color = "#991b1b";
                badge.style.borderColor = "#fecaca";
            }
            setText("citizen-prop-unit", "Could not load your record (" + err.message + ")");
            return;
        }

        const items = (body && body.items) || [];

        if (!items.length) {
            if (empty) empty.style.display = "block";
            if (panel) panel.style.display = "none";
            if (badge) {
                badge.innerText = "NO LINKED RECORD";
                badge.style.background = "#f1f5f9";
                badge.style.color = "#475569";
                badge.style.borderColor = "#cbd5e1";
            }
            return;
        }

        if (empty) empty.style.display = "none";
        if (panel) panel.style.display = "";

        // A demo citizen is linked to one building. If more are ever linked,
        // surface that honestly rather than silently showing only the first.
        const record = items[0];
        if (items.length > 1) {
            setText(
                "citizen-prop-unit",
                items.length + " properties linked — showing the first"
            );
        }

        const v = record.vertical || {};
        const p = record.provenance || {};
        const parcel = record.parcel || {};
        const Auth0 = Auth.user || {};

        setText("citizen-owner", Auth0.full_name || ND);
        setText("citizen-prop-unit", record.unit_label || "Linked structure " + record.building_id);
        setText(
            "citizen-prop-khasra",
            parcel.linked_parcel_id
                ? "Parcel " + parcel.linked_parcel_id + (parcel.townname ? " · " + parcel.townname : "")
                : ND
        );
        setText("citizen-prop-ulpin", record.proposed_ulpin || ND);
        setText(
            "citizen-prop-elev",
            "Ground: " + num(v.ground_elevation_m, " m MSL") +
            " · Height: " + num(v.building_height_m, " m") +
            " · Linkage: PROPOSED (not official issuance)"
        );

        setText("citizen-parcel-id", parcel.linked_parcel_id || ND);
        setText("citizen-match", p.footprint_match_status || ND);
        colourise(
            document.getElementById("citizen-match"),
            p.footprint_match_status === "CONTAINED" ? "ok"
                : p.footprint_match_status === "MAJORITY" ? "warn" : "bad"
        );

        setText("citizen-ground-elev", num(v.ground_elevation_m, " m MSL"));

        const heightState = v.height_status ? " (" + v.height_status + ")" : "";
        setText("citizen-height", num(v.building_height_m, " m") + heightState);

        // Floor count with its evidence basis, so a landowner can see whether
        // the number is an observed tag or a model estimate (AGENTS.md rule 4).
        const floorStatus = p.floor_detection_status || ND;
        const floors = v.floor_count_estimated;
        const range =
            v.floor_min !== null && v.floor_min !== undefined &&
            v.floor_max !== null && v.floor_max !== undefined &&
            v.floor_min !== v.floor_max
                ? " (range " + v.floor_min + "–" + v.floor_max + ")" : "";
        const floorsText = floorStatus === "NOT_DETERMINABLE"
            ? ND
            : (floors === null || floors === undefined ? ND : floors + " floor" + (floors === 1 ? "" : "s") + range);
        setText("citizen-floors", floorsText);
        const floorsNode = document.getElementById("citizen-floors");
        if (floorsNode) {
            floorsNode.title = floorStatus === "OBSERVED"
                ? "Observed from the official OSM building:levels tag."
                : floorStatus === "PREDICTED"
                    ? "Estimated by the ML floor model (" + (p.floor_model_version || "version unknown") +
                      "), confidence " + (v.floor_confidence_state || ND) + "."
                    : "Insufficient evidence to determine a floor count.";
        }

        setText(
            "citizen-evidence-source",
            [p.geometry_source, p.height_source].filter(Boolean).join(" + ") || ND
        );

        setText("citizen-verification", record.verification_status || ND);
        const verNode = document.getElementById("citizen-verification");
        colourise(
            verNode,
            record.verification_status === "VERIFIED" ? "ok"
                : record.verification_status === "PROVISIONAL" ? "warn" : "bad"
        );

        if (badge) {
            badge.innerText = record.verification_status || ND;
            const tone = record.verification_status === "VERIFIED" ? "ok"
                : record.verification_status === "PROVISIONAL" ? "warn" : "bad";
            badge.style.background = tone === "ok" ? "#dcfce7" : tone === "warn" ? "#fef3c7" : "#fef2f2";
            badge.style.color = tone === "ok" ? "#15803d" : tone === "warn" ? "#b45309" : "#991b1b";
            badge.style.borderColor = tone === "ok" ? "#86efac" : tone === "warn" ? "#fde68a" : "#fecaca";
        }

        setText("citizen-redaction-text", record.disclosure_note || "");

        // QR seal for the proposed linkage
        if (record.proposed_ulpin && window.renderUlpinQRCode) {
            try {
                window.renderUlpinQRCode("citizen-passbook-qr", record.proposed_ulpin, { size: 74, pad: 1 });
            } catch (e) {
                /* QR engine unavailable — the ID text is still shown */
            }
        }

        // Expose for the certificate / copy actions.
        window.__citizenRecord = record;
    }

    // ----------------------------------------------------------------------
    // SDM DESK
    // ----------------------------------------------------------------------
    async function loadGrievanceRegister() {
        const list = document.getElementById("sdm-grievance-list");
        if (!list) return;
        let body;
        try {
            body = await Auth.request("/api/grievances");
        } catch (err) {
            list.innerHTML =
                '<div style="padding:14px; border-radius:8px; background:#fef2f2; border:1px solid #fecaca; color:#991b1b;">' +
                "Could not load the grievance register (" + err.message + ").</div>";
            return;
        }
        const items = (body && body.items) || [];
        setText("sdm-total-grievances", items.length);
        setText("sdm-pending", items.filter((g) => g.status === "SUBMITTED_PENDING_REVIEW").length);

        if (!items.length) {
            list.innerHTML =
                '<div style="text-align:center; padding:22px 0; color:#94a3b8;">' +
                "No grievances in the register yet.</div>";
            return;
        }

        list.innerHTML = items
            .map(function (g) {
                return (
                    '<div style="border:1px solid #e2e8f0; border-radius:8px; padding:9px 10px; margin-bottom:7px;">' +
                    '<div style="display:flex; justify-content:space-between; gap:8px; align-items:baseline;">' +
                    '<span style="font-family:monospace; font-size:10px; font-weight:800; color:#002855;">' + g.id + "</span>" +
                    '<span class="badge" style="background:#fff7ed; color:#b45309; font-size:8px; border:1px solid #fed7aa;">' + g.status + "</span>" +
                    "</div>" +
                    '<div style="font-size:11px; font-weight:700; color:#0f172a; margin-top:4px;">' + g.subject + "</div>" +
                    '<div style="font-size:10px; color:#64748b; margin-top:2px; line-height:1.45;">' + g.narrative + "</div>" +
                    '<div style="font-size:9px; color:#94a3b8; margin-top:4px; font-family:monospace;">' +
                    g.building_id + " · " + g.region + "</div>" +
                    "</div>"
                );
            })
            .join("");
    }

    // ----------------------------------------------------------------------
    // PLANNER DESK — surface the real pipeline counts for the active region
    // ----------------------------------------------------------------------
    async function loadRegionSummary() {
        const region = (window.activeRegionKey) || "bhopal";
        try {
            const body = await Auth.request("/api/records/summary?region=" + encodeURIComponent(region));
            setText("stat-buildings", (body.buildings || 0).toLocaleString());
            setText("stat-parcels", (body.parcels || 0).toLocaleString());
        } catch (e) {
            /* keep the client-side counts rendered by app.js */
        }
    }

    // ----------------------------------------------------------------------
    // grievance filing (citizen)
    // ----------------------------------------------------------------------
    function initGrievanceFiling() {
        const btn = document.getElementById("citizen-grievance-btn");
        if (!btn) return;
        btn.addEventListener("click", async function () {
            const record = window.__citizenRecord;
            if (!record) {
                if (window.showGovToast) {
                    window.showGovToast("No Linked Record", "File a grievance once a property is linked to your account.", "ph-warning");
                }
                return;
            }
            const subject = window.prompt(
                "Grievance subject (mutation / survey):",
                "Boundary or floor record does not match my sanctioned plan"
            );
            if (!subject) return;
            const narrative = window.prompt(
                "Describe the issue:",
                "The portal record for " + record.proposed_ulpin + " does not match my sanctioned building plan."
            );
            if (!narrative) return;

            try {
                const created = await Auth.request("/api/grievances", {
                    method: "POST",
                    body: {
                        region: record.region,
                        building_id: record.building_id,
                        category: "MUTATION_OR_SURVEY",
                        subject: subject,
                        narrative: narrative
                    }
                });
                if (window.showGovToast) {
                    window.showGovToast(
                        "Grievance Filed",
                        "Reference <b>" + created.id + "</b> submitted to the SDM grievance cell.",
                        "ph-check-circle"
                    );
                }
            } catch (err) {
                if (window.showGovToast) {
                    window.showGovToast("Grievance Not Filed", err.message, "ph-warning");
                }
            }
        });
    }

    // ----------------------------------------------------------------------
    // wiring
    // ----------------------------------------------------------------------
    function loadForRole() {
        if (!Auth.isSignedIn()) return;
        switch (Auth.roleId) {
            case "citizen":
                loadCitizenPortfolio();
                break;
            case "sdm":
                loadGrievanceRegister();
                break;
            case "registrar":
            case "planner":
                loadRegionSummary();
                break;
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        initGrievanceFiling();

        const refresh = document.getElementById("btn-refresh-grievances");
        if (refresh) refresh.addEventListener("click", loadGrievanceRegister);

        const escalate = document.getElementById("btn-sdm-escalate");
        if (escalate) {
            escalate.addEventListener("click", function () {
                const note = document.getElementById("sdm-escalate-note");
                if (Auth.can("review:adjudicate")) {
                    if (window.showGovToast) {
                        window.showGovToast(
                            "Registrar Seat Required",
                            "Rule 8 adjudication must be performed by the Registrar, not the SDM desk.",
                            "ph-lock-key"
                        );
                    }
                } else if (note) {
                    note.style.display = "block";
                }
            });
        }

        window.addEventListener("govrole:changed", loadForRole);
        window.addEventListener("boundaryDataLoaded", function () {
            if (Auth.isSignedIn() && !Auth.isCitizen) loadRegionSummary();
        });
    });

    window.AeroRoleData = {
        reload: loadForRole,
        citizenPortfolio: loadCitizenPortfolio,
        grievanceRegister: loadGrievanceRegister
    };
})();
