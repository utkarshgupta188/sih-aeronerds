"""Password hashing and signed session tokens.

Deliberately implemented with the Python standard library only
(``hashlib`` / ``hmac`` / ``secrets``) so the demo has no dependency on
passlib, bcrypt wheels or PyJWT, which keeps ``run_server.py`` runnable on a
clean machine during a live evaluation.

Design notes
------------
* Passwords are stretched with PBKDF2-HMAC-SHA256 and a per-user random
  salt. Iteration count is recorded inside the stored hash string so it can be
  raised later without invalidating existing rows.
* Comparison is done with :func:`hmac.compare_digest` to avoid timing leaks.
* Session tokens are opaque, HMAC-signed, single-purpose bearer tokens that
  carry only the session id, the user id and an expiry. No role or capability
  data is trusted from the token body -- every request re-reads the role from
  the database, so a role change takes effect immediately instead of waiting
  for the token to expire.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

# OWASP 2023 guidance for PBKDF2-HMAC-SHA256.
DEFAULT_ITERATIONS = 240_000
SALT_BYTES = 16
TOKEN_TTL_SECONDS = 60 * 60 * 8  # 8 hour working session

_ALGO_TAG = "pbkdf2_sha256"


# --------------------------------------------------------------------------
# encoding helpers
# --------------------------------------------------------------------------
def b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


# --------------------------------------------------------------------------
# passwords
# --------------------------------------------------------------------------
def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    """Hash ``password`` into a self-describing ``pbkdf2_sha256$...`` string."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO_TAG}${iterations}${b64e(salt)}${b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of ``password`` against a stored hash."""
    if not stored or not isinstance(password, str):
        return False
    try:
        algo, iterations_s, salt_b64, hash_b64 = stored.split("$", 3)
    except ValueError:
        return False
    if algo != _ALGO_TAG:
        return False
    try:
        iterations = int(iterations_s)
    except ValueError:
        return False
    expected = b64d(hash_b64)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b64d(salt_b64), iterations)
    return hmac.compare_digest(expected, candidate)


# --------------------------------------------------------------------------
# session tokens
# --------------------------------------------------------------------------
def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def sign_token(
    session_id: str,
    user_id: str,
    secret: str,
    *,
    expires_in: int = TOKEN_TTL_SECONDS,
    now: float | None = None,
) -> tuple[str, float]:
    """Return ``(token, expires_at_epoch_seconds)`` for a new session."""
    issued = int(now if now is not None else time.time())
    expires = issued + int(expires_in)
    body = {"sid": session_id, "uid": user_id, "iat": issued, "exp": expires}
    payload = b64e(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = b64e(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{signature}", float(expires)


def verify_token(
    token: str, secret: str, *, now: float | None = None
) -> dict | None:
    """Validate a bearer token and return its claims, or ``None`` if invalid.

    The caller must still re-read the user and role from storage; this only
    proves the token was issued by this server and has not expired.
    """
    if not token or not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 2:
        return None
    payload, signature = parts
    expected_sig = b64e(
        hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected_sig, signature):
        return None
    try:
        claims = json.loads(b64d(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict):
        return None
    if not claims.get("sid") or not claims.get("uid"):
        return None
    current = now if now is not None else time.time()
    try:
        exp = float(claims.get("exp", 0))
    except (TypeError, ValueError):
        return None
    if exp <= current:
        return None
    return claims


def new_secret() -> str:
    """Generate a strong signing secret (used when none is configured)."""
    return secrets.token_urlsafe(48)
