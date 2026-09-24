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
from backend.services.session_service import SessionService, SessionNotFoundException, SessionNotActiveException, InvalidExerciseException
from backend.services.patient_service import PatientService
from backend.services.rehab_service import RehabService
from backend.schemas.analysis import ProcessFrameRequest
from backend.main import root, health_check, app
from fastapi.testclient import TestClient


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
        self.patient_repo = SQLAlchemyPatientRepository(self.db)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)
        self.patient_repo.create_patient({"patient_id": "PATIENT-TEST", "name": "Patient TEST", "status": "ACTIVE"})
        self.patient_repo.create_patient({"patient_id": "PATIENT-001", "name": "Patient 001", "status": "ACTIVE"})
        self.service = SessionService(
            session_repo=self.session_repo,
            telemetry_repo=self.telemetry_repo,
            result_repo=self.result_repo,
            patient_repo=self.patient_repo,
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

    def test_record_to_ended_session_raises_exception(self):
        start_res = self.service.start_session(
            StartSessionRequest(patient_id="PATIENT-001", exercise="elbow_flexion")
        )
        sid = start_res.session_id
        self.service.record_result(sid, RecordResultRequest(repetitions=1))
        self.service.end_session(sid)
        
        frame_req = RecordFrameRequest(
            frame_id=1,
            landmarks={"LEFT_ELBOW": {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}},
            joint_angles={"left_elbow": 120.0},
            phase="EXTENDED"
        )
        with self.assertRaises(SessionNotActiveException):
            self.service.record_frame(sid, frame_req)
            
        result_req = RecordResultRequest(
            repetitions=5,
            rom_min=45.0,
            rom_max=165.0,
            rom_average=120.0,
            performance_score=95.0,
            feedback="Good form"
        )
        with self.assertRaises(SessionNotActiveException):
            self.service.record_result(sid, result_req)


    def test_start_session_with_unknown_exercise_raises_exception(self):
        with self.assertRaises(InvalidExerciseException):
            self.service.start_session(
                StartSessionRequest(patient_id="PATIENT-TEST", exercise="invalid_dance")
            )

    def test_start_session_all_approved_exercises(self):
        for ex in ["elbow_flexion", "shoulder_flexion", "shoulder_abduction", "knee_flexion"]:
            res = self.service.start_session(
                StartSessionRequest(patient_id="PATIENT-TEST", exercise=ex)
            )
            self.assertEqual(res.status, "ACTIVE")
            self.assertEqual(res.exercise, ex)

    def test_post_session_unknown_exercise_returns_400(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.core.dependencies import get_session_repo, get_telemetry_repo, get_result_repo
        app.dependency_overrides[get_session_repo] = lambda: self.session_repo
        app.dependency_overrides[get_telemetry_repo] = lambda: self.telemetry_repo
        app.dependency_overrides[get_result_repo] = lambda: self.result_repo
        try:
            client = TestClient(app)
            resp = client.post("/api/sessions", json={"patient_id": "P001", "exercise": "unknown_dance"})
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Unknown or unsupported exercise", resp.json()["detail"])
        finally:
            app.dependency_overrides.clear()


class TestPatientService(unittest.TestCase):
    """Test patient history and listing functionality."""

    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.db.create_schema()
        
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.patient_repo = SQLAlchemyPatientRepository(self.db)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)
        
        self.patient_repo.create_patient({"patient_id": "PATIENT-A", "name": "Patient A", "status": "ACTIVE"})
        self.patient_repo.create_patient({"patient_id": "PATIENT-B", "name": "Patient B", "status": "ACTIVE"})

        self.session_service = SessionService(
            session_repo=self.session_repo,
            telemetry_repo=self.telemetry_repo,
            result_repo=self.result_repo,
            patient_repo=self.patient_repo,
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
        self.session_service.record_result(
            s2.session_id,
            RecordResultRequest(repetitions=5, rom_min=20.0, rom_max=150.0)
        )
        self.session_service.end_session(s2.session_id)

        # Retrieve history for PATIENT-A (newest first: s2 then s1)
        history = self.patient_service.get_patient_history("PATIENT-A")
        self.assertEqual(history.patient_id, "PATIENT-A")
        self.assertEqual(history.total_sessions, 2)
        self.assertEqual(history.sessions[0].session_id, s2.session_id)
        self.assertEqual(history.sessions[0].results[0].repetitions, 5)
        self.assertEqual(history.sessions[1].session_id, s1.session_id)
        self.assertEqual(history.sessions[1].results[0].repetitions, 10)

        # Retrieve patient list (PATIENT-A and PATIENT-B both persist)
        patient_list = self.patient_service.list_patients()
        self.assertEqual(patient_list.total_patients, 2)
        patient_a = next(p for p in patient_list.patients if p.patient_id == "PATIENT-A")
        self.assertEqual(patient_a.total_sessions, 2)


class TestRehabService(unittest.TestCase):
    """Test exercise definitions catalog and frame analysis pipeline integration."""

    def setUp(self):
        self.rehab_service = RehabService()
        self.client = TestClient(app)

    def test_list_exercises(self):
        res = self.rehab_service.list_exercises()
        self.assertEqual(res.total, 4)
        exercise_ids = [ex.id for ex in res.exercises]
        for expected in ["elbow_flexion", "shoulder_flexion", "shoulder_abduction", "knee_flexion"]:
            self.assertIn(expected, exercise_ids)

    def test_get_exercise_details(self):
        for ex_id, expected_name in [
            ("elbow_flexion", "Elbow Flexion"),
            ("shoulder_flexion", "Shoulder Flexion"),
            ("shoulder_abduction", "Shoulder Abduction"),
            ("knee_flexion", "Knee Flexion"),
        ]:
            ex = self.rehab_service.get_exercise_details(ex_id)
            self.assertEqual(ex.name, expected_name)

    def test_get_invalid_exercise_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.rehab_service.get_exercise_details("invalid_exercise_id")

    def test_process_pose_frame_with_shoulder(self):
        pose_frame = {
            "timestamp": 123456.0,
            "angles": {"left_shoulder": 160.0},
            "visibility": {"LEFT_HIP": 0.9, "LEFT_SHOULDER": 0.9, "LEFT_ELBOW": 0.9},
            "landmarks": {
                "LEFT_HIP": {"x": 0.5, "y": 0.7, "z": 0.0},
                "LEFT_SHOULDER": {"x": 0.5, "y": 0.4, "z": 0.0},
                "LEFT_ELBOW": {"x": 0.5, "y": 0.1, "z": 0.0}
            }
        }
        req = ProcessFrameRequest(pose_frame=pose_frame, exercise_id="shoulder_flexion")
        res = self.rehab_service.process_pose_frame(req)
        self.assertEqual(res.raw_angle, 160.0)
        self.assertEqual(res.state, "EXTENDED")

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

    def test_process_pose_frame_with_unknown_exercise_raises_key_error(self):
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
        req = ProcessFrameRequest(pose_frame=pose_frame, exercise_id="not_a_real_exercise")
        with self.assertRaises(KeyError):
            self.rehab_service.process_pose_frame(req)

    def test_post_process_frame_unknown_exercise_returns_400(self):
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
        resp = self.client.post("/api/analysis/process-frame", json={
            "pose_frame": pose_frame,
            "exercise_id": "not_a_real_exercise"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unknown or unsupported exercise", resp.json()["detail"])



from backend.routes.analysis import _compute_performance_score
from rehabilitation.exercises import get_exercise_definition


class TestPerformanceScoringPhase4C(unittest.TestCase):
    def test_compute_performance_score_clamping(self):
        # Excursion > target clamps to 100.0
        self.assertEqual(_compute_performance_score(150.0, target_rom=130.0), 100.0)
        # Excursion < 0 clamps to 0.0
        self.assertEqual(_compute_performance_score(-10.0, target_rom=130.0), 0.0)
        # None excursion returns 0.0
        self.assertEqual(_compute_performance_score(None, target_rom=130.0), 0.0)
        # Zero or negative target_rom returns 0.0
        self.assertEqual(_compute_performance_score(50.0, target_rom=0.0), 0.0)
        self.assertEqual(_compute_performance_score(50.0, target_rom=-130.0), 0.0)

    def test_all_four_exercises_target_rom_scoring(self):
        elbow_def = get_exercise_definition("elbow_flexion")
        knee_def = get_exercise_definition("knee_flexion")
        sh_flex_def = get_exercise_definition("shoulder_flexion")
        sh_abd_def = get_exercise_definition("shoulder_abduction")

        # Verify target ROMs from ExerciseDefinition
        self.assertEqual(elbow_def.target_rom, 130.0)
        self.assertEqual(knee_def.target_rom, 130.0)
        self.assertEqual(sh_flex_def.target_rom, 160.0)
        self.assertEqual(sh_abd_def.target_rom, 160.0)

        # 65 deg excursion:
        # Elbow: (65 / 130) * 100 = 50.0%
        self.assertAlmostEqual(_compute_performance_score(65.0, elbow_def.target_rom), 50.0)
        # Knee: (65 / 130) * 100 = 50.0%
        self.assertAlmostEqual(_compute_performance_score(65.0, knee_def.target_rom), 50.0)
        # Shoulder Flexion: (80 / 160) * 100 = 50.0%
        self.assertAlmostEqual(_compute_performance_score(80.0, sh_flex_def.target_rom), 50.0)
        # Shoulder Abduction: (80 / 160) * 100 = 50.0%
        self.assertAlmostEqual(_compute_performance_score(80.0, sh_abd_def.target_rom), 50.0)

    def test_midpoint_vs_excursion_semantics(self):
        # min_angle = 100.0, max_angle = 160.0
        min_angle = 100.0
        max_angle = 160.0
        midpoint = (min_angle + max_angle) / 2.0  # 130.0
        excursion = max_angle - min_angle         # 60.0

        # rom_average remains the midpoint
        self.assertEqual(midpoint, 130.0)
        # performance_score uses excursion (60 / 130 * 100 = 46.15%)
        score = _compute_performance_score(excursion, target_rom=130.0)
        self.assertAlmostEqual(score, (60.0 / 130.0) * 100.0, places=2)
        self.assertNotEqual(score, (midpoint / 130.0) * 100.0)


if __name__ == "__main__":
    unittest.main()
