#!/usr/bin/env python
"""Idempotent schema migrations for columns/tables that create_all() won't add.

create_all() creates missing TABLES but never adds a column to an existing one,
so every column added after a table shipped needs an explicit ALTER here.

Runs from anywhere DATABASE_URL points (build.sh on Render, or a shell against
Neon — unlike the old Render Postgres, Neon is reachable from WSL).

    DATABASE_URL=postgresql://... python tools/migrate_schema.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app  # noqa: E402
from sqlalchemy import text  # noqa: E402
from src.online_poker.database import db  # noqa: E402

# (table, "column TYPE [constraints]") — added after the table first shipped.
ADD_COLUMNS = [
    ("users", "is_admin BOOLEAN NOT NULL DEFAULT FALSE"),
    ("poker_tables", "is_mixed_game BOOLEAN NOT NULL DEFAULT FALSE"),
    ("poker_tables", "raise_cap_override INTEGER"),  # BACKLOG 6.2.13
    ("poker_tables", "hand_cap_bb INTEGER"),  # BACKLOG 6.2.13
    ("poker_tables", "custom_mix_config TEXT"),  # Phase 9.3
    ("poker_tables", "custom_variant_config TEXT"),  # Phase 9.5
    ("game_session_state", "current_variant_index INTEGER"),
    ("game_session_state", "hands_in_current_variant INTEGER"),
    ("game_session_state", "orbit_size INTEGER"),
]

CREATE_TABLES = [
    # Phase 9.3 user mix library
    """
    CREATE TABLE IF NOT EXISTS custom_mixes (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id),
        display_name VARCHAR(60) NOT NULL,
        rotation TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_custom_mix_user_name UNIQUE (user_id, display_name)
    )
    """,
    # Phase 9.5 user variant library
    """
    CREATE TABLE IF NOT EXISTS custom_variants (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id),
        display_name VARCHAR(60) NOT NULL,
        base_variant VARCHAR(50),
        config TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_custom_variant_user_name UNIQUE (user_id, display_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS disabled_variants (
        id VARCHAR(36) PRIMARY KEY,
        variant_name VARCHAR(100) UNIQUE NOT NULL,
        reason TEXT,
        disabled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        disabled_by VARCHAR(36) NOT NULL REFERENCES users(id)
    )
    """,
]


def main() -> None:
    app, _ = create_app()
    with app.app_context():
        for table, column in ADD_COLUMNS:
            name = column.split()[0]
            try:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column}"))
                db.session.commit()
                print(f"Added {table}.{name}")
            except Exception as e:
                db.session.rollback()
                msg = str(e).lower()
                if "already exists" in msg or "duplicate" in msg:
                    print(f"{table}.{name} already exists")
                else:
                    print(f"Note ({table}.{name}): {e}")

        for ddl in CREATE_TABLES:
            table = ddl.split("IF NOT EXISTS")[1].split("(")[0].strip()
            try:
                db.session.execute(text(ddl))
                db.session.commit()
                print(f"Ensured table {table}")
            except Exception as e:
                db.session.rollback()
                print(f"Note ({table}): {e}")


if __name__ == "__main__":
    main()
