"""
Tests for SQLite migration in Phase 5A.
Validates:
- Migration on an existing database
- Migration preserves existing rows
- Old sessions default to left
- Idempotent execution
- New sessions/results with 'right' side
"""
import tempfile
from pathlib import Path
from sqlalchemy import create_engine, text
from digital_thread.migration import run_sqlite_migrations, get_table_columns


def test_sqlite_migration_on_legacy_db():
    # 1. Create a temporary SQLite database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    try:
        # 2. Construct legacy Phase 4C schema without 'side' columns
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    patient_id VARCHAR(64) NOT NULL,
                    exercise VARCHAR(128) NOT NULL,
                    started_at DATETIME NOT NULL,
                    ended_at DATETIME,
                    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
                )
            """))
            conn.execute(text("""
                CREATE INDEX ix_sessions_patient_id ON sessions (patient_id)
            """))
            conn.execute(text("""
                CREATE TABLE results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(64) UNIQUE NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    exercise VARCHAR(128) NOT NULL,
                    repetitions INTEGER NOT NULL,
                    rom_min FLOAT,
                    rom_max FLOAT,
                    rom_average FLOAT,
                    performance_score FLOAT,
                    feedback TEXT NOT NULL DEFAULT ''
                )
            """))
            conn.execute(text("""
                CREATE INDEX ix_results_session_id ON results (session_id)
            """))

            # 3. Seed pre-existing legacy rows
            conn.execute(text("""
                INSERT INTO sessions (session_id, patient_id, exercise, started_at, status)
                VALUES ('S-LEGACY-001', 'P-001', 'elbow_flexion', '2026-01-01T10:00:00', 'ACTIVE')
            """))
            conn.execute(text("""
                INSERT INTO results (session_id, exercise, repetitions, rom_min, rom_max, rom_average, performance_score, feedback)
                VALUES ('S-LEGACY-001', 'elbow_flexion', 12, 30.0, 150.0, 90.0, 92.5, 'Good job!')
            """))

        # Verify 'side' is absent before migration
        assert "side" not in get_table_columns(engine, "sessions")
        assert "side" not in get_table_columns(engine, "results")

        # 4. Run migration
        applied = run_sqlite_migrations(engine)
        assert applied["sessions"] is True
        assert applied["results"] is True

        # 5. Verify schema now includes 'side' with default 'left'
        assert "side" in get_table_columns(engine, "sessions")
        assert "side" in get_table_columns(engine, "results")

        # 6. Verify existing legacy rows preserved with side == 'left'
        with engine.connect() as conn:
            s_row = conn.execute(text("SELECT session_id, patient_id, exercise, side, status FROM sessions WHERE session_id='S-LEGACY-001'")).fetchone()
            assert s_row is not None
            assert s_row[0] == "S-LEGACY-001"
            assert s_row[1] == "P-001"
            assert s_row[2] == "elbow_flexion"
            assert s_row[3] == "left"
            assert s_row[4] == "ACTIVE"

            r_row = conn.execute(text("SELECT session_id, exercise, side, repetitions, performance_score, feedback FROM results WHERE session_id='S-LEGACY-001'")).fetchone()
            assert r_row is not None
            assert r_row[0] == "S-LEGACY-001"
            assert r_row[1] == "elbow_flexion"
            assert r_row[2] == "left"
            assert r_row[3] == 12
            assert r_row[4] == 92.5
            assert r_row[5] == "Good job!"

        # 7. Verify new insert with side='right' works
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO patients (patient_id, name, status, created_at, updated_at)
                VALUES ('P-002', 'Patient Two', 'ACTIVE', '2026-01-02T10:00:00', '2026-01-02T10:00:00')
            """))
            conn.execute(text("""
                INSERT INTO sessions (session_id, patient_id, exercise, side, started_at, status)
                VALUES ('S-NEW-RIGHT', 'P-002', 'knee_flexion', 'right', '2026-01-02T10:00:00', 'ACTIVE')
            """))
            conn.execute(text("""
                INSERT INTO results (session_id, exercise, side, repetitions, rom_min, rom_max, rom_average, performance_score, feedback)
                VALUES ('S-NEW-RIGHT', 'knee_flexion', 'right', 10, 40.0, 130.0, 85.0, 88.0, 'Nice work on right leg')
            """))

        with engine.connect() as conn:
            new_s = conn.execute(text("SELECT side FROM sessions WHERE session_id='S-NEW-RIGHT'")).scalar()
            assert new_s == "right"
            new_r = conn.execute(text("SELECT side FROM results WHERE session_id='S-NEW-RIGHT'")).scalar()
            assert new_r == "right"

        # 8. Verify idempotency - second run must not alter anything or throw errors
        second_run = run_sqlite_migrations(engine)
        assert second_run["sessions"] is False
        assert second_run["results"] is False

    finally:
        engine.dispose()
        if db_path.exists():
            try:
                db_path.unlink()
            except OSError:
                pass
