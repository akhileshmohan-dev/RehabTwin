"""
Database and Persistence Test Suite for Phase 6A + 6B:
- Patient SQLite persistence
- PatientExercise SQLite persistence
- Foreign-key enforcement under PRAGMA foreign_keys=ON
- Uniqueness constraints on (patient_id, exercise_id, side)
- Migration on legacy DB with sessions and results
- Existing session/result records remain intact
- Restart durability: dispose engine, reconnect, verify survival
"""
import os
import tempfile
import unittest
from pathlib import Path
from sqlalchemy import create_engine, text, event
from sqlalchemy.exc import IntegrityError

from digital_thread.db import Database
from digital_thread.models import Patient, PatientExerciseAssignment, Session, Result, utc_now
from digital_thread.migration import run_sqlite_migrations, get_table_columns
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemyAssignmentRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyResultRepository,
)


class TestPatientDatabasePersistence(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_db_persist_{os.urandom(6).hex()}.db"
        self.db_url = f"sqlite:///{self.db_path}?check_same_thread=False"
        self.db = Database(self.db_url)
        self.db.create_schema()

    def tearDown(self):
        self.db.engine.dispose()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_01_patient_persistence_sqlite(self):
        """1. Patient model persists cleanly in SQLite."""
        with self.db.session() as s:
            p = Patient(
                patient_id="P_SQLITE_1",
                name="SQLite Test User",
                age=55,
                gender="male",
                phone="555-1234",
                email="sql@test.com",
                notes="Primary knee rehab",
                status="ACTIVE",
            )
            s.add(p)
            s.commit()

        # Query back using raw SQL to verify actual SQLite persistence
        with self.db.engine.connect() as conn:
            row = conn.execute(text("SELECT patient_id, name, age, status FROM patients WHERE patient_id='P_SQLITE_1'")).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "P_SQLITE_1")
            self.assertEqual(row[1], "SQLite Test User")
            self.assertEqual(row[2], 55)
            self.assertEqual(row[3], "ACTIVE")

    def test_02_patient_exercise_persistence_sqlite(self):
        """2. PatientExerciseAssignment persists cleanly in SQLite."""
        with self.db.session() as s:
            p = Patient(patient_id="P_SQLITE_2", name="Patient Two", status="ACTIVE")
            s.add(p)
            s.flush()

            a = PatientExerciseAssignment(
                patient_id="P_SQLITE_2",
                exercise_id="knee_flexion",
                side="right",
                target_rom=130.0,
                target_repetitions=10,
                sessions_per_day=3,
                notes="Post-op protocol",
                active=True,
            )
            s.add(a)
            s.commit()

        with self.db.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT patient_id, exercise_id, side, target_rom, target_repetitions, sessions_per_day, active "
                "FROM patient_exercises WHERE patient_id='P_SQLITE_2'"
            )).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "P_SQLITE_2")
            self.assertEqual(row[1], "knee_flexion")
            self.assertEqual(row[2], "right")
            self.assertEqual(row[3], 130.0)
            self.assertEqual(row[4], 10)
            self.assertEqual(row[5], 3)
            self.assertEqual(row[6], 1)

    def test_03_foreign_key_enforcement_on_assignment(self):
        """3. SQLite PRAGMA foreign_keys=ON rejects assignment with non-existent patient_id."""
        with self.assertRaises(IntegrityError):
            with self.db.session() as s:
                orphaned_assignment = PatientExerciseAssignment(
                    patient_id="NON_EXISTENT_PATIENT",
                    exercise_id="elbow_flexion",
                    side="left",
                    active=True,
                )
                s.add(orphaned_assignment)
                s.commit()

    def test_04_uniqueness_constraint_on_assignment(self):
        """4. Uniqueness constraint rejects duplicate (patient_id, exercise_id, side)."""
        with self.db.session() as s:
            p = Patient(patient_id="P_UQ", name="Unique Test", status="ACTIVE")
            s.add(p)
            s.flush()
            s.add(PatientExerciseAssignment(
                patient_id="P_UQ", exercise_id="elbow_flexion", side="left", active=True
            ))
            s.commit()

        # Second insert with identical (patient_id, exercise_id, side) must fail with IntegrityError
        with self.assertRaises(IntegrityError):
            with self.db.session() as s:
                s.add(PatientExerciseAssignment(
                    patient_id="P_UQ", exercise_id="elbow_flexion", side="left", active=True
                ))
                s.commit()

    def test_05_migration_on_legacy_db_with_sessions_and_results(self):
        """
        TEST 1 — LEGACY SESSION FOREIGN KEY:
        Verifies:
        1. patients table exists.
        2. legacy patients are backfilled.
        3. all old sessions remain.
        4. all old results remain.
        5. all old frames remain.
        6. sessions.patient_id has an actual FOREIGN KEY to patients.patient_id in SQLite schema.
        7. child foreign keys in results and frames still reference sessions.
        8. PRAGMA foreign_key_check returns zero violations.
        9. inserting a session with a nonexistent patient fails FK constraint.
        10. inserting a session with an existing patient succeeds.
        11. deleting parent patient cascades cleanly.
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        legacy_path = Path(tmp.name)
        legacy_engine = create_engine(f"sqlite:///{legacy_path.as_posix()}", future=True)

        @event.listens_for(legacy_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        try:
            # Construct legacy schema (Phase 4C/5F without patients table and without sessions FK)
            with legacy_engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE sessions (
                        session_id VARCHAR(64) PRIMARY KEY,
                        patient_id VARCHAR(64) NOT NULL,
                        exercise VARCHAR(128) NOT NULL,
                        side VARCHAR(16) NOT NULL DEFAULT 'left',
                        started_at DATETIME NOT NULL,
                        ended_at DATETIME,
                        status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id VARCHAR(64) UNIQUE NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                        exercise VARCHAR(128) NOT NULL,
                        side VARCHAR(16) NOT NULL DEFAULT 'left',
                        repetitions INTEGER NOT NULL,
                        rom_min FLOAT,
                        rom_max FLOAT,
                        rom_average FLOAT,
                        performance_score FLOAT,
                        feedback TEXT NOT NULL DEFAULT ''
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE frames (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                        frame_id INTEGER NOT NULL,
                        timestamp DATETIME NOT NULL,
                        landmarks JSON NOT NULL,
                        joint_angles JSON NOT NULL,
                        phase VARCHAR(64)
                    )
                """))
                conn.execute(text("""
                    INSERT INTO sessions (session_id, patient_id, exercise, side, started_at, status)
                    VALUES ('S-LEGACY-1', 'P_LEGACY_ALPHA', 'elbow_flexion', 'left', '2026-01-01 10:00:00', 'COMPLETED')
                """))
                conn.execute(text("""
                    INSERT INTO results (session_id, exercise, side, repetitions, rom_min, rom_max, performance_score, feedback)
                    VALUES ('S-LEGACY-1', 'elbow_flexion', 'left', 10, 30.0, 140.0, 90.0, 'Legacy test result')
                """))
                conn.execute(text("""
                    INSERT INTO frames (session_id, frame_id, timestamp, landmarks, joint_angles)
                    VALUES ('S-LEGACY-1', 1, '2026-01-01 10:00:01', '{}', '{}')
                """))

            # Verify sessions had NO foreign key to patients before migration
            with legacy_engine.connect() as conn:
                fks_before = conn.execute(text("PRAGMA foreign_key_list(sessions)")).fetchall()
                self.assertFalse(any(row[2].lower() == "patients" for row in fks_before))

            # Run SQLite migrations
            applied = run_sqlite_migrations(legacy_engine)
            self.assertTrue(applied["patients"])
            self.assertTrue(applied["patient_exercises"])
            self.assertTrue(applied["sessions"])

            with legacy_engine.connect() as conn:
                # 1. Verify patients table exists and P_LEGACY_ALPHA was backfilled
                p_row = conn.execute(text("SELECT patient_id, name, status FROM patients WHERE patient_id='P_LEGACY_ALPHA'")).fetchone()
                self.assertIsNotNone(p_row)
                self.assertEqual(p_row[0], "P_LEGACY_ALPHA")
                self.assertEqual(p_row[1], "Patient P_LEGACY_ALPHA")
                self.assertEqual(p_row[2], "ACTIVE")

                # 2. Verify historical session, result, and frame are completely preserved
                s_row = conn.execute(text("SELECT session_id, patient_id, status FROM sessions WHERE session_id='S-LEGACY-1'")).fetchone()
                self.assertIsNotNone(s_row)
                self.assertEqual(s_row[0], "S-LEGACY-1")
                self.assertEqual(s_row[1], "P_LEGACY_ALPHA")

                r_row = conn.execute(text("SELECT repetitions, performance_score FROM results WHERE session_id='S-LEGACY-1'")).fetchone()
                self.assertIsNotNone(r_row)
                self.assertEqual(r_row[0], 10)
                self.assertEqual(r_row[1], 90.0)

                f_row = conn.execute(text("SELECT frame_id FROM frames WHERE session_id='S-LEGACY-1'")).fetchone()
                self.assertIsNotNone(f_row)
                self.assertEqual(f_row[0], 1)

                # 3. Inspect actual SQLite schema: sessions.patient_id must have FOREIGN KEY to patients
                fks_after = conn.execute(text("PRAGMA foreign_key_list(sessions)")).fetchall()
                self.assertTrue(any(row[2].lower() == "patients" for row in fks_after), "sessions must have FK to patients")

                # 4. Results and frames foreign keys still reference sessions
                r_fks = conn.execute(text("PRAGMA foreign_key_list(results)")).fetchall()
                f_fks = conn.execute(text("PRAGMA foreign_key_list(frames)")).fetchall()
                self.assertTrue(any(row[2].lower() == "sessions" for row in r_fks))
                self.assertTrue(any(row[2].lower() == "sessions" for row in f_fks))

                # 5. PRAGMA foreign_key_check returns zero violations
                violations = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
                self.assertEqual(len(violations), 0, f"Expected 0 violations, got: {violations}")

            # 6. Inserting a session with a nonexistent patient now fails under PRAGMA foreign_keys=ON
            with self.assertRaises(Exception) as ctx:
                with legacy_engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO sessions (session_id, patient_id, exercise, side, started_at, status)
                        VALUES ('S-FAIL-FK', 'P_NONEXISTENT_999', 'elbow_flexion', 'left', '2026-01-01', 'ACTIVE')
                    """))
            self.assertIn("foreign key", str(ctx.exception).lower())

            # 7. Inserting a session with an existing patient succeeds
            with legacy_engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO sessions (session_id, patient_id, exercise, side, started_at, status)
                    VALUES ('S-VALID-2', 'P_LEGACY_ALPHA', 'elbow_flexion', 'left', '2026-01-01', 'ACTIVE')
                """))
                valid_count = conn.execute(text("SELECT count(*) FROM sessions WHERE session_id='S-VALID-2'")).scalar()
                self.assertEqual(valid_count, 1)

            # 8. Deleting parent patient cascades cleanly
            with legacy_engine.begin() as conn:
                conn.execute(text("DELETE FROM patients WHERE patient_id='P_LEGACY_ALPHA'"))
                sess_left = conn.execute(text("SELECT count(*) FROM sessions WHERE patient_id='P_LEGACY_ALPHA'")).scalar()
                res_left = conn.execute(text("SELECT count(*) FROM results WHERE session_id='S-LEGACY-1'")).scalar()
                frames_left = conn.execute(text("SELECT count(*) FROM frames WHERE session_id='S-LEGACY-1'")).scalar()
                self.assertEqual(sess_left, 0)
                self.assertEqual(res_left, 0)
                self.assertEqual(frames_left, 0)

        finally:
            legacy_engine.dispose()
            if legacy_path.exists():
                try:
                    legacy_path.unlink()
                except OSError:
                    pass

    def test_07_migration_idempotency_comprehensive(self):
        """
        MIGRATION IDEMPOTENCY:
        Run migration twice on the same legacy database.
        The second run must not duplicate patients, sessions, results, or assignments,
        and must not rebuild or corrupt data unnecessarily.
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        legacy_path = Path(tmp.name)
        legacy_engine = create_engine(f"sqlite:///{legacy_path.as_posix()}", future=True)

        try:
            with legacy_engine.begin() as conn:
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
                    CREATE TABLE results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id VARCHAR(64) UNIQUE NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                        exercise VARCHAR(128) NOT NULL,
                        repetitions INTEGER NOT NULL,
                        performance_score FLOAT
                    )
                """))
                conn.execute(text("INSERT INTO sessions VALUES ('S1', 'P1', 'elbow_flexion', '2026-01-01', NULL, 'COMPLETED')"))
                conn.execute(text("INSERT INTO results (session_id, exercise, repetitions, performance_score) VALUES ('S1', 'elbow_flexion', 8, 88.0)"))

            # First run: applies migrations
            run1 = run_sqlite_migrations(legacy_engine)
            self.assertTrue(run1["patients"])
            self.assertTrue(run1["sessions"])

            # Snapshot counts after first run
            with legacy_engine.connect() as conn:
                p_cnt1 = conn.execute(text("SELECT count(*) FROM patients")).scalar()
                s_cnt1 = conn.execute(text("SELECT count(*) FROM sessions")).scalar()
                r_cnt1 = conn.execute(text("SELECT count(*) FROM results")).scalar()
                v_cnt1 = conn.execute(text("PRAGMA foreign_key_check")).fetchall()

            self.assertEqual(p_cnt1, 1)
            self.assertEqual(s_cnt1, 1)
            self.assertEqual(r_cnt1, 1)
            self.assertEqual(len(v_cnt1), 0)

            # Second run: must be completely no-op (idempotent)
            run2 = run_sqlite_migrations(legacy_engine)
            self.assertFalse(run2["patients"])
            self.assertFalse(run2["sessions"])
            self.assertFalse(run2["results"])
            self.assertFalse(run2["patient_exercises"])

            # Snapshot counts after second run: must match identically
            with legacy_engine.connect() as conn:
                p_cnt2 = conn.execute(text("SELECT count(*) FROM patients")).scalar()
                s_cnt2 = conn.execute(text("SELECT count(*) FROM sessions")).scalar()
                r_cnt2 = conn.execute(text("SELECT count(*) FROM results")).scalar()
                v_cnt2 = conn.execute(text("PRAGMA foreign_key_check")).fetchall()

            self.assertEqual(p_cnt2, p_cnt1)
            self.assertEqual(s_cnt2, s_cnt1)
            self.assertEqual(r_cnt2, r_cnt1)
            self.assertEqual(len(v_cnt2), 0)

        finally:
            legacy_engine.dispose()
            if legacy_path.exists():
                try:
                    legacy_path.unlink()
                except OSError:
                    pass

    def test_06_restart_durability(self):
        """6. Application restart durability: dispose engine, reconnect, verify data survives."""
        # 1. Create patient and assignment
        patient_repo1 = SQLAlchemyPatientRepository(self.db)
        assign_repo1 = SQLAlchemyAssignmentRepository(self.db)
        sess_repo1 = SQLAlchemySessionRepository(self.db)
        res_repo1 = SQLAlchemyResultRepository(self.db)

        p = patient_repo1.create_patient({
            "patient_id": "P_DURABLE_6",
            "name": "Durable Patient",
            "age": 48,
            "status": "ACTIVE"
        })
        a = assign_repo1.assign_exercise({
            "patient_id": "P_DURABLE_6",
            "exercise_id": "elbow_flexion",
            "side": "right",
            "target_rom": 145.0,
            "target_repetitions": 12,
            "sessions_per_day": 2,
            "notes": "Durable notes",
            "active": True
        })
        sid = sess_repo1.start_session("P_DURABLE_6", "elbow_flexion", side="right")
        res_repo1.record_result(
            session_id=sid,
            repetitions=12,
            rom_min=35.0,
            rom_max=145.0,
            rom_average=90.0,
            performance_score=95.0,
            feedback="Excellent session"
        )
        sess_repo1.end_session(sid)

        # 2. Dispose engine (simulate application restart)
        self.db.engine.dispose()

        # 3. Create fresh Database instance pointing to the exact same file
        db2 = Database(self.db_url)
        db2.create_schema()
        patient_repo2 = SQLAlchemyPatientRepository(db2)
        assign_repo2 = SQLAlchemyAssignmentRepository(db2)

        # 4. Verify patient survived
        p_reloaded = patient_repo2.get_patient("P_DURABLE_6")
        self.assertIsNotNone(p_reloaded)
        self.assertEqual(p_reloaded["name"], "Durable Patient")
        self.assertEqual(p_reloaded["age"], 48)

        # 5. Verify assignment survived
        assignments = assign_repo2.list_assignments("P_DURABLE_6")
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]["exercise_id"], "elbow_flexion")
        self.assertEqual(assignments[0]["side"], "right")
        self.assertEqual(assignments[0]["target_rom"], 145.0)

        # 6. Verify dashboard stats survived
        overview = patient_repo2.get_system_overview()
        self.assertGreaterEqual(overview["total_patients"], 1)
        self.assertGreaterEqual(overview["total_sessions"], 1)
        self.assertEqual(overview["average_performance_score"], 95.0)

        db2.engine.dispose()
