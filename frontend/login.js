/**
 * AeroNerds SIH26011 — Sign-in gate.
 *
 * Blocks the portal until a valid session exists, then hands control to the
 * app. Deliberately shows the four statutory seats and their capabilities so
 * a visitor understands the access model before typing a credential.
 *
 * If the auth API is unreachable (for example the portal is being served by
 * the static-only run_demo.py) this screen says so plainly rather than
 * silently falling back to an unauthenticated portal.
 */

(function () {
    "use strict";

    const Auth = window.AeroAuth;

    const DEMO_ACCOUNTS = [
        { user: "registrar", pass: "Demo@Registrar1", role: "Registrar", seat: "Rule 8 adjudication, manifest export" },
        { user: "planner", pass: "Demo@Planner1", role: "Town Planner", seat: "FSI / zoning audit" },
        { user: "sdm", pass: "Demo@SDM1", role: "SDM", seat: "Grievance adjudication" },
        { user: "citizen", pass: "Demo@Citizen1", role: "Citizen", seat: "Own linked records only" },
        { user: "citizen2", pass: "Demo@Citizen2", role: "Citizen", seat: "Own linked records only" }
    ];

    function el(id) {
        return document.getElementById(id);
    }

    function show(node, visible) {
        if (node) node.style.display = visible ? "" : "none";
    }

    function setStatus(text, tone) {
        const box = el("auth-status");
        if (!box) return;
        box.textContent = text || "";
        box.className = "auth-status" + (tone ? " tone-" + tone : "");
    }

    function openLogin(reason) {
        const overlay = el("auth-gate");
        if (!overlay) return;
        overlay.style.display = "flex";
        overlay.classList.remove("auth-gate-closing");
        setStatus(reason || "", reason ? "warn" : "");
        const user = el("auth-username");
        if (user) setTimeout(() => user.focus(), 60);
    }

    function closeLogin() {
        const overlay = el("auth-gate");
        if (!overlay) return;
        overlay.style.display = "none";
    }

    function renderRoleSummary(roles) {
        const box = el("auth-role-grid");
        if (!box) return;
        box.innerHTML = roles
            .map(function (r) {
                const caps = (r.capabilities || []).length;
                return (
                    '<div class="auth-role-card">' +
                    '<div class="auth-role-title"><i class="ph ' + r.icon + '"></i>' + r.title + "</div>" +
                    '<div class="auth-role-dept">' + r.department + "</div>" +
                    '<div class="auth-role-caps">' + caps + " capability" + (caps === 1 ? "" : "s") + "</div>" +
                    "</div>"
                );
            })
            .join("");
    }

    async function loadRoleCatalogue() {
        try {
            const res = await fetch("/api/meta/roles");
            if (!res.ok) return;
            const data = await res.json();
            renderRoleSummary(data.roles || []);
        } catch (e) {
            /* catalogue is decorative; sign-in still works without it */
        }
    }

    async function healthCheck() {
        try {
            const res = await fetch("/api/meta/health");
            if (!res.ok) throw new Error("bad status");
        } catch (e) {
            const warn = el("auth-api-warning");
            show(warn, true);
            const box = el("auth-api-warning-text");
            if (box) {
                box.innerHTML =
                    "The authentication service is not reachable, so this portal cannot verify who you are.<br>" +
                    "<strong>Start it with <code>python run_server.py</code></strong> and reload. " +
                    "The portal is intentionally not usable unsigned.";
            }
            setStatus("Auth service offline — access denied.", "error");
        }
    }

    function renderDemoAccounts() {
        const box = el("auth-demo-accounts");
        if (!box) return;
        box.innerHTML = DEMO_ACCOUNTS.map(function (a) {
            return (
                '<button type="button" class="auth-demo-row" data-user="' + a.user + '" data-pass="' + a.pass + '">' +
                '<span class="auth-demo-user">' + a.user + "</span>" +
                '<span class="auth-demo-role">' + a.role + "</span>" +
                '<span class="auth-demo-seat">' + a.seat + "</span>" +
                "</button>"
            );
        }).join("");
        box.querySelectorAll(".auth-demo-row").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const u = el("auth-username");
                const p = el("auth-password");
                if (u) u.value = btn.getAttribute("data-user");
                if (p) p.value = btn.getAttribute("data-pass");
                setStatus("Credentials filled from demo fixture. Press Sign in.", "info");
                const submit = el("auth-submit");
                if (submit) submit.focus();
            });
        });
    }

    async function submit(event) {
        if (event) event.preventDefault();
        const user = (el("auth-username") || {}).value || "";
        const pass = (el("auth-password") || {}).value || "";
        const btn = el("auth-submit");

        if (!user.trim() || !pass) {
            setStatus("Enter both a username and a password.", "warn");
            return;
        }
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="ph ph-spinner"></i> Verifying…';
        }
        setStatus("Verifying credentials and role…", "info");
        try {
            const session = await Auth.login(user.trim(), pass);
            setStatus("Signed in as " + session.full_name + ".", "ok");
            closeLogin();
            window.dispatchEvent(new CustomEvent("auth:ready", { detail: session }));
        } catch (err) {
            setStatus(err.message || "Sign-in failed.", "error");
            const p = el("auth-password");
            if (p) {
                p.value = "";
                p.focus();
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Sign in";
            }
        }
    }

    function setupLogout() {
        document.addEventListener("click", function (e) {
            const btn = e.target.closest && e.target.closest("[data-auth-logout]");
            if (!btn) return;
            e.preventDefault();
            Auth.logout().then(function () {
                openLogin("You have been signed out.");
            });
        });
    }

    function syncSessionUI() {
        const user = Auth.user;
        if (!user) return;
        document.querySelectorAll("[data-session-name]").forEach(function (n) {
            n.textContent = user.full_name;
        });
        document.querySelectorAll("[data-session-role]").forEach(function (n) {
            n.textContent = user.role_title;
        });
        document.querySelectorAll("[data-session-badge]").forEach(function (n) {
            n.textContent = user.role_badge;
        });
        document.querySelectorAll("[data-session-username]").forEach(function (n) {
            n.textContent = user.username;
        });
        document.querySelectorAll("[data-cap]").forEach(function (n) {
            const required = (n.getAttribute("data-cap") || "").split(",").map((s) => s.trim()).filter(Boolean);
            if (!required.length) return;
            const allowed = Auth.hasAny(required);
            n.style.display = allowed ? "" : "none";
            n.setAttribute("aria-hidden", allowed ? "false" : "true");
        });
    }

    /** Honour ?seat=<role> from the public landing page deep links, so an
     *  evaluator can jump straight to a desk and have it pre-filled. */
    function prefillFromSeatParam() {
        let seat = null;
        try {
            const params = new URLSearchParams(window.location.search);
            seat = params.get("seat");
            if (!seat) {
                const hash = window.location.hash.replace(/^#/, "");
                if (hash.indexOf("seat=") === 0) seat = decodeURIComponent(hash.slice(5));
            }
        } catch (e) {
            return;
        }
        if (!seat) return;

        const match = DEMO_ACCOUNTS.find(function (a) { return a.role.toLowerCase().indexOf(seat.toLowerCase()) !== -1; })
            || DEMO_ACCOUNTS.find(function (a) { return a.user === seat.toLowerCase(); });

        if (!match) return;
        const u = el("auth-username");
        const p = el("auth-password");
        if (u) u.value = match.user;
        if (p) p.value = match.pass;
        document.querySelectorAll(".auth-demo-row").forEach(function (row) {
            row.classList.toggle("is-highlighted", row.getAttribute("data-user") === match.user);
        });
        setStatus("Pre-filled the " + match.role + " demo seat from the link. Press Sign in.", "info");
    }

    document.addEventListener("DOMContentLoaded", async function () {
        renderDemoAccounts();
        setupLogout();
        prefillFromSeatParam();
        await healthCheck();
        loadRoleCatalogue();

        const form = el("auth-form");
        if (form) form.addEventListener("submit", submit);

        // A live session skips the gate entirely.
        const me = await Auth.validate();
        if (me) {
            syncSessionUI();
            window.dispatchEvent(new CustomEvent("auth:ready", { detail: me }));
        } else {
            openLogin();
        }
    });

    window.addEventListener("auth:expired", function () {
        openLogin("Your session expired. Please sign in again.");
    });
    window.addEventListener("auth:changed", syncSessionUI);
    window.addEventListener("auth:ready", syncSessionUI);

    window.AeroAuthGate = { open: openLogin, close: closeLogin };
})();
