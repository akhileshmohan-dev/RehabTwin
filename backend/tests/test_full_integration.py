"""
backend/tests/test_full_integration.py

Phase 5F Holistic End-to-End Integration Test Suite.
Exercises actual application boundaries across all layers:
  REST API → Service → Repository → SQLite (with PRAGMA foreign_keys=ON)
  and:
  WebSocket → Pipeline → Result persistence → REST completion → Therapist dashboard API.
"""
import base64
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.dependencies import (
    get_database,
    get_patient_repo,
    get_assignment_repo,
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
)
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemyAssignmentRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from digital_thread.db import Database


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def _create_jpeg_b64() -> str:
    """Create a 64x64 valid JPEG image encoded as base64."""
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[:, :] = [120, 150, 180]
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def _build_mock_mp_pose(landmark_positions: dict[int, tuple[float, float]]):
    """
    Build a mock MediaPipe pose result with 33 landmarks having 0.99 visibility,
    overriding specific indices with provided (x, y) coordinates.
    """
    landmarks = []
    for _ in range(33):
        lm = MagicMock()
        lm.x, lm.y, lm.z, lm.visibility = 0.5, 0.5, 0.0, 0.99
        landmarks.append(lm)

    for idx, (x, y) in landmark_positions.items():
        landmarks[idx].x = x
        landmarks[idx].y = y

    result = MagicMock()
    result.pose_landmarks = MagicMock()
    result.pose_landmarks.landmark = landmarks
    return result


def _mp_left_elbow(angle_type: str = "flexed"):
    """
    Left arm MediaPipe landmarks:
      LEFT_SHOULDER = 11
      LEFT_ELBOW    = 13
      LEFT_WRIST    = 15
    """
    # Shoulder at (0.3, 0.2), Elbow at (0.3, 0.5)
    if angle_type == "flexed":
        # Wrist at (0.3, 0.25) -> ~70° angle (< 100° threshold)
        return _build_mock_mp_pose({11: (0.3, 0.2), 13: (0.3, 0.5), 15: (0.4, 0.4)})
    else:
        # Extended: Wrist at (0.3, 0.8) -> ~170° angle (> 160° threshold)
        return _build_mock_mp_pose({11: (0.3, 0.2), 13: (0.3, 0.5), 15: (0.3, 0.8)})


def _mp_right_elbow(angle_type: str = "flexed"):
    """
    Right arm MediaPipe landmarks:
      RIGHT_SHOULDER = 12
      RIGHT_ELBOW    = 14
      RIGHT_WRIST    = 16
    """
    if angle_type == "flexed":
        return _build_mock_mp_pose({12: (0.7, 0.2), 14: (0.7, 0.5), 16: (0.6, 0.4)})
    else:
        return _build_mock_mp_pose({12: (0.7, 0.2), 14: (0.7, 0.5), 16: (0.7, 0.8)})


def _mp_right_knee(angle_type: str = "flexed"):
    """
    Right leg MediaPipe landmarks:
      RIGHT_HIP   = 24
      RIGHT_KNEE  = 26
      RIGHT_ANKLE = 28
    """
    if angle_type == "flexed":
        return _build_mock_mp_pose({24: (0.6, 0.4), 26: (0.6, 0.7), 28: (0.5, 0.6)})
    else:
        return _build_mock_mp_pose({24: (0.6, 0.4), 26: (0.6, 0.7), 28: (0.6, 0.95)})


def _mp_no_person():
    """Mock MediaPipe result when no person is detected."""
    res = MagicMock()
    res.pose_landmarks = None
    return res


# ---------------------------------------------------------------------------
# Base Integration Test Case with Clean Database Fixture
# ---------------------------------------------------------------------------

class BaseIntegrationTest(unittest.TestCase):
    def setUp(self):
        # Unique file-backed SQLite database per test for thread safety in TestClient
        self.db_path = f"test_integ_{os.urandom(6).hex()}.db"
        self.db_url = f"sqlite:///{self.db_path}?check_same_thread=False"
        self.db = Database(self.db_url)
        self.db.create_schema()

        app.dependency_overrides[get_database] = lambda: self.db
        app.dependency_overrides[get_patient_repo] = lambda: SQLAlchemyPatientRepository(self.db)
        app.dependency_overrides[get_assignment_repo] = lambda: SQLAlchemyAssignmentRepository(self.db)
        app.dependency_overrides[get_session_repo] = lambda: SQLAlchemySessionRepository(self.db)
        app.dependency_overrides[get_telemetry_repo] = lambda: SQLAlchemyTelemetryRepository(self.db)
        app.dependency_overrides[get_result_repo] = lambda: SQLAlchemyResultRepository(self.db)

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.engine.dispose()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Scenario Tests
# ---------------------------------------------------------------------------

class TestPhase5FIntegration(BaseIntegrationTest):

    def test_scenario_a_patient_p1_left_elbow_full_lifecycle(self):
        """
        Scenario A:
        P1 starts Left Elbow Flexion via REST, streams valid frames via WebSocket,
        completes via END_SESSION + REST /end, and verifies Result & Therapist Dashboard.
        """
        # 1. Register patient and assign exercise via REST API
        self.client.post("/api/patients", json={"patient_id": "P1", "name": "Patient P1"})
        self.client.post("/api/patients/P1/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        start_resp = self.client.post("/api/sessions", json={
            "patient_id": "P1",
            "exercise": "elbow_flexion",
            "side": "left",
        })
        self.assertEqual(start_resp.status_code, 201)
        sess_data = start_resp.json()
        sid = sess_data["session_id"]
        self.assertEqual(sess_data["side"], "left")
        self.assertEqual(sess_data["status"], "ACTIVE")

        # 2. Connect WebSocket and stream frames
        b64_frame = _create_jpeg_b64()
        with patch("backend.routes.analysis.mp.solutions.pose.Pose") as mock_pose_cls:
            mock_pose = MagicMock()
            mock_pose_cls.return_value = mock_pose
            # Stream 5 extended -> 5 flexed -> 5 extended to settle MovingAverageFilter(window_size=5)
            # and complete 1 repetition cleanly
            frames = [_mp_left_elbow("extended")] * 5 + [_mp_left_elbow("flexed")] * 5 + [_mp_left_elbow("extended")] * 5
            mock_pose.process.side_effect = frames

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(len(frames)):
                    ws.send_text(b64_frame)
                    msg = ws.receive_json()
                    self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                    self.assertTrue(msg["pose_status"]["is_valid"])

                # Send END_SESSION control message
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_msg = ws.receive_json()
                self.assertEqual(final_msg["type"], "FINAL_RESULT")
                self.assertGreaterEqual(final_msg["repetitions"], 1)
                self.assertIsNotNone(final_msg["performance_score"])

        # 3. Complete session via authoritative REST /end
        end_resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(end_resp.status_code, 200)
        end_data = end_resp.json()
        self.assertEqual(end_data["status"], "COMPLETED")
        self.assertIsNotNone(end_data["result"])
        self.assertEqual(end_data["result"]["side"], "left")

        # 4. Verify Therapist Dashboard overview and history
        overview_resp = self.client.get("/api/patients")
        self.assertEqual(overview_resp.status_code, 200)
        overview = overview_resp.json()
        self.assertEqual(overview["total_patients"], 1)
        self.assertEqual(overview["total_sessions"], 1)
        self.assertEqual(overview["active_patients"], 0)
        self.assertIsNotNone(overview["average_performance_score"])

        history_resp = self.client.get("/api/patients/P1/sessions")
        self.assertEqual(history_resp.status_code, 200)
        history = history_resp.json()
        self.assertEqual(history["total_sessions"], 1)
        self.assertEqual(history["sessions"][0]["side"], "left")
        self.assertEqual(len(history["sessions"][0]["results"]), 1)
        self.assertEqual(history["sessions"][0]["results"][0]["side"], "left")

    def test_scenario_b_patient_p1_right_elbow_isolation(self):
        """
        Scenario B:
        Patient P1 performs Right Elbow Flexion in a separate session.
        Verifies Result.side='right' and that Left session is not contaminated.
        """
        # Register patient and assign exercises
        self.client.post("/api/patients", json={"patient_id": "P1", "name": "Patient P1"})
        self.client.post("/api/patients/P1/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        self.client.post("/api/patients/P1/exercises", json={"exercise_id": "elbow_flexion", "side": "right"})
        left_sid = self.client.post("/api/sessions", json={
            "patient_id": "P1",
            "exercise": "elbow_flexion",
            "side": "left",
        }).json()["session_id"]
        # Record a dummy result and complete it
        SQLAlchemyResultRepository(self.db).record_result(
            session_id=left_sid,
            repetitions=5,
            rom_min=40.0,
            rom_max=140.0,
            rom_average=90.0,
            performance_score=75.0,
            feedback="Left arm completed",
        )
        self.client.post(f"/api/sessions/{left_sid}/end")

        # Create Right session
        right_sid = self.client.post("/api/sessions", json={
            "patient_id": "P1",
            "exercise": "elbow_flexion",
            "side": "right",
        }).json()["session_id"]

        b64_frame = _create_jpeg_b64()
        with patch("backend.routes.analysis.mp.solutions.pose.Pose") as mock_pose_cls:
            mock_pose = MagicMock()
            mock_pose_cls.return_value = mock_pose
            mock_pose.process.side_effect = [
                _mp_right_elbow("extended"),
                _mp_right_elbow("flexed"),
                _mp_right_elbow("extended"),
            ]

            with self.client.websocket_connect(f"/api/analysis/ws/{right_sid}") as ws:
                for _ in range(3):
                    ws.send_text(b64_frame)
                    msg = ws.receive_json()
                    self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                    self.assertTrue(msg["pose_status"]["is_valid"])

                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_msg = ws.receive_json()
                self.assertEqual(final_msg["type"], "FINAL_RESULT")

        self.client.post(f"/api/sessions/{right_sid}/end")

        # Verify history preserves both sides accurately without contamination
        history = self.client.get("/api/patients/P1/sessions").json()
        self.assertEqual(history["total_sessions"], 2)
        sessions_by_side = {s["side"]: s for s in history["sessions"]}
        self.assertIn("left", sessions_by_side)
        self.assertIn("right", sessions_by_side)
        self.assertEqual(sessions_by_side["left"]["results"][0]["side"], "left")
        self.assertEqual(sessions_by_side["right"]["results"][0]["side"], "right")

    def test_scenario_c_genuine_concurrent_overlapping_sessions(self):
        """
        Scenario C:
        Two patients (P1 left elbow, P2 right knee) have simultaneous ACTIVE sessions.
        Frames are interleaved over concurrent WebSockets.
        Verifies no cross-talk of session IDs, pipelines, telemetry, sides, or results.
        """
        self.client.post("/api/patients", json={"patient_id": "P1", "name": "Patient P1"})
        self.client.post("/api/patients/P1/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        self.client.post("/api/patients", json={"patient_id": "P2", "name": "Patient P2"})
        self.client.post("/api/patients/P2/exercises", json={"exercise_id": "knee_flexion", "side": "right"})

        s1 = self.client.post("/api/sessions", json={
            "patient_id": "P1", "exercise": "elbow_flexion", "side": "left"
        }).json()["session_id"]

        s2 = self.client.post("/api/sessions", json={
            "patient_id": "P2", "exercise": "knee_flexion", "side": "right"
        }).json()["session_id"]

        # Verify both are ACTIVE simultaneously in system overview
        overview = self.client.get("/api/patients").json()
        self.assertEqual(overview["active_patients"], 2)
        self.assertEqual(overview["total_patients"], 2)

        b64_frame = _create_jpeg_b64()

        # Two distinct mock pose instances for the two WebSocket connections
        pose1 = MagicMock()
        pose2 = MagicMock()
        pose1.process.side_effect = [
            _mp_left_elbow("extended"),
            _mp_left_elbow("flexed"),
            _mp_left_elbow("extended"),
        ]
        pose2.process.side_effect = [
            _mp_right_knee("extended"),
            _mp_right_knee("flexed"),
            _mp_right_knee("extended"),
        ]

        with patch("backend.routes.analysis.mp.solutions.pose.Pose", side_effect=[pose1, pose2]):
            with self.client.websocket_connect(f"/api/analysis/ws/{s1}") as ws1:
                with self.client.websocket_connect(f"/api/analysis/ws/{s2}") as ws2:
                    # Interleave frame processing while both sessions are active
                    ws1.send_text(b64_frame)
                    msg1_a = ws1.receive_json()
                    self.assertEqual(msg1_a["session_id"], s1)

                    ws2.send_text(b64_frame)
                    msg2_a = ws2.receive_json()
                    self.assertEqual(msg2_a["session_id"], s2)

                    ws1.send_text(b64_frame)
                    msg1_b = ws1.receive_json()
                    self.assertEqual(msg1_b["session_id"], s1)

                    ws2.send_text(b64_frame)
                    msg2_b = ws2.receive_json()
                    self.assertEqual(msg2_b["session_id"], s2)

                    # Complete both sessions independently
                    ws1.send_text(json.dumps({"type": "END_SESSION"}))
                    final1 = ws1.receive_json()
                    self.assertEqual(final1["session_id"], s1)

                    ws2.send_text(json.dumps({"type": "END_SESSION"}))
                    final2 = ws2.receive_json()
                    self.assertEqual(final2["session_id"], s2)

        self.client.post(f"/api/sessions/{s1}/end")
        self.client.post(f"/api/sessions/{s2}/end")

        # Verify results in SQLite
        res1 = SQLAlchemyResultRepository(self.db).get_result(s1)
        res2 = SQLAlchemyResultRepository(self.db).get_result(s2)
        self.assertEqual(res1["exercise"], "elbow_flexion")
        self.assertEqual(res1["side"], "left")
        self.assertEqual(res2["exercise"], "knee_flexion")
        self.assertEqual(res2["side"], "right")

        # Verify active count drops back to 0
        final_overview = self.client.get("/api/patients").json()
        self.assertEqual(final_overview["active_patients"], 0)

    def test_scenario_d_valid_invalid_valid_continuity(self):
        """
        Scenario D:
        Streams VALID → INVALID → VALID frames.
        Verifies invalid frames do not reset, corrupt, or increment repetitions/ROM.
        """
        self.client.post("/api/patients", json={"patient_id": "P_CONT", "name": "Patient Cont"})
        self.client.post("/api/patients/P_CONT/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        sid = self.client.post("/api/sessions", json={
            "patient_id": "P_CONT", "exercise": "elbow_flexion", "side": "left"
        }).json()["session_id"]

        b64_frame = _create_jpeg_b64()
        with patch("backend.routes.analysis.mp.solutions.pose.Pose") as mock_pose_cls:
            mock_pose = MagicMock()
            mock_pose_cls.return_value = mock_pose
            # 5 extended -> 5 flexed -> 2 invalid -> 5 extended
            frames = (
                [_mp_left_elbow("extended")] * 5
                + [_mp_left_elbow("flexed")] * 5
                + [_mp_no_person()] * 2
                + [_mp_left_elbow("extended")] * 5
            )
            mock_pose.process.side_effect = frames

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                # 1. 5 extended frames -> repetitions: 0, state: EXTENDED
                for _ in range(5):
                    ws.send_text(b64_frame)
                    r = ws.receive_json()
                    self.assertEqual(r["type"], "ANALYSIS_RESULT")
                    self.assertEqual(r["repetitions"], 0)

                # 2. 5 flexed frames -> transitions to FLEXED, repetitions still 0
                for _ in range(5):
                    ws.send_text(b64_frame)
                    r = ws.receive_json()
                    self.assertEqual(r["type"], "ANALYSIS_RESULT")
                self.assertEqual(r["state"], "FLEXED")
                self.assertEqual(r["repetitions"], 0)

                # 3. 2 invalid frames -> NO_POSE, does not corrupt state
                for _ in range(2):
                    ws.send_text(b64_frame)
                    r = ws.receive_json()
                    self.assertEqual(r["type"], "NO_POSE")

                # 4. 5 extended frames -> transitions back to EXTENDED, repetition completes to 1!
                for _ in range(5):
                    ws.send_text(b64_frame)
                    r = ws.receive_json()
                    self.assertEqual(r["type"], "ANALYSIS_RESULT")
                self.assertEqual(r["repetitions"], 1)
                self.assertEqual(r["state"], "EXTENDED")

    def test_scenario_e1_unexpected_disconnect_after_valid_processing(self):
        """
        Scenario E1:
        Client processes valid frames, then disconnects abruptly without END_SESSION.
        Verifies Result is persisted by disconnect handler, session remains ACTIVE,
        and subsequent REST /end marks COMPLETED.
        """
        self.client.post("/api/patients", json={"patient_id": "P_DISC", "name": "Patient Disc"})
        self.client.post("/api/patients/P_DISC/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        sid = self.client.post("/api/sessions", json={
            "patient_id": "P_DISC", "exercise": "elbow_flexion", "side": "left"
        }).json()["session_id"]

        b64_frame = _create_jpeg_b64()
        with patch("backend.routes.analysis.mp.solutions.pose.Pose") as mock_pose_cls:
            mock_pose = MagicMock()
            mock_pose_cls.return_value = mock_pose
            mock_pose.process.return_value = _mp_left_elbow("extended")

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(b64_frame)
                ws.receive_json()
                # Disconnect abruptly by closing context manager without END_SESSION

        # Verify Result was persisted on disconnect
        result = SQLAlchemyResultRepository(self.db).get_result(sid)
        self.assertIsNotNone(result)

        # Verify session status is STILL ACTIVE (WebSocket disconnect does not complete session)
        sess = SQLAlchemySessionRepository(self.db).get_session(sid)
        self.assertEqual(sess["status"], "ACTIVE")

        # REST /end completes it
        end_resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(end_resp.status_code, 200)
        self.assertEqual(end_resp.json()["status"], "COMPLETED")

    def test_scenario_e2_unexpected_disconnect_before_usable_result(self):
        """
        Scenario E2:
        Session starts, WebSocket disconnects with 0 valid frames.
        Verifies no Result exists, session remains ACTIVE, REST /end returns 400.
        """
        self.client.post("/api/patients", json={"patient_id": "P_DISC2", "name": "Patient Disc 2"})
        self.client.post("/api/patients/P_DISC2/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        sid = self.client.post("/api/sessions", json={
            "patient_id": "P_DISC2", "exercise": "elbow_flexion", "side": "left"
        }).json()["session_id"]

        with patch("backend.routes.analysis.mp.solutions.pose.Pose") as mock_pose_cls:
            mock_pose = MagicMock()
            mock_pose_cls.return_value = mock_pose
            mock_pose.process.return_value = _mp_no_person()

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                # Send frame that produces NO_POSE (not valid)
                ws.send_text(_create_jpeg_b64())
                ws.receive_json()
                # Disconnect without valid frames

        # Verify no Result was persisted
        result = SQLAlchemyResultRepository(self.db).get_result(sid)
        self.assertIsNone(result)

        # Verify session is still ACTIVE
        sess = SQLAlchemySessionRepository(self.db).get_session(sid)
        self.assertEqual(sess["status"], "ACTIVE")

        # REST /end should fail with 400
        end_resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(end_resp.status_code, 400)
        self.assertIn("cannot be ended because no result has been recorded", end_resp.json()["detail"])

        # Session remains ACTIVE
        sess_after = SQLAlchemySessionRepository(self.db).get_session(sid)
        self.assertEqual(sess_after["status"], "ACTIVE")

    def test_scenario_f_rest_end_with_active_and_no_result(self):
        """
        Scenario F:
        Attempt REST /end directly on an ACTIVE session with no Result.
        Verifies 400, no fake Result, and status remains ACTIVE.
        """
        self.client.post("/api/patients", json={"patient_id": "P_NORES", "name": "Patient NoRes"})
        self.client.post("/api/patients/P_NORES/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        sid = self.client.post("/api/sessions", json={
            "patient_id": "P_NORES", "exercise": "elbow_flexion", "side": "left"
        }).json()["session_id"]

        end_resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(end_resp.status_code, 400)

        # Verify no Result created
        result = SQLAlchemyResultRepository(self.db).get_result(sid)
        self.assertIsNone(result)

        # Status remains ACTIVE
        sess = SQLAlchemySessionRepository(self.db).get_session(sid)
        self.assertEqual(sess["status"], "ACTIVE")

    def test_scenario_g_restart_durability_and_survival(self):
        """
        Scenario G:
        Creates session & result, completes it, disposes database engine,
        creates a new Database instance pointing to the same file, and verifies
        all records and dashboard aggregations survive intact.
        """
        self.client.post("/api/patients", json={"patient_id": "P_DURABLE", "name": "Patient Durable"})
        self.client.post("/api/patients/P_DURABLE/exercises", json={"exercise_id": "shoulder_abduction", "side": "right"})
        sid = self.client.post("/api/sessions", json={
            "patient_id": "P_DURABLE", "exercise": "shoulder_abduction", "side": "right"
        }).json()["session_id"]

        # Record result and complete
        SQLAlchemyResultRepository(self.db).record_result(
            session_id=sid,
            repetitions=15,
            rom_min=20.0,
            rom_max=160.0,
            rom_average=140.0,
            performance_score=95.0,
            feedback="Great abduction range",
        )
        self.client.post(f"/api/sessions/{sid}/end")

        # Dispose database engine (simulating shutdown)
        self.db.engine.dispose()
        app.dependency_overrides.clear()

        # Reopen with brand new Database instance pointing to the exact same file
        restarted_db = Database(self.db_url)
        restarted_db.create_schema()

        app.dependency_overrides[get_database] = lambda: restarted_db
        app.dependency_overrides[get_patient_repo] = lambda: SQLAlchemyPatientRepository(restarted_db)
        app.dependency_overrides[get_assignment_repo] = lambda: SQLAlchemyAssignmentRepository(restarted_db)
        app.dependency_overrides[get_session_repo] = lambda: SQLAlchemySessionRepository(restarted_db)
        app.dependency_overrides[get_telemetry_repo] = lambda: SQLAlchemyTelemetryRepository(restarted_db)
        app.dependency_overrides[get_result_repo] = lambda: SQLAlchemyResultRepository(restarted_db)

        new_client = TestClient(app, raise_server_exceptions=False)

        # Query session
        sess_resp = new_client.get(f"/api/sessions/{sid}")
        self.assertEqual(sess_resp.status_code, 200)
        s_data = sess_resp.json()
        self.assertEqual(s_data["patient_id"], "P_DURABLE")
        self.assertEqual(s_data["exercise"], "shoulder_abduction")
        self.assertEqual(s_data["side"], "right")
        self.assertEqual(s_data["status"], "COMPLETED")

        # Query history
        hist_resp = new_client.get("/api/patients/P_DURABLE/sessions")
        self.assertEqual(hist_resp.status_code, 200)
        h_data = hist_resp.json()
        self.assertEqual(h_data["total_sessions"], 1)
        res = h_data["sessions"][0]["results"][0]
        self.assertEqual(res["repetitions"], 15)
        self.assertEqual(res["performance_score"], 95.0)

        # Query overview
        ov_resp = new_client.get("/api/patients")
        self.assertEqual(ov_resp.status_code, 200)
        ov = ov_resp.json()
        self.assertEqual(ov["total_patients"], 1)
        self.assertEqual(ov["total_sessions"], 1)
        self.assertEqual(ov["average_performance_score"], 95.0)

        restarted_db.engine.dispose()

    def test_scenario_h_bilateral_dashboard_isolation(self):
        """
        Scenario H:
        Completed left and right sessions of the same exercise.
        Verifies dashboard history preserves both sides distinctly.
        """
        # Register patient and create Left session
        self.client.post("/api/patients", json={"patient_id": "P_ISO", "name": "Patient Iso"})
        self.client.post("/api/patients/P_ISO/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        self.client.post("/api/patients/P_ISO/exercises", json={"exercise_id": "elbow_flexion", "side": "right"})
        s_left = self.client.post("/api/sessions", json={
            "patient_id": "P_ISO", "exercise": "elbow_flexion", "side": "left"
        }).json()["session_id"]
        SQLAlchemyResultRepository(self.db).record_result(
            session_id=s_left, repetitions=8, rom_min=45.0, rom_max=130.0,
            rom_average=87.5, performance_score=80.0, feedback="Left side"
        )
        self.client.post(f"/api/sessions/{s_left}/end")

        # Create Right session
        s_right = self.client.post("/api/sessions", json={
            "patient_id": "P_ISO", "exercise": "elbow_flexion", "side": "right"
        }).json()["session_id"]
        SQLAlchemyResultRepository(self.db).record_result(
            session_id=s_right, repetitions=12, rom_min=30.0, rom_max=145.0,
            rom_average=87.5, performance_score=92.0, feedback="Right side"
        )
        self.client.post(f"/api/sessions/{s_right}/end")

        history = self.client.get("/api/patients/P_ISO/sessions").json()
        self.assertEqual(history["total_sessions"], 2)
        sides = {s["side"]: s["results"][0]["repetitions"] for s in history["sessions"]}
        self.assertEqual(sides["left"], 8)
        self.assertEqual(sides["right"], 12)

    def test_scenario_i_cross_exercise_isolation(self):
        """
        Scenario I:
        Patient has completed sessions for different exercises.
        Verifies both are present with distinct exercises and accurate individual results.
        """
        self.client.post("/api/patients", json={"patient_id": "P_EX", "name": "Patient Ex"})
        self.client.post("/api/patients/P_EX/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        self.client.post("/api/patients/P_EX/exercises", json={"exercise_id": "knee_flexion", "side": "left"})
        s_elbow = self.client.post("/api/sessions", json={
            "patient_id": "P_EX", "exercise": "elbow_flexion", "side": "left"
        }).json()["session_id"]
        SQLAlchemyResultRepository(self.db).record_result(
            session_id=s_elbow, repetitions=10, rom_min=40.0, rom_max=135.0,
            rom_average=87.5, performance_score=85.0
        )
        self.client.post(f"/api/sessions/{s_elbow}/end")

        s_knee = self.client.post("/api/sessions", json={
            "patient_id": "P_EX", "exercise": "knee_flexion", "side": "left"
        }).json()["session_id"]
        SQLAlchemyResultRepository(self.db).record_result(
            session_id=s_knee, repetitions=14, rom_min=35.0, rom_max=140.0,
            rom_average=87.5, performance_score=90.0
        )
        self.client.post(f"/api/sessions/{s_knee}/end")

        history = self.client.get("/api/patients/P_EX/sessions").json()
        self.assertEqual(history["total_sessions"], 2)
        ex_map = {s["exercise"]: s["results"][0]["repetitions"] for s in history["sessions"]}
        self.assertEqual(ex_map["elbow_flexion"], 10)
        self.assertEqual(ex_map["knee_flexion"], 14)

    def test_scenario_j_completed_session_without_result(self):
        """
        Scenario J:
        A completed session exists without a Result.
        Verifies dashboard API returns empty results list, average score excludes it,
        and no fabricated 0.0 scores contaminate the overview.
        """
        # Register patient and create session 1 with Result
        self.client.post("/api/patients", json={"patient_id": "P_NORESULT", "name": "Patient NoResult"})
        self.client.post("/api/patients/P_NORESULT/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        self.client.post("/api/patients/P_NORESULT/exercises", json={"exercise_id": "elbow_flexion", "side": "right"})
        s1 = self.client.post("/api/sessions", json={
            "patient_id": "P_NORESULT", "exercise": "elbow_flexion", "side": "left"
        }).json()["session_id"]
        SQLAlchemyResultRepository(self.db).record_result(
            session_id=s1, repetitions=10, rom_min=40.0, rom_max=140.0,
            rom_average=90.0, performance_score=80.0
        )
        self.client.post(f"/api/sessions/{s1}/end")

        # Create session 2 directly ended in DB without Result (e.g. administrative completion)
        s2 = self.client.post("/api/sessions", json={
            "patient_id": "P_NORESULT", "exercise": "elbow_flexion", "side": "right"
        }).json()["session_id"]
        SQLAlchemySessionRepository(self.db).end_session(s2)

        # Overview average score must be 80.0 (session 2 with no Result must not drag it down to 40.0)
        overview = self.client.get("/api/patients").json()
        self.assertEqual(overview["total_sessions"], 2)
        self.assertEqual(overview["average_performance_score"], 80.0)

        # History check
        history = self.client.get("/api/patients/P_NORESULT/sessions").json()
        s2_hist = next(s for s in history["sessions"] if s["session_id"] == s2)
        self.assertEqual(s2_hist["status"], "COMPLETED")
        self.assertEqual(s2_hist["results"], [])  # Empty results list, no fabricated data
