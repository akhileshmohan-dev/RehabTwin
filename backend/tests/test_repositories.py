import pytest
import os
from digital_thread.db import Database
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from digital_thread.models import Result, Patient


@pytest.fixture
def db():
    # Use an in-memory test database to avoid Windows file locks
    db_url = "sqlite:///:memory:"
    database = Database(db_url)
    database.create_schema()
    with database.session() as s:
        s.add(Patient(patient_id="P123", name="Patient P123", status="ACTIVE"))
        s.commit()
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
    
    with db.session() as s:
        s.add(Patient(patient_id="PATIENT_A", name="Patient PATIENT_A", status="ACTIVE"))
        s.add(Patient(patient_id="PATIENT_B", name="Patient PATIENT_B", status="ACTIVE"))
        s.commit()
    
    session_repo.start_session("PATIENT_A", "Exercise 1")
    session_repo.start_session("PATIENT_A", "Exercise 2")
    session_repo.start_session("PATIENT_B", "Exercise 1")
    
    patients = [p for p in patient_repo.list_patients() if p["patient_id"] in ("PATIENT_A", "PATIENT_B")]
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


from sqlalchemy.exc import IntegrityError

def test_database_enforces_unique_result(db):
    session_repo = SQLAlchemySessionRepository(db)
    sid = session_repo.start_session("P123", "Squats")
    
    with db.session() as session:
        # Insert first result directly
        r1 = Result(
            session_id=sid, exercise="Squats", repetitions=10, 
            rom_min=10.0, rom_max=100.0, rom_average=50.0, performance_score=80.0
        )
        session.add(r1)
        session.commit()
        
        # Attempt to insert second result directly for the same session
        r2 = Result(
            session_id=sid, exercise="Squats", repetitions=15, 
            rom_min=10.0, rom_max=100.0, rom_average=50.0, performance_score=85.0
        )
        session.add(r2)
        
        with pytest.raises(IntegrityError):
            session.commit()
            
        session.rollback()
        
        # Assert exactly one result remains
        count = session.query(Result).filter_by(session_id=sid).count()
        assert count == 1


import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_concurrent_result_idempotency():
    # Use a file-backed temp DB to avoid SQLite in-memory thread isolation artifacts
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Create database with check_same_thread=False for ThreadPoolExecutor
        db_url = f"sqlite:///{db_path}?check_same_thread=False"
        database = Database(db_url)
        database.create_schema()
        with database.session() as s:
            s.add(Patient(patient_id="P999", name="Patient P999", status="ACTIVE"))
            s.commit()
        
        session_repo = SQLAlchemySessionRepository(database)
        result_repo = SQLAlchemyResultRepository(database)
        
        sid = session_repo.start_session("P999", "Concurrency Test")
        
        def record_fn(rep):
            # Each thread uses its own session under the hood (SessionLocal)
            result_repo.record_result(sid, rep, 10.0, 100.0, 50.0, float(rep))
            return True

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(record_fn, i) for i in range(1, 6)]
            
            # Ensure no exceptions leaked
            for future in as_completed(futures):
                assert future.result() is True
                
        # Assert exactly one result row exists after concurrent races
        with database.session() as session:
            count = session.query(Result).filter_by(session_id=sid).count()
            assert count == 1
    finally:
        database.engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)
