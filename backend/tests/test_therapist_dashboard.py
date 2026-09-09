"""
Unit and integration tests for Phase 5E — Therapist Dashboard.

Validates:
1. Patient list derived strictly from real sessions.
2. Patient isolation (Patient A's sessions never appear in Patient B's history).
3. Active patient count accurately counts distinct patients with status == 'ACTIVE'.
4. Active patient count is 0 when all sessions are COMPLETED.
5. Average performance score calculation (strictly completed sessions with persisted results).
6. ACTIVE sessions excluded from average score.
7. COMPLETED sessions included in average score.
8. Bilateral side propagation (session.side and result.side for left and right).
9. Exercise isolation (different exercises remain distinct).
10. Sessions without Result handled cleanly without crashing.
11. Completed sessions with Result return full metric fields.
12. Newest-first ordering (started_at DESC contract).
13. Result field integrity (repetitions, rom_min, rom_max, rom_average, score, feedback).
14. Empty patient database returns 0 count and empty list.
15. Legacy session side fallback to 'left'.
16. Total session count calculation.
17. System average score excludes ACTIVE / no-result sessions.
18. No duplicate score contribution from repository joins.
19. Full REST API integration through TestClient for GET /api/patients and GET /api/patients/{id}/sessions.
"""
import os
import tempfile
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from digital_thread.db import Database
from digital_thread.models import Session, Result
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from backend.services.patient_service import PatientService
from backend.services.session_service import SessionService
from backend.core.dependencies import (
    get_database,
    get_patient_repo,
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
)
from backend.main import app


@pytest.fixture
def file_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_url = f"sqlite:///{tmp.name}?check_same_thread=False"
    db = Database(db_url)
    db.create_schema()
    yield db
    db.engine.dispose()
    try:
        os.remove(tmp.name)
    except OSError:
        pass


@pytest.fixture
def repos(file_db):
    return {
        "db": file_db,
        "patient_repo": SQLAlchemyPatientRepository(file_db),
        "session_repo": SQLAlchemySessionRepository(file_db),
        "telemetry_repo": SQLAlchemyTelemetryRepository(file_db),
        "result_repo": SQLAlchemyResultRepository(file_db),
    }


@pytest.fixture
def client(repos):
    app.dependency_overrides[get_database] = lambda: repos["db"]
    app.dependency_overrides[get_patient_repo] = lambda: repos["patient_repo"]
    app.dependency_overrides[get_session_repo] = lambda: repos["session_repo"]
    app.dependency_overrides[get_telemetry_repo] = lambda: repos["telemetry_repo"]
    app.dependency_overrides[get_result_repo] = lambda: repos["result_repo"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_empty_patient_database(repos, client):
    """Empty database returns 0 totals and empty list cleanly."""
    patient_service = PatientService(repos["patient_repo"])
    res = patient_service.list_patients()
    assert res.total_patients == 0
    assert res.total_sessions == 0
    assert res.active_patients == 0
    assert res.average_performance_score is None
    assert len(res.patients) == 0

    api_res = client.get("/api/patients")
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["total_patients"] == 0
    assert data["total_sessions"] == 0
    assert data["active_patients"] == 0
    assert data["average_performance_score"] is None
    assert data["patients"] == []


def test_patient_list_derived_from_real_sessions(repos, client):
    """Patients appear in list only when sessions exist."""
    session_repo = repos["session_repo"]
    session_repo.start_session(patient_id="P1", exercise="elbow_flexion", side="left")
    session_repo.start_session(patient_id="P2", exercise="shoulder_abduction", side="right")

    api_res = client.get("/api/patients")
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["total_patients"] == 2
    assert data["total_sessions"] == 2
    patient_ids = [p["patient_id"] for p in data["patients"]]
    assert "P1" in patient_ids
    assert "P2" in patient_ids


def test_patient_isolation(repos, client):
    """Patient A's sessions never appear in Patient B's history."""
    session_repo = repos["session_repo"]
    s_a1 = session_repo.start_session(patient_id="PAT_A", exercise="elbow_flexion", side="left")
    s_a2 = session_repo.start_session(patient_id="PAT_A", exercise="shoulder_flexion", side="right")
    s_b1 = session_repo.start_session(patient_id="PAT_B", exercise="knee_flexion", side="left")

    res_a = client.get("/api/patients/PAT_A/sessions").json()
    res_b = client.get("/api/patients/PAT_B/sessions").json()

    assert res_a["total_sessions"] == 2
    assert all(s["patient_id"] == "PAT_A" for s in res_a["sessions"])
    assert res_b["total_sessions"] == 1
    assert all(s["patient_id"] == "PAT_B" for s in res_b["sessions"])


def test_active_patients_count_and_zero_when_none_active(repos, client):
    """
    Active Patients count:
    - distinct patients with at least one session with status == 'ACTIVE'
    - 0 when all sessions are COMPLETED
    - a patient with multiple ACTIVE sessions is counted only ONCE.
    """
    session_repo = repos["session_repo"]
    result_repo = repos["result_repo"]

    # P1 has 2 ACTIVE sessions
    s1 = session_repo.start_session(patient_id="P1", exercise="elbow_flexion", side="left")
    s2 = session_repo.start_session(patient_id="P1", exercise="shoulder_flexion", side="right")
    # P2 has 1 ACTIVE session
    s3 = session_repo.start_session(patient_id="P2", exercise="knee_flexion", side="left")
    # P3 has 1 COMPLETED session with result
    s4 = session_repo.start_session(patient_id="P3", exercise="elbow_flexion", side="right")
    result_repo.record_result(s4, repetitions=5, rom_min=40.0, rom_max=140.0, rom_average=90.0, performance_score=80.0)
    session_repo.end_session(s4)

    res = client.get("/api/patients").json()
    assert res["total_patients"] == 3
    assert res["total_sessions"] == 4
    # P1 (active), P2 (active), P3 (completed only) -> 2 active patients
    assert res["active_patients"] == 2

    # Now complete P1's and P2's sessions
    for sid in [s1, s2, s3]:
        result_repo.record_result(sid, repetitions=1, rom_min=10.0, rom_max=50.0, rom_average=30.0, performance_score=50.0)
        session_repo.end_session(sid)

    res_all_done = client.get("/api/patients").json()
    assert res_all_done["active_patients"] == 0


def test_average_performance_score_excludes_active_and_no_result(repos, client):
    """
    Average performance score:
    - mean of persisted performance_score values from completed sessions that have a valid persisted Result.
    - ACTIVE sessions do NOT contribute.
    - Completed sessions without Results do NOT contribute.
    - No duplicate score contributions from joins.
    """
    session_repo = repos["session_repo"]
    result_repo = repos["result_repo"]

    # Session 1: P1, COMPLETED, score = 80.0
    s1 = session_repo.start_session(patient_id="P1", exercise="elbow_flexion", side="left")
    result_repo.record_result(s1, repetitions=10, rom_min=30.0, rom_max=160.0, rom_average=95.0, performance_score=80.0)
    session_repo.end_session(s1)

    # Session 2: P1, COMPLETED, score = 90.0
    s2 = session_repo.start_session(patient_id="P1", exercise="elbow_flexion", side="left")
    result_repo.record_result(s2, repetitions=10, rom_min=30.0, rom_max=160.0, rom_average=95.0, performance_score=90.0)
    session_repo.end_session(s2)

    # Session 3: P2, ACTIVE, has no result
    s3 = session_repo.start_session(patient_id="P2", exercise="shoulder_flexion", side="right")

    # Session 4: P2, COMPLETED without a result (aborted legacy session)
    s4 = session_repo.start_session(patient_id="P2", exercise="knee_flexion", side="left")
    session_repo.end_session(s4)

    # System average should be (80.0 + 90.0) / 2 = 85.0
    res = client.get("/api/patients").json()
    assert res["average_performance_score"] == 85.0

    # Per-patient averages
    p1 = next(p for p in res["patients"] if p["patient_id"] == "P1")
    assert p1["average_performance_score"] == 85.0
    assert p1["completed_sessions"] == 2
    assert p1["active_sessions"] == 0

    p2 = next(p for p in res["patients"] if p["patient_id"] == "P2")
    assert p2["average_performance_score"] is None
    assert p2["completed_sessions"] == 1
    assert p2["active_sessions"] == 1


def test_bilateral_side_propagation(repos, client):
    """
    Sessions and Results correctly preserve and propagate 'left' and 'right' side.
    API returns side on session and on results list.
    """
    session_repo = repos["session_repo"]
    result_repo = repos["result_repo"]

    # Left session
    s_left = session_repo.start_session(patient_id="PBilateral", exercise="elbow_flexion", side="left")
    result_repo.record_result(s_left, repetitions=5, rom_min=20.0, rom_max=140.0, rom_average=80.0, performance_score=85.0)
    session_repo.end_session(s_left)

    # Right session
    s_right = session_repo.start_session(patient_id="PBilateral", exercise="elbow_flexion", side="right")
    result_repo.record_result(s_right, repetitions=8, rom_min=25.0, rom_max=145.0, rom_average=85.0, performance_score=92.0)
    session_repo.end_session(s_right)

    history = client.get("/api/patients/PBilateral/sessions").json()
    assert history["total_sessions"] == 2

    session_map = {s["session_id"]: s for s in history["sessions"]}
    assert session_map[s_left]["side"] == "left"
    assert session_map[s_left]["results"][0]["side"] == "left"
    assert session_map[s_right]["side"] == "right"
    assert session_map[s_right]["results"][0]["side"] == "right"


def test_newest_first_ordering(repos, client):
    """
    Sessions must be returned in descending started_at order (newest first).
    """
    session_repo = repos["session_repo"]
    s1 = session_repo.start_session(patient_id="POrder", exercise="elbow_flexion", side="left")
    s2 = session_repo.start_session(patient_id="POrder", exercise="shoulder_flexion", side="right")
    s3 = session_repo.start_session(patient_id="POrder", exercise="knee_flexion", side="left")

    history = client.get("/api/patients/POrder/sessions").json()
    session_ids = [s["session_id"] for s in history["sessions"]]
    # s3 was started last, so it should be first
    assert session_ids == [s3, s2, s1]


def test_session_fields_and_result_integrity(repos, client):
    """
    Validates all session fields (started_at, ended_at, status, side, exercise)
    and result fields (repetitions, rom_min, rom_max, rom_average, score, feedback).
    """
    session_repo = repos["session_repo"]
    result_repo = repos["result_repo"]

    sid = session_repo.start_session(patient_id="PIntegrity", exercise="shoulder_abduction", side="right")
    result_repo.record_result(
        sid,
        repetitions=12,
        rom_min=15.0,
        rom_max=165.0,
        rom_average=90.0,
        performance_score=96.5,
        feedback="Excellent abduction range"
    )
    session_repo.end_session(sid)

    history = client.get("/api/patients/PIntegrity/sessions").json()
    assert len(history["sessions"]) == 1
    sess = history["sessions"][0]

    assert sess["session_id"] == sid
    assert sess["patient_id"] == "PIntegrity"
    assert sess["exercise"] == "shoulder_abduction"
    assert sess["side"] == "right"
    assert sess["status"] == "COMPLETED"
    assert sess["started_at"] is not None
    assert sess["ended_at"] is not None

    res = sess["results"][0]
    assert res["repetitions"] == 12
    assert res["side"] == "right"
    assert res["rom_min"] == 15.0
    assert res["rom_max"] == 165.0
    assert res["rom_average"] == 90.0
    assert res["performance_score"] == 96.5
    assert res["feedback"] == "Excellent abduction range"


def test_legacy_session_defaults_to_left(repos, client):
    """
    Legacy database row where side is None/empty defaults safely to 'left'.
    """
    db = repos["db"]
    with db.session() as s:
        legacy_sess = Session(
            session_id="S-LEGACY",
            patient_id="PLegacy",
            exercise="elbow_flexion",
            side=None,  # simulating unmigrated/legacy record
            started_at=datetime.now(timezone.utc),
            status="COMPLETED"
        )
        s.add(legacy_sess)
        s.commit()

    history = client.get("/api/patients/PLegacy/sessions").json()
    assert len(history["sessions"]) == 1
    assert history["sessions"][0]["side"] == "left"
