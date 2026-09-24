"""
backend/tests/test_sqlite_pragmas.py

Verifies SQLite connection behavior, foreign key constraint enforcement,
and migration durability.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from digital_thread.db import Database
from digital_thread.models import Patient, Session, Frame, Result, utc_now


def test_sqlite_foreign_keys_pragma_enabled(tmp_path):
    """Verify that PRAGMA foreign_keys is 1 on every SQLite connection."""
    db_file = tmp_path / "pragma_test.db"
    db = Database(f"sqlite:///{db_file}")
    db.create_schema()

    with db.session() as session:
        result = session.execute(text("PRAGMA foreign_keys")).scalar()
        assert result == 1


def test_frame_foreign_key_violation_raises_integrity_error(tmp_path):
    """Verify that inserting a Frame with an invalid session_id fails with IntegrityError."""
    db_file = tmp_path / "fk_frame_test.db"
    db = Database(f"sqlite:///{db_file}")
    db.create_schema()

    with pytest.raises(IntegrityError):
        with db.session() as session:
            session.add(Frame(
                session_id="NON_EXISTENT_SESSION",
                frame_id=1,
                timestamp=utc_now(),
                landmarks={"NOSE": {"x": 0.5, "y": 0.5, "visibility": 0.9}},
                joint_angles={"left_elbow": 90.0},
                phase="FLEXED",
            ))
            session.commit()


def test_result_foreign_key_violation_raises_integrity_error(tmp_path):
    """Verify that inserting a Result with an invalid session_id fails with IntegrityError."""
    db_file = tmp_path / "fk_result_test.db"
    db = Database(f"sqlite:///{db_file}")
    db.create_schema()

    with pytest.raises(IntegrityError):
        with db.session() as session:
            session.add(Result(
                session_id="NON_EXISTENT_SESSION",
                exercise="elbow_flexion",
                side="left",
                repetitions=5,
                rom_min=45.0,
                rom_max=140.0,
                rom_average=92.5,
                performance_score=85.0,
                feedback="Good work",
            ))
            session.commit()


def test_valid_parent_and_children_persist_successfully(tmp_path):
    """Verify that valid sessions, frames, and results succeed with foreign keys active."""
    db_file = tmp_path / "valid_test.db"
    db = Database(f"sqlite:///{db_file}")
    db.create_schema()

    with db.session() as session:
        session.add(Patient(patient_id="P001", name="Patient P001", status="ACTIVE"))
        sess = Session(
            session_id="VALID-S001",
            patient_id="P001",
            exercise="elbow_flexion",
            side="left",
            started_at=utc_now(),
            status="ACTIVE",
        )
        session.add(sess)
        session.commit()

    with db.session() as session:
        session.add(Frame(
            session_id="VALID-S001",
            frame_id=1,
            timestamp=utc_now(),
            landmarks={"NOSE": {"x": 0.5, "y": 0.5, "visibility": 0.9}},
            joint_angles={"left_elbow": 90.0},
            phase="FLEXED",
        ))
        session.add(Result(
            session_id="VALID-S001",
            exercise="elbow_flexion",
            side="left",
            repetitions=10,
            rom_min=50.0,
            rom_max=145.0,
            rom_average=97.5,
            performance_score=90.0,
            feedback="Excellent session",
        ))
        session.commit()

    with db.session() as session:
        s = session.get(Session, "VALID-S001")
        assert s is not None
        assert len(s.frames) == 1
        assert len(s.results) == 1
        assert s.results[0].performance_score == 90.0


def test_schema_and_migration_intact_with_pragmas(tmp_path):
    """Verify that run_sqlite_migrations executes without error on engine with foreign_keys=ON."""
    db_file = tmp_path / "migration_test.db"
    db = Database(f"sqlite:///{db_file}")
    db.create_schema()

    # Re-running migrations should be idempotent and succeed
    from digital_thread.migration import run_sqlite_migrations
    applied = run_sqlite_migrations(db.engine)
    assert isinstance(applied, dict)
    assert applied["sessions"] is False  # already present
    assert applied["results"] is False   # already present
