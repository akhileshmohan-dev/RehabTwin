"""
Unit tests for RehabTwin FastAPI backend API layer.
Uses standard library unittest and temporary in-memory database isolation.
"""
import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone

import mediapipe as mp
import types
if not hasattr(mp, "solutions"):
    mp.solutions = types.SimpleNamespace()
    mp.solutions.pose = types.SimpleNamespace()
    mp.solutions.pose.Pose = lambda *a, **k: MagicMock()
    mp.solutions.pose.PoseLandmark = types.SimpleNamespace()

from digital_thread.thread import DigitalThread
from backend.core.dependencies import set_digital_thread_instance, get_digital_thread
from backend.schemas.session import (
    StartSessionRequest,
    RecordFrameRequest,
    RecordResultRequest
)
from backend.services.session_service import SessionService, SessionNotFoundException
from backend.services.patient_service import PatientService
from backend.services.rehab_service import RehabService
from backend.schemas.analysis import ProcessFrameRequest
from backend.main import root, health_check


from digital_thread.db import Database
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemySessionRepository,
    SQLAlchemyPatientRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)

class TestHealthEndpoints(unittest.TestCase):
    """Test root and health check endpoints."""

    def test_root_endpoint(self):
        res = root()
        self.assertEqual(res["status"], "running")
        self.assertEqual(res["service"], "RehabTwin API")

    def test_health_endpoint(self):
        res = health_check()
        self.assertEqual(res["status"], "healthy")


class TestSessionService(unittest.TestCase):
    """Test session creation, retrieval, frame recording, ending, and 404 handling."""

    def setUp(self):
        # Use an in-memory SQLite database for isolated test execution
        self.db = Database("sqlite:///:memory:")
        self.db.create_schema()
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)
        self.service = SessionService(
            session_repo=self.session_repo,
            telemetry_repo=self.telemetry_repo,
            result_repo=self.result_repo
        )

    def test_start_and_get_session(self):
        req = StartSessionRequest(patient_id="PATIENT-TEST", exercise="elbow_flexion")
        start_res = self.service.start_session(req)
        
        self.assertIsNotNone(start_res.session_id)
        self.assertEqual(start_res.patient_id, "PATIENT-TEST")
        self.assertEqual(start_res.exercise, "elbow_flexion")
        self.assertEqual(start_res.status, "ACTIVE")

        # Get session
        get_res = self.service.get_session(start_res.session_id)
        self.assertEqual(get_res.session_id, start_res.session_id)
        self.assertEqual(get_res.status, "ACTIVE")

    def test_get_nonexistent_session_raises_404(self):
        with self.assertRaises(SessionNotFoundException):
            self.service.get_session("NONEXISTENT-ID")

    def test_record_frame_and_end_session(self):
        start_res = self.service.start_session(
            StartSessionRequest(patient_id="PATIENT-001", exercise="elbow_flexion")
        )
        sid = start_res.session_id

        # Record Frame
        frame_req = RecordFrameRequest(
            frame_id=1,
            landmarks={"LEFT_ELBOW": {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}},
            joint_angles={"left_elbow": 120.0},
            phase="EXTENDED"
        )
        frame_res = self.service.record_frame(sid, frame_req)
        self.assertEqual(frame_res.frame_id, 1)

        # Record Result
        result_req = RecordResultRequest(
            repetitions=5,
            rom_min=45.0,
            rom_max=165.0,
            rom_average=120.0,
            performance_score=95.0,
            feedback="Good form"
        )
        res_res = self.service.record_result(sid, result_req)
        self.assertEqual(res_res.session_id, sid)

        # End Session
        end_res = self.service.end_session(sid)
        self.assertEqual(end_res.status, "COMPLETED")

        # Verify status update
        session_data = self.service.get_session(sid)
        self.assertEqual(session_data.status, "COMPLETED")
        self.assertIsNotNone(session_data.ended_at)


class TestPatientService(unittest.TestCase):
    """Test patient history and listing functionality."""

    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.db.create_schema()
        
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.patient_repo = SQLAlchemyPatientRepository(self.db)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)
        
        self.session_service = SessionService(
            session_repo=self.session_repo,
            telemetry_repo=self.telemetry_repo,
            result_repo=self.result_repo
        )
        self.patient_service = PatientService(patient_repo=self.patient_repo)

    def test_patient_history_and_list(self):
        # Create sessions for PATIENT-A and PATIENT-B
        s1 = self.session_service.start_session(
            StartSessionRequest(patient_id="PATIENT-A", exercise="elbow_flexion")
        )
        self.session_service.record_result(
            s1.session_id,
            RecordResultRequest(repetitions=10, rom_min=30.0, rom_max=160.0)
        )
        self.session_service.end_session(s1.session_id)

        s2 = self.session_service.start_session(
            StartSessionRequest(patient_id="PATIENT-A", exercise="shoulder_flexion")
        )
        self.session_service.end_session(s2.session_id)

        # Retrieve history for PATIENT-A
        history = self.patient_service.get_patient_history("PATIENT-A")
        self.assertEqual(history.patient_id, "PATIENT-A")
        self.assertEqual(history.total_sessions, 2)
        self.assertEqual(history.sessions[0].results[0].repetitions, 10)

        # Retrieve patient list
        patient_list = self.patient_service.list_patients()
        self.assertEqual(patient_list.total_patients, 1)
        self.assertEqual(patient_list.patients[0].patient_id, "PATIENT-A")
        self.assertEqual(patient_list.patients[0].total_sessions, 2)


class TestRehabService(unittest.TestCase):
    """Test exercise definitions catalog and frame analysis pipeline integration."""

    def setUp(self):
        self.rehab_service = RehabService()

    def test_list_exercises(self):
        res = self.rehab_service.list_exercises()
        self.assertGreater(res.total, 0)
        exercise_ids = [ex.id for ex in res.exercises]
        self.assertIn("elbow_flexion", exercise_ids)

    def test_get_exercise_details(self):
        ex = self.rehab_service.get_exercise_details("elbow_flexion")
        self.assertEqual(ex.name, "Elbow Flexion")

    def test_get_invalid_exercise_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.rehab_service.get_exercise_details("invalid_exercise_id")

    def test_process_pose_frame(self):
        pose_frame = {
            "timestamp": 123456.0,
            "angles": {"left_elbow": 170.0},
            "visibility": {"LEFT_ELBOW": 0.9, "LEFT_SHOULDER": 0.9, "LEFT_WRIST": 0.9},
            "landmarks": {
                "LEFT_SHOULDER": {"x": 0.5, "y": 0.2, "z": 0.0},
                "LEFT_ELBOW": {"x": 0.5, "y": 0.5, "z": 0.0},
                "LEFT_WRIST": {"x": 0.5, "y": 0.8, "z": 0.0}
            }
        }
        req = ProcessFrameRequest(pose_frame=pose_frame)
        res = self.rehab_service.process_pose_frame(req)

        self.assertEqual(res.raw_angle, 170.0)
        self.assertIsNotNone(res.valid_angle)
        self.assertIsNotNone(res.smoothed_angle)
        self.assertEqual(res.state, "EXTENDED")
        self.assertEqual(res.repetitions, 0)


if __name__ == "__main__":
    unittest.main()
