"""Role definitions and capability-based access control.

Four statutory roles are modelled, matching the jurisdictions the portal
already presents in its navigation bar:

======================  ====================================================
Role                    Statutory seat
======================  ====================================================
``registrar``           Directorate of Land Records / DoLR (Rule 8 gate)
``planner``             Urban Local Body -- Town Planning Officer (ULB)
``sdm``                 Sub-Divisional Magistrate / Grievance Officer
``citizen``             3D ULPIN landowner / resident
======================  ====================================================

Access is expressed as *capabilities*, not as scattered role equality
checks, so that adding a role later does not require hunting down every
``if role == ...`` in the codebase (AGENTS.md rule 6: keep deterministic
access rules out of opaque logic).

Scope rule that matters most
----------------------------
``parcel:read:all`` and ``building:read:all`` are held by government roles
only. A citizen holds ``parcel:read:own`` / ``building:read:own``, and the
citizen record endpoint additionally filters to the building ids linked to
that citizen's own account. Capability alone is never sufficient for a
citizen to read another citizen's record -- the row filter is the real
boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# capability vocabulary
# --------------------------------------------------------------------------
CAP_READ_PARCELS_ALL = "parcel:read:all"
CAP_READ_PARCELS_OWN = "parcel:read:own"
CAP_READ_BUILDINGS_ALL = "building:read:all"
CAP_READ_BUILDINGS_OWN = "building:read:own"
CAP_ADJUDICATE = "review:adjudicate"          # APPROVE / CORRECT / REJECT / UNRESOLVED
CAP_ANNOTATE = "review:annotate"              # flag for field verification
CAP_ZONING_AUDIT = "zoning:audit"             # FSI / FAR / height compliance scan
CAP_GRIEVANCE_ADJUDICATE = "grievance:adjudicate"
CAP_GRIEVANCE_FILE = "grievance:file"
CAP_EXPORT_MANIFEST = "manifest:export"
CAP_CERTIFICATE_ISSUE = "certificate:issue"
CAP_CERTIFICATE_VIEW_OWN = "certificate:view:own"
CAP_AUDIT_LOG_READ = "auditlog:read"

#: Capabilities that must never be granted to a citizen-facing account.
AUTHORITY_ONLY_CAPABILITIES = frozenset(
    {
        CAP_ADJUDICATE,
        CAP_EXPORT_MANIFEST,
        CAP_CERTIFICATE_ISSUE,
        CAP_AUDIT_LOG_READ,
        CAP_ZONING_AUDIT,
        CAP_GRIEVANCE_ADJUDICATE,
        CAP_READ_PARCELS_ALL,
        CAP_READ_BUILDINGS_ALL,
    }
)


@dataclass(frozen=True)
class Role:
    id: str
    title: str
    dept: str
    badge: str
    icon: str
    workspace_id: str
    subtitle: str
    capabilities: frozenset[str]
    #: Fields this role may see in a full cadastral record.
    can_see_ai_internals: bool = False

    def can(self, capability: str) -> bool:
        return capability in self.capabilities


ROLES: dict[str, Role] = {
    "registrar": Role(
        id="registrar",
        title="Chief Cadastral Surveyor",
        dept="Directorate of Land Records & SVAMITVA",
        badge="REGISTRAR",
        icon="ph-shield-check",
        workspace_id="registrar-workspace",
        subtitle="Statutory 3D Cadastral Delineation & ULPIN Adjudication Desk",
        capabilities=frozenset(
            {
                CAP_READ_PARCELS_ALL,
                CAP_READ_BUILDINGS_ALL,
                CAP_ADJUDICATE,
                CAP_ANNOTATE,
                CAP_GRIEVANCE_ADJUDICATE,
                CAP_EXPORT_MANIFEST,
                CAP_CERTIFICATE_ISSUE,
                CAP_AUDIT_LOG_READ,
            }
        ),
        can_see_ai_internals=True,
    ),
    "planner": Role(
        id="planner",
        title="Town Planning Officer",
        dept="Urban Local Body (ULB)",
        badge="TOWN PLANNER",
        icon="ph-buildings",
        workspace_id="planner-workspace",
        subtitle="Vertical FSI / Height Compliance & Encroachment Auditing",
        capabilities=frozenset(
            {
                CAP_READ_PARCELS_ALL,
                CAP_READ_BUILDINGS_ALL,
                CAP_ZONING_AUDIT,
                CAP_ANNOTATE,
                CAP_EXPORT_MANIFEST,
            }
        ),
        can_see_ai_internals=True,
    ),
    "sdm": Role(
        id="sdm",
        title="Sub-Divisional Magistrate",
        dept="Revenue Administration / Grievance Cell",
        badge="SDM",
        icon="ph-gavel",
        workspace_id="sdm-workspace",
        subtitle="Citizen Grievance Adjudication & Escalation Desk",
        capabilities=frozenset(
            {
                CAP_READ_PARCELS_ALL,
                CAP_READ_BUILDINGS_ALL,
                CAP_GRIEVANCE_ADJUDICATE,
                CAP_ANNOTATE,
            }
        ),
        can_see_ai_internals=True,
    ),
    "citizen": Role(
        id="citizen",
        title="Citizen Landowner",
        dept="Vertical property record",
        badge="PROPERTY OWNER",
        icon="ph-user-circle",
        workspace_id="citizen-workspace",
        subtitle="3D property passbook & self-verification",
        capabilities=frozenset(
            {
                CAP_READ_PARCELS_OWN,
                CAP_READ_BUILDINGS_OWN,
                CAP_GRIEVANCE_FILE,
                CAP_CERTIFICATE_VIEW_OWN,
            }
        ),
        can_see_ai_internals=False,
    ),
}

#: Legacy key -> current role id, so existing saved UIs do not hard-fail.
ROLE_ALIASES = {"admin": "registrar"}

DEFAULT_ROLE = "registrar"


def normalise_role(role_key: str | None) -> str:
    if not role_key:
        return DEFAULT_ROLE
    key = str(role_key).strip().lower()
    key = ROLE_ALIASES.get(key, key)
    return key if key in ROLES else DEFAULT_ROLE


def get_role(role_key: str | None) -> Role:
    return ROLES[normalise_role(role_key)]


def capabilities_for(role_key: str | None) -> frozenset[str]:
    return get_role(role_key).capabilities


def has_capability(role_key: str | None, capability: str) -> bool:
    return get_role(role_key).can(capability)


def is_authority_role(role_key: str | None) -> bool:
    return normalise_role(role_key) != "citizen"


# --------------------------------------------------------------------------
# citizen field redaction
# --------------------------------------------------------------------------
#: Internal / model-facing fields a citizen must never receive. AGENTS.md rule 5
#: is that AI assists and does not adjudicate; exposing raw anomaly scores to a
#: landowner would invite the opposite misreading, so they are stripped at the
#: API boundary rather than merely hidden with CSS.
CITIZEN_REDACTED_FIELDS = frozenset(
    {
        "ai_anomaly_flag",
        "ai_anomaly_score",
        "ai_anomaly_rank",
        "anomaly_status",
        "parcel_overlap_ratio",
        "reviewer_status",
        "reviewer_note",
        "reviewer_id",
        "reviewed_at",
        "raw_evidence_vector",
        "model_internals",
    }
)

#: Human-readable explanation shown to a citizen in place of a redacted field.
CITIZEN_REDACTION_NOTICE = (
    "Internal model diagnostics are withheld from the landowner view. "
    "The anomaly model assists review and never decides a title question."
)


def redact_for_citizen(record: dict) -> dict:
    """Return a copy of ``record`` with citizen-inappropriate fields removed."""
    return {k: v for k, v in record.items() if k not in CITIZEN_REDACTED_FIELDS}
