import pytest
import os
from digital_thread.db import Database
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from digital_thread.models import Result


@pytest.fixture
def db():
    # Use an in-memory test database to avoid Windows file locks
    db_url = "sqlite:///:memory:"
    database = Database(db_url)
    database.create_schema()
    yield database
    database.engine.dispose()


def test_session_creation_and_retrieval(db):
    session_repo = SQLAlchemySessionRepository(db)
    
    sid = session_repo.start_session("P123", "Bicep Curls")
    assert sid is not None
    
    session = session_repo.get_session(sid)
    assert session["patient_id"] == "P123"
    assert session["exercise"] == "Bicep Curls"
    assert session["status"] == "ACTIVE"
    
    session_repo.end_session(sid)
    ended_session = session_repo.get_session(sid)
    assert ended_session["status"] == "COMPLETED"


def test_patient_repository_isolation(db):
    session_repo = SQLAlchemySessionRepository(db)
    patient_repo = SQLAlchemyPatientRepository(db)
    
    session_repo.start_session("PATIENT_A", "Exercise 1")
    session_repo.start_session("PATIENT_A", "Exercise 2")
    session_repo.start_session("PATIENT_B", "Exercise 1")
    
    patients = patient_repo.list_patients()
    assert len(patients) == 2
    
    patient_a = next(p for p in patients if p["patient_id"] == "PATIENT_A")
    assert patient_a["total_sessions"] == 2
    
    history_a = patient_repo.get_patient_history("PATIENT_A")
    assert len(history_a) == 2
    assert all(s["patient_id"] == "PATIENT_A" for s in history_a)


def test_telemetry_insertion(db):
    session_repo = SQLAlchemySessionRepository(db)
    telemetry_repo = SQLAlchemyTelemetryRepository(db)
    
    sid = session_repo.start_session("P123", "Bicep Curls")
    telemetry_repo.record_frame(sid, 1, {"x": 1}, {"left_elbow": 90.0}, "UP")
    
    # We can check export to see if it was inserted
    export = session_repo.export_session(sid, "test_export.json")
    import json
    with open(export, "r") as f:
        data = json.load(f)
    assert len(data["frames"]) == 1
    assert data["frames"][0]["frame_id"] == 1


def test_result_idempotency(db):
    session_repo = SQLAlchemySessionRepository(db)
    result_repo = SQLAlchemyResultRepository(db)
    
    sid = session_repo.start_session("P123", "Bicep Curls")
    
    # First call
    result_repo.record_result(sid, 10, 10.0, 140.0, 75.0, 95.0, "Good job")
    
    # Second call (idempotent update)
    result_repo.record_result(sid, 12, 10.0, 145.0, 75.0, 98.0, "Great job")
    
    result = result_repo.get_result(sid)
    assert result["repetitions"] == 12
    assert result["performance_score"] == 98.0
    
    # Assert only 1 row exists
    with db.session() as session:
        results = session.query(Result).filter_by(session_id=sid).all()
        assert len(results) == 1
