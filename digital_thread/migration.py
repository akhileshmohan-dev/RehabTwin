"""
SQLite migration utility for RehabTwin database schema evolution.
Applies non-destructive schema migrations:
- Adds 'side' column with default 'left' if absent in sessions and results.
- Creates 'patients' table if absent and backfills historical distinct patient_ids from sessions.
- Creates 'patient_exercises' table with foreign keys and unique constraints if absent.
- Preserves all existing data, foreign keys, and indexes.
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
    - Creates 'patients' table and backfills patient records from existing sessions.
    - Creates 'patient_exercises' table for therapist rehabilitation plans.
    - Preserves all indexes and foreign keys.
    """
    applied = {"sessions": False, "results": False, "patients": False, "patient_exercises": False}

    # Only run SQLite PRAGMA checks if dialect is sqlite
    if engine.dialect.name != "sqlite":
        return applied

    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}

        # 1. Create patients table if absent
        if "patients" not in tables:
            conn.execute(text("""
                CREATE TABLE patients (
                    patient_id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(128) NOT NULL,
                    age INTEGER,
                    gender VARCHAR(32),
                    phone VARCHAR(32),
                    email VARCHAR(128),
                    notes TEXT,
                    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """))
            applied["patients"] = True

        # 2. Backfill patients from existing sessions if present
        if "sessions" in tables:
            conn.execute(text("""
                INSERT OR IGNORE INTO patients (patient_id, name, status, created_at, updated_at)
                SELECT DISTINCT patient_id, 'Patient ' || patient_id, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM sessions
                WHERE patient_id IS NOT NULL AND patient_id != ''
            """))

            sessions_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(sessions)")).fetchall()}
            if sessions_cols and "side" not in sessions_cols:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN side VARCHAR(16) NOT NULL DEFAULT 'left'"))
                applied["sessions"] = True

        # 3. Check results table columns
        if "results" in tables:
            results_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(results)")).fetchall()}
            if results_cols and "side" not in results_cols:
                conn.execute(text("ALTER TABLE results ADD COLUMN side VARCHAR(16) NOT NULL DEFAULT 'left'"))
                applied["results"] = True

        # 4. Check patient_exercises table
        if "patient_exercises" not in tables:
            conn.execute(text("""
                CREATE TABLE patient_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id VARCHAR(64) NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
                    exercise_id VARCHAR(64) NOT NULL,
                    side VARCHAR(16) NOT NULL DEFAULT 'left',
                    target_rom FLOAT,
                    target_repetitions INTEGER,
                    sessions_per_day INTEGER DEFAULT 1,
                    notes TEXT DEFAULT '',
                    active BOOLEAN NOT NULL DEFAULT 1,
                    assigned_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_patient_exercise_side UNIQUE (patient_id, exercise_id, side)
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patient_exercises_patient_id ON patient_exercises(patient_id)"))
            applied["patient_exercises"] = True

    # 5. Check if sessions table has enforced foreign key to patients
    raw_conn = engine.raw_connection()
    cursor = raw_conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        if cursor.fetchone():
            cursor.execute("PRAGMA foreign_key_list(sessions)")
            fks = cursor.fetchall()
            has_patient_fk = any(row[2].lower() == "patients" for row in fks)
            if not has_patient_fk:
                # Inspect actual foreign-key relationships of results and frames before rebuild
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='results'")
                has_results_table = cursor.fetchone() is not None
                results_fks_before = []
                if has_results_table:
                    cursor.execute("PRAGMA foreign_key_list(results)")
                    results_fks_before = cursor.fetchall()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='frames'")
                has_frames_table = cursor.fetchone() is not None
                frames_fks_before = []
                if has_frames_table:
                    cursor.execute("PRAGMA foreign_key_list(frames)")
                    frames_fks_before = cursor.fetchall()

                # Perform safe SQLite 12-step table rebuild
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.execute("PRAGMA legacy_alter_table=ON")
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute("""
                    CREATE TABLE sessions_new (
                        session_id VARCHAR(64) PRIMARY KEY,
                        patient_id VARCHAR(64) NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
                        exercise VARCHAR(128) NOT NULL,
                        side VARCHAR(16) NOT NULL DEFAULT 'left',
                        started_at DATETIME NOT NULL,
                        ended_at DATETIME,
                        status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
                    )
                """)
                cursor.execute("""
                    INSERT INTO sessions_new (session_id, patient_id, exercise, side, started_at, ended_at, status)
                    SELECT session_id, patient_id, exercise, side, started_at, ended_at, status FROM sessions
                """)
                cursor.execute("DROP TABLE sessions")
                cursor.execute("ALTER TABLE sessions_new RENAME TO sessions")
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_sessions_patient_id ON sessions (patient_id)")
                cursor.execute("COMMIT")
                cursor.execute("PRAGMA legacy_alter_table=OFF")
                cursor.execute("PRAGMA foreign_keys=ON")

                # Verify referential integrity
                cursor.execute("PRAGMA foreign_key_check")
                violations = cursor.fetchall()
                if violations:
                    raise RuntimeError(f"Foreign key violations detected after sessions table rebuild: {violations}")

                # Verify child foreign keys remain intact
                if has_results_table:
                    cursor.execute("PRAGMA foreign_key_list(results)")
                    results_fks_after = cursor.fetchall()
                    if results_fks_before and not any(r[2].lower() == "sessions" for r in results_fks_after):
                        raise RuntimeError("Results table lost foreign key reference to sessions")

                if has_frames_table:
                    cursor.execute("PRAGMA foreign_key_list(frames)")
                    frames_fks_after = cursor.fetchall()
                    if frames_fks_before and not any(r[2].lower() == "sessions" for r in frames_fks_after):
                        raise RuntimeError("Frames table lost foreign key reference to sessions")

                raw_conn.commit()
                applied["sessions"] = True
    finally:
        raw_conn.close()

    return applied
