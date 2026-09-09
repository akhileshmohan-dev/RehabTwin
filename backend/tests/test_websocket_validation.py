"""
backend/tests/test_websocket_validation.py

Phase 5B WebSocket integration tests for Pose Validation & Exceptions.
Validates:
- Structured NO_POSE message when no person detected.
- Structured NO_POSE message with missing_landmarks array when landmarks are out of frame.
- Structured ANALYSIS_RESULT with valid_angle=null and pose_status when visibility is low (< 0.5).
- Telemetry persistence is strictly NOT recorded on invalid frames.
- Repetition and ROM continuity across invalid -> valid frame sequences.
- Authoritative session side validation for bilateral sessions (left and right).
"""
import base64
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from digital_thread.db import Database
from digital_thread.models import Frame
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from backend.core.dependencies import (
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
)
from backend.main import app


def _make_test_db():
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


def _dummy_jpeg_b64():
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[:, :] = [100, 150, 200]
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode()


class TestWebSocketValidation(unittest.TestCase):
    def setUp(self):
        self.db = _make_test_db()
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)

        app.dependency_overrides[get_session_repo] = lambda: self.session_repo
        app.dependency_overrides[get_telemetry_repo] = lambda: self.telemetry_repo
        app.dependency_overrides[get_result_repo] = lambda: self.result_repo

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        _cleanup_db(self.db)

    def test_ws_no_person_detected_message(self):
        sid = self.session_repo.start_session("P001", "elbow_flexion", side="left")

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_res = MagicMock()
            mock_res.pose_landmarks = None
            mock_inst.process.return_value = mock_res
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_dummy_jpeg_b64())
                msg = ws.receive_json()

                assert msg["type"] == "NO_POSE"
                assert msg["status"] == "NO_PERSON_DETECTED"
                assert "No person detected" in msg["message"]
                assert msg["missing_landmarks"] == []

    def test_ws_missing_landmarks_message(self):
        sid = self.session_repo.start_session("P001", "elbow_flexion", side="left")

        # Missing LEFT_WRIST
        partial_landmarks = {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
        }

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", return_value=partial_landmarks):
            mock_inst = MagicMock()
            mock_res = MagicMock()
            mock_res.pose_landmarks = MagicMock()
            mock_inst.process.return_value = mock_res
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_dummy_jpeg_b64())
                msg = ws.receive_json()

                assert msg["type"] == "NO_POSE"
                assert msg["status"] == "REQUIRED_LANDMARKS_MISSING"
                assert "LEFT_WRIST" in msg["missing_landmarks"]

    def test_ws_low_visibility_message(self):
        sid = self.session_repo.start_session("P001", "elbow_flexion", side="left")

        # Low visibility on LEFT_WRIST (< 0.5)
        low_vis_landmarks = {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST": {"x": 500.0, "y": 500.0, "z": 0.0, "visibility": 0.25},
        }

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", return_value=low_vis_landmarks), \
             patch("backend.routes.analysis.calculate_angle", return_value=90.0):
            mock_inst = MagicMock()
            mock_res = MagicMock()
            mock_res.pose_landmarks = MagicMock()
            mock_inst.process.return_value = mock_res
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_dummy_jpeg_b64())
                msg = ws.receive_json()

                assert msg["type"] == "ANALYSIS_RESULT"
                assert msg["valid_angle"] is None
                assert msg["pose_status"]["is_valid"] is False
                assert msg["pose_status"]["status"] == "LOW_VISIBILITY"
                assert "LEFT_WRIST" in msg["pose_status"]["low_visibility_landmarks"]

    def test_ws_telemetry_not_recorded_on_invalid_frames(self):
        sid = self.session_repo.start_session("P001", "elbow_flexion", side="left")

        low_vis_landmarks = {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.1},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.1},
            "LEFT_WRIST": {"x": 500.0, "y": 500.0, "z": 0.0, "visibility": 0.1},
        }

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", return_value=low_vis_landmarks), \
             patch("backend.routes.analysis.calculate_angle", return_value=90.0):
            mock_inst = MagicMock()
            mock_res = MagicMock()
            mock_res.pose_landmarks = MagicMock()
            mock_inst.process.return_value = mock_res
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                # Send 10 invalid frames (exceeding telemetry interval of 5)
                for _ in range(10):
                    ws.send_text(_dummy_jpeg_b64())
                    ws.receive_json()

                # Verify Frame telemetry count in database is 0
                with self.db.session() as s:
                    count = s.query(Frame).filter_by(session_id=sid).count()
                assert count == 0

    def test_ws_bilateral_right_side_validation(self):
        sid = self.session_repo.start_session("P001", "elbow_flexion", side="right")

        # Right side complete landmarks
        right_landmarks = {
            "RIGHT_SHOULDER": {"x": 700.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
            "RIGHT_ELBOW": {"x": 700.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
            "RIGHT_WRIST": {"x": 900.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
        }

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", return_value=right_landmarks), \
             patch("backend.routes.analysis.calculate_angle", return_value=120.0):
            mock_inst = MagicMock()
            mock_res = MagicMock()
            mock_res.pose_landmarks = MagicMock()
            mock_inst.process.return_value = mock_res
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_dummy_jpeg_b64())
                msg = ws.receive_json()

                assert msg["type"] == "ANALYSIS_RESULT"
                assert msg["pose_status"]["is_valid"] is True
                assert msg["pose_status"]["status"] == "VALID"
                assert msg["valid_angle"] == 120.0

    def test_ws_valid_invalid_valid_continuity(self):
        """
        Validates Requirement:
        VALID -> INVALID -> VALID sequence over live WebSocket preserves:
        - repetition continuity
        - movement state
        - ROM min and max
        - no telemetry persisted on invalid frames
        - seamless recovery when valid frames resume
        """
        sid = self.session_repo.start_session("P001", "elbow_flexion", side="left")

        # Step 1: Valid extended pose (~165 deg)
        ext_landmarks = {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST": {"x": 300.0, "y": 750.0, "z": 0.0, "visibility": 0.99},
        }
        # Step 2: Valid flexed pose (~65 deg)
        flex_landmarks = {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST": {"x": 450.0, "y": 250.0, "z": 0.0, "visibility": 0.99},
        }
        # Step 3: Invalid low-visibility pose
        low_vis_landmarks = {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST": {"x": 450.0, "y": 250.0, "z": 0.0, "visibility": 0.2},
        }

        current_landmarks = [ext_landmarks]
        current_angle = [165.0]

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", side_effect=lambda *args, **kwargs: current_landmarks[0]), \
             patch("backend.routes.analysis.calculate_angle", side_effect=lambda *args, **kwargs: current_angle[0]):

            mock_inst = MagicMock()
            mock_res = MagicMock()
            mock_res.pose_landmarks = True
            mock_inst.process.return_value = mock_res
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                # 1. Stream 5 extended frames to initialize pipeline at ~165 deg
                current_landmarks[0] = ext_landmarks
                current_angle[0] = 165.0
                for _ in range(5):
                    ws.send_text(_dummy_jpeg_b64())
                    msg = ws.receive_json()
                    self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                    self.assertTrue(msg["pose_status"]["is_valid"])

                self.assertEqual(msg["state"], "EXTENDED")
                self.assertIsNotNone(msg["rom"]["max_angle"])
                rom_max_before = msg["rom"]["max_angle"]

                # 2. Stream 5 flexed frames (~65 deg) to flex
                current_landmarks[0] = flex_landmarks
                current_angle[0] = 65.0
                for _ in range(5):
                    ws.send_text(_dummy_jpeg_b64())
                    msg = ws.receive_json()
                    self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                    self.assertTrue(msg["pose_status"]["is_valid"])

                # Snapshot valid state before invalid sequence
                reps_before = msg["repetitions"]
                state_before = msg["state"]
                rom_min_before = msg["rom"]["min_angle"]
                self.assertLess(rom_min_before, 100.0)

                # Count valid telemetry records so far
                with self.db.session() as s:
                    telemetry_count_before = s.query(Frame).filter_by(session_id=sid).count()
                self.assertGreater(telemetry_count_before, 0)

                # 3. Stream 3 NO_PERSON frames (landmarks is None)
                mock_res.pose_landmarks = None
                for _ in range(3):
                    ws.send_text(_dummy_jpeg_b64())
                    msg_np = ws.receive_json()
                    self.assertEqual(msg_np["type"], "NO_POSE")
                    self.assertEqual(msg_np["status"], "NO_PERSON_DETECTED")

                # Stream 3 LOW_VISIBILITY frames
                mock_res.pose_landmarks = True
                current_landmarks[0] = low_vis_landmarks
                current_angle[0] = 65.0
                for _ in range(3):
                    ws.send_text(_dummy_jpeg_b64())
                    msg_lv = ws.receive_json()
                    self.assertEqual(msg_lv["type"], "ANALYSIS_RESULT")
                    self.assertIsNone(msg_lv["valid_angle"])
                    self.assertEqual(msg_lv["pose_status"]["status"], "LOW_VISIBILITY")
                    # Assert state, repetitions, and ROM are preserved
                    self.assertEqual(msg_lv["repetitions"], reps_before)
                    self.assertEqual(msg_lv["state"], state_before)
                    self.assertEqual(msg_lv["rom"]["min_angle"], rom_min_before)
                    self.assertEqual(msg_lv["rom"]["max_angle"], rom_max_before)

                # Assert NO new telemetry rows were created during the 6 invalid frames
                with self.db.session() as s:
                    telemetry_count_after_invalid = s.query(Frame).filter_by(session_id=sid).count()
                self.assertEqual(telemetry_count_after_invalid, telemetry_count_before)

                # 4. Stream 5 VALID extended frames (~165 deg) to complete repetition
                current_landmarks[0] = ext_landmarks
                current_angle[0] = 165.0
                for _ in range(5):
                    ws.send_text(_dummy_jpeg_b64())
                    msg_rec = ws.receive_json()
                    self.assertEqual(msg_rec["type"], "ANALYSIS_RESULT")
                    self.assertTrue(msg_rec["pose_status"]["is_valid"])

                # Verification: repetition counter completed repetition, ROM min remains preserved
                self.assertGreaterEqual(msg_rec["repetitions"], 1)
                self.assertEqual(msg_rec["rom"]["min_angle"], rom_min_before)
                self.assertEqual(msg_rec["state"], "EXTENDED")

    def test_ws_unexpected_disconnect_leaves_session_active(self):
        """
        Validates that when a WebSocket disconnects abruptly (no END_SESSION control message):
        - the session is NOT marked COMPLETED in database
        - session status remains ACTIVE
        - REST /api/sessions/{id}/end remains the sole authoritative completion mechanism
        """
        sid = self.session_repo.start_session("P001", "elbow_flexion", side="left")

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_res = MagicMock()
            mock_res.pose_landmarks = None
            mock_inst.process.return_value = mock_res
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_dummy_jpeg_b64())
                ws.receive_json()
                # WebSocket context exits abruptly (client drop)

        session_record = self.session_repo.get_session(sid)
        self.assertEqual(session_record["status"], "ACTIVE")
