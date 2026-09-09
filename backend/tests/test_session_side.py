"""
Tests for session side handling and validation in Phase 5A.
Validates:
- New left session creation
- New right session creation
- Case-insensitive side normalization
- Invalid side rejected with HTTP 400
- Old/legacy sessions default to 'left'
- Session repository and result repository side persistence
- Export session includes side
"""
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from digital_thread.db import Database
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemySessionRepository,
    SQLAlchemyPatientRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from backend.services.session_service import SessionService, InvalidSideException
from backend.schemas.session import StartSessionRequest
from backend.core.dependencies import (
    get_database,
    get_session_repo,
    get_patient_repo,
    get_telemetry_repo,
    get_result_repo,
)
from backend.main import app


def _make_file_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_url = f"sqlite:///{tmp.name}?check_same_thread=False"
    db = Database(db_url)
    db.create_schema()
    db._test_path = tmp.name
    return db


def _cleanup_db(db):
    db.engine.dispose()
    try:
        os.remove(db._test_path)
    except OSError:
        pass


class TestSessionSide(unittest.TestCase):
    def setUp(self):
        self.db = _make_file_db()
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.patient_repo = SQLAlchemyPatientRepository(self.db)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)

        self.service = SessionService(
            session_repo=self.session_repo,
            telemetry_repo=self.telemetry_repo,
            result_repo=self.result_repo,
        )

        # Override dependencies for FastAPI TestClient
        app.dependency_overrides[get_database] = lambda: self.db
        app.dependency_overrides[get_session_repo] = lambda: self.session_repo
        app.dependency_overrides[get_patient_repo] = lambda: self.patient_repo
        app.dependency_overrides[get_telemetry_repo] = lambda: self.telemetry_repo
        app.dependency_overrides[get_result_repo] = lambda: self.result_repo

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        _cleanup_db(self.db)

    def test_start_session_default_left(self):
        req = StartSessionRequest(patient_id="P1", exercise="elbow_flexion")
        res = self.service.start_session(req)
        self.assertEqual(res.side, "left")

        session_data = self.session_repo.get_session(res.session_id)
        self.assertEqual(session_data["side"], "left")

    def test_start_session_explicit_right(self):
        req = StartSessionRequest(patient_id="P1", exercise="knee_flexion", side="right")
        res = self.service.start_session(req)
        self.assertEqual(res.side, "right")

        session_data = self.session_repo.get_session(res.session_id)
        self.assertEqual(session_data["side"], "right")

    def test_start_session_case_insensitive(self):
        req1 = StartSessionRequest(patient_id="P1", exercise="shoulder_flexion", side="Right")
        res1 = self.service.start_session(req1)
        self.assertEqual(res1.side, "right")

        req2 = StartSessionRequest(patient_id="P1", exercise="shoulder_abduction", side=" LEFT ")
        res2 = self.service.start_session(req2)
        self.assertEqual(res2.side, "left")

    def test_start_session_invalid_side_raises_exception(self):
        with self.assertRaises(InvalidSideException):
            self.service.start_session(
                StartSessionRequest(patient_id="P1", exercise="elbow_flexion", side="middle")
            )

    def test_api_start_session_left_and_right(self):
        # Left
        resp_left = self.client.post("/api/sessions", json={
            "patient_id": "P-API",
            "exercise": "elbow_flexion",
            "side": "left"
        })
        self.assertEqual(resp_left.status_code, 201)
        data_left = resp_left.json()
        self.assertEqual(data_left["side"], "left")

        # Right
        resp_right = self.client.post("/api/sessions", json={
            "patient_id": "P-API",
            "exercise": "elbow_flexion",
            "side": "right"
        })
        self.assertEqual(resp_right.status_code, 201)
        data_right = resp_right.json()
        self.assertEqual(data_right["side"], "right")

    def test_api_start_session_case_insensitive_normalized(self):
        resp = self.client.post("/api/sessions", json={
            "patient_id": "P-API",
            "exercise": "knee_flexion",
            "side": "  RIGHT  "
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["side"], "right")

    def test_api_start_session_invalid_side_returns_400(self):
        resp = self.client.post("/api/sessions", json={
            "patient_id": "P-API",
            "exercise": "elbow_flexion",
            "side": "both"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid side 'both'", resp.json()["detail"])

    def test_result_persistence_inherits_session_side(self):
        sid = self.session_repo.start_session(patient_id="P-RES", exercise="elbow_flexion", side="right")
        self.result_repo.record_result(
            session_id=sid,
            repetitions=5,
            rom_min=45.0,
            rom_max=140.0,
            rom_average=92.5,
            performance_score=85.0,
            feedback="Great work",
        )
        res = self.result_repo.get_result(sid)
        self.assertIsNotNone(res)
        self.assertEqual(res["side"], "right")

    def test_patient_history_and_export_includes_side(self):
        sid = self.session_repo.start_session(patient_id="P-HIST", exercise="shoulder_flexion", side="right")
        self.result_repo.record_result(
            session_id=sid,
            repetitions=8,
            rom_min=30.0,
            rom_max=150.0,
            rom_average=90.0,
            performance_score=90.0,
            feedback="Solid form",
        )

        history = self.patient_repo.get_patient_history("P-HIST")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["side"], "right")
        self.assertEqual(history[0]["results"][0]["side"], "right")

        resp = self.client.get(f"/api/sessions/{sid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["side"], "right")


if __name__ == "__main__":
    unittest.main()
