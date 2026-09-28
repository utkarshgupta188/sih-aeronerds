/**
 * AeroNerds SIH26011 — Authentication client & capability gate (frontend).
 *
 * Replaces the previous "persona switcher" pattern, where any visitor could
 * click a card and become the Registrar. Role is now decided by the server at
 * sign-in and re-asserted on every request; this file only:
 *
 *   1. holds the bearer token for the active session,
 *   2. exposes a capability check used to hide controls the signed-in role
 *      cannot exercise, and
 *   3. revalidates the session on load so a stale tab cannot keep a dead
 *      token in the UI.
 *
 * IMPORTANT: hiding a control here is a usability measure, not the security
 * boundary. The server re-checks every capability independently, so a user
 * who forces a hidden button visible still receives HTTP 403.
 */

(function () {
    "use strict";

    const TOKEN_KEY = "aeronerds_auth_token";
    const SESSION_KEY = "aeronerds_session_user";

    const Auth = {
        token: null,
        user: null,
        capabilities: new Set(),

        // -- storage -----------------------------------------------------
        load() {
            try {
                this.token = sessionStorage.getItem(TOKEN_KEY);
                const cached = sessionStorage.getItem(SESSION_KEY);
                if (cached) {
                    this.user = JSON.parse(cached);
                    this.capabilities = new Set(this.user.capabilities || []);
                }
            } catch (e) {
                this.token = null;
                this.user = null;
                this.capabilities = new Set();
            }
            return this;
        },

        persist() {
            try {
                if (this.token) sessionStorage.setItem(TOKEN_KEY, this.token);
                else sessionStorage.removeItem(TOKEN_KEY);
                if (this.user) sessionStorage.setItem(SESSION_KEY, JSON.stringify(this.user));
                else sessionStorage.removeItem(SESSION_KEY);
            } catch (e) {
                /* storage unavailable (private mode) — session stays in memory */
            }
        },

        // -- api ---------------------------------------------------------
        async request(path, options) {
            const opts = Object.assign({ headers: {} }, options || {});
            opts.headers = Object.assign({}, opts.headers);
            if (this.token) opts.headers["Authorization"] = "Bearer " + this.token;
            if (opts.body && typeof opts.body !== "string") {
                opts.headers["Content-Type"] = "application/json";
                opts.body = JSON.stringify(opts.body);
            }
            const res = await fetch(path, opts);
            let data = null;
            try {
                data = await res.json();
            } catch (e) {
                data = null;
            }
            if (res.status === 401 && this.token) {
                // Session died server-side: drop it and force re-auth.
                this.clear();
                window.dispatchEvent(new CustomEvent("auth:expired"));
            }
            if (!res.ok) {
                const err = new Error((data && data.detail) || "Request failed (" + res.status + ")");
                err.status = res.status;
                err.code = data && data.code;
                throw err;
            }
            return data;
        },

        // -- lifecycle ---------------------------------------------------
        async login(username, password) {
            const out = await this.request("/api/auth/login", {
                method: "POST",
                body: { username: username, password: password }
            });
            this.token = out.access_token;
            this.user = out.user;
            this.capabilities = new Set(out.user.capabilities || []);
            this.persist();
            window.dispatchEvent(new CustomEvent("auth:changed", { detail: this.user }));
            return this.user;
        },

        async logout() {
            try {
                if (this.token) await this.request("/api/auth/logout", { method: "POST" });
            } catch (e) {
                /* already invalid server-side */
            }
            this.clear();
            window.dispatchEvent(new CustomEvent("auth:changed", { detail: null }));
        },

        clear() {
            this.token = null;
            this.user = null;
            this.capabilities = new Set();
            this.persist();
        },

        /** Ask the server whether the held token is still good. */
        async validate() {
            if (!this.token) return null;
            try {
                const me = await this.request("/api/auth/me");
                this.user = me;
                this.capabilities = new Set(me.capabilities || []);
                this.persist();
                return me;
            } catch (e) {
                this.clear();
                return null;
            }
        },

        // -- authorisation helpers ---------------------------------------
        isSignedIn() {
            return !!this.user && !!this.token;
        },

        can(capability) {
            return this.capabilities.has(capability);
        },

        hasAny(list) {
            return (list || []).some((c) => this.capabilities.has(c));
        },

        isRole(roleId) {
            return !!this.user && this.user.role_id === roleId;
        },

        get roleId() {
            return this.user ? this.user.role_id : null;
        },

        get isCitizen() {
            return this.isRole("citizen");
        },

        /**
         * Show or hide every element carrying a data-cap attribute.
         * `data-cap` accepts a comma separated list (any-of semantics).
         */
        applyCapabilityVisibility(root) {
            const scope = root || document;
            scope.querySelectorAll("[data-cap]").forEach((el) => {
                const required = (el.getAttribute("data-cap") || "")
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean);
                const allowed = !required.length || this.hasAny(required);
                el.style.display = allowed ? "" : "none";
                el.setAttribute("aria-hidden", allowed ? "false" : "true");
                if (el.dataset.capHidden !== undefined && !allowed) {
                    el.dataset.capHidden = "1";
                } else {
                    delete el.dataset.capHidden;
                }
                if (el.tagName === "BUTTON" || el.tagName === "A") {
                    el.disabled = !allowed;
                    el.setAttribute("aria-disabled", allowed ? "false" : "true");
                }
            });
        },

        /** Visible explanation for a control the current role cannot use. */
        denialReason(capability) {
            if (!this.isSignedIn()) return "Sign in to continue.";
            const role = this.user.role_title || this.roleId;
            return role + " does not hold '" + capability + "' on this portal.";
        }
    };

    Auth.load();
    window.AeroAuth = Auth;

    /** Proactively hide capability-gated controls before sign-in. */
    document.addEventListener("DOMContentLoaded", () => Auth.applyCapabilityVisibility());
})();
