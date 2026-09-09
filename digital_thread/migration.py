"""
SQLite migration utility for RehabTwin database schema evolution.
Applies non-destructive schema migrations, such as adding the 'side' column
with default 'left' while preserving all existing data, foreign keys, and indexes.
"""
from typing import Dict, Set
from sqlalchemy import text
from sqlalchemy.engine import Engine


def get_table_columns(engine: Engine, table_name: str) -> Set[str]:
    """Retrieve column names for a given SQLite table using PRAGMA table_info."""
    with engine.connect() as conn:
        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
        return {row[1] for row in result.fetchall()}


def run_sqlite_migrations(engine: Engine) -> Dict[str, bool]:
    """
    Safely and idempotently run migrations on an existing SQLite database.
    - Preserves all pre-existing rows in sessions and results.
    - Adds 'side' column with NOT NULL DEFAULT 'left' if absent.
    - Preserves all indexes and foreign keys.
    """
    applied = {"sessions": False, "results": False}

    # Only run SQLite PRAGMA checks if dialect is sqlite
    if engine.dialect.name != "sqlite":
        return applied

    with engine.begin() as conn:
        # Check sessions table
        sessions_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(sessions)")).fetchall()}
        if sessions_cols and "side" not in sessions_cols:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN side VARCHAR(16) NOT NULL DEFAULT 'left'"))
            applied["sessions"] = True

        # Check results table
        results_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(results)")).fetchall()}
        if results_cols and "side" not in results_cols:
            conn.execute(text("ALTER TABLE results ADD COLUMN side VARCHAR(16) NOT NULL DEFAULT 'left'"))
            applied["results"] = True

    return applied
