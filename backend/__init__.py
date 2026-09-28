"""AeroNerds SIH26011 — Authenticated backend package.

Provides server-side authentication and role-based access control for the
3D ULPIN vertical property mapping portal.

IMPORTANT (AGENTS.md rule 2 / 9):
    This service does NOT create or recognise official ULPINs. It only
    authenticates users and scopes which *proposed* evidence records each
    role is permitted to read. Legal recognition remains with the competent
    authority.
"""

__all__ = ["security", "rbac", "users", "schemas", "main"]
