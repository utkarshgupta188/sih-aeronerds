"""SQLite-backed user, session and citizen-property link store.

Schema notes
------------
* ``citizen_links`` is what actually enforces data scope. A citizen can only
  ever read building ids present in this table for their own ``user_id``.
* Demo accounts are *fixtures for local evaluation only*. They are clearly
  flagged with ``is_demo = 1`` so no UI or export can ever present them as
  real government officers or real ownership records (AGENTS.md rule 9).
* The database file is generated at runtime and is git-ignored; it must never
  be committed.

Real deployments would move this to PostgreSQL/PostGIS per AGENTS.md rule 12.
SQLite is used here so the demo boots with zero infrastructure, and the
query surface is plain parameterised SQL so the swap is mechanical.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from . import security
from .rbac import normalise_role

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "aeronerds_auth.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    email          TEXT,
    full_name      TEXT NOT NULL,
    role_id        TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    jurisdiction   TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1,
    is_demo        INTEGER NOT NULL DEFAULT 1,
    created_at     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS citizen_links (
    user_id     TEXT NOT NULL,
    region      TEXT NOT NULL,
    building_id TEXT NOT NULL,
    unit_label  TEXT,
    PRIMARY KEY (user_id, region, building_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_links_user ON citizen_links (user_id);
"""


@dataclass(frozen=True)
class User:
    id: str
    username: str
    email: str | None
    full_name: str
    role_id: str
    jurisdiction: str | None
    is_active: bool
    is_demo: bool

    @property
    def is_citizen(self) -> bool:
        return self.role_id == "citizen"


# --------------------------------------------------------------------------
# Demo fixtures
# --------------------------------------------------------------------------
# Passwords are intentionally obvious and documented: this is a local
# evaluation fixture, not a credential store. Never reuse these anywhere.
DEMO_USERS: list[dict] = [
    {
        "username": "registrar",
        "password": "Demo@Registrar1",
        "full_name": "Dr. S. Nair",
        "role_id": "registrar",
        "jurisdiction": "Directorate of Land Records, DoLR (Bhopal)",
        "email": "registrar.demo@aeronerds.local",
    },
    {
        "username": "planner",
        "password": "Demo@Planner1",
        "full_name": "Er. Rajesh Verma",
        "role_id": "planner",
        "jurisdiction": "Bhopal Municipal Corporation (ULB)",
        "email": "planner.demo@aeronerds.local",
    },
    {
        "username": "sdm",
        "password": "Demo@SDM1",
        "full_name": "Shri A. K. Iyer",
        "role_id": "sdm",
        "jurisdiction": "SDM Revenue Division, Bhopal",
        "email": "sdm.demo@aeronerds.local",
    },
    {
        "username": "citizen",
        "password": "Demo@Citizen1",
        "full_name": "Demo Landowner",
        "role_id": "citizen",
        "jurisdiction": "Ward 41, Bhopal",
        "email": "citizen.demo@aeronerds.local",
    },
    {
        "username": "citizen2",
        "password": "Demo@Citizen2",
        "full_name": "Demo Co-owner",
        "role_id": "citizen",
        "jurisdiction": "Ward 40, Bhopal",
        "email": "citizen2.demo@aeronerds.local",
    },
]

#: Citizens are bound to building ids that genuinely exist in
#: ``frontend/data/bhopal_buildings_3d.geojson`` so the citizen view renders
#: real pipeline output rather than invented property records.
DEMO_CITIZEN_LINKS: dict[str, list[dict]] = {
    "citizen": [
        {
            "region": "bhopal",
            "building_id": "osm_way_413845798",
            "unit_label": "Unit 101 (observed 2-floor tag)",
        }
    ],
    "citizen2": [
        {
            "region": "bhopal",
            "building_id": "osm_way_375220424",
            "unit_label": "Unit 402 (modelled 4-floor mass)",
        }
    ],
}


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------
class UserStore:
    def __init__(self, db_path: str | os.PathLike | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
        self.seed_demo_users_if_empty()

    # -- plumbing ----------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # -- seeding -----------------------------------------------------------
    def seed_demo_users_if_empty(self) -> int:
        with self._connect() as conn:
            existing = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        if existing:
            return 0

        now = time.time()
        created = 0
        with self._connect() as conn:
            for spec in DEMO_USERS:
                user_id = f"u_{spec['username']}"
                conn.execute(
                    """
                    INSERT INTO users
                        (id, username, email, full_name, role_id, password_hash,
                         jurisdiction, is_active, is_demo, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)
                    """,
                    (
                        user_id,
                        spec["username"],
                        spec.get("email"),
                        spec["full_name"],
                        normalise_role(spec["role_id"]),
                        security.hash_password(spec["password"]),
                        spec.get("jurisdiction"),
                        now,
                    ),
                )
                created += 1
                for link in DEMO_CITIZEN_LINKS.get(spec["username"], []):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO citizen_links
                            (user_id, region, building_id, unit_label)
                        VALUES (?, ?, ?, ?)
                        """,
                        (user_id, link["region"], link["building_id"], link.get("unit_label")),
                    )
        return created

    # -- users -------------------------------------------------------------
    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            role_id=normalise_role(row["role_id"]),
            jurisdiction=row["jurisdiction"],
            is_active=bool(row["is_active"]),
            is_demo=bool(row["is_demo"]),
        )

    def get_by_username(self, username: str) -> tuple[User, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE lower(username) = lower(?)", (username,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row), row["password_hash"]

    def get_by_id(self, user_id: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def list_users(self) -> list[User]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY role_id, username").fetchall()
        return [self._row_to_user(r) for r in rows]

    # -- citizen scope -----------------------------------------------------
    def citizen_building_ids(self, user_id: str, region: str | None = None) -> list[str]:
        """Building ids this citizen is entitled to read."""
        with self._connect() as conn:
            if region:
                rows = conn.execute(
                    "SELECT building_id FROM citizen_links WHERE user_id = ? AND region = ?",
                    (user_id, region),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT building_id FROM citizen_links WHERE user_id = ?", (user_id,)
                ).fetchall()
        return [r["building_id"] for r in rows]

    def citizen_links(self, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT region, building_id, unit_label FROM citizen_links "
                "WHERE user_id = ? ORDER BY region, building_id",
                (user_id,),
            ).fetchall()
        return [
            {
                "region": r["region"],
                "building_id": r["building_id"],
                "unit_label": r["unit_label"],
            }
            for r in rows
        ]

    def link_building(self, user_id: str, region: str, building_id: str, unit_label: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO citizen_links (user_id, region, building_id, unit_label) "
                "VALUES (?, ?, ?, ?)",
                (user_id, region, building_id, unit_label),
            )

    # -- sessions ----------------------------------------------------------
    def create_session(self, session_id: str, user_id: str, expires_at: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (session_id, user_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, user_id, time.time(), expires_at),
            )

    def session_is_live(self, session_id: str, now: float | None = None) -> bool:
        current = now if now is not None else time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT expires_at FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return bool(row) and float(row["expires_at"]) > current

    def revoke_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def purge_expired_sessions(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (time.time(),))
            return cur.rowcount or 0


def build_store(db_path: str | os.PathLike | None = None) -> UserStore:
    return UserStore(db_path)
