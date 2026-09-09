"""
Phase 4A WebSocket integration tests.

Uses FastAPI TestClient + file-backed SQLite (check_same_thread=False)
since TestClient runs the ASGI app in a worker thread.
No physical camera required.
"""
import base64
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from digital_thread.db import Database
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
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

def _make_file_db():
    """
    File-backed SQLite with check_same_thread=False.
    TestClient runs the ASGI app in a worker thread; SQLite :memory:
    databases are per-connection and not visible across threads.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_url = f"sqlite:///{tmp.name}?check_same_thread=False"
    db = Database(db_url)
    db.create_schema()
    db._test_path = tmp.name  # carry path for cleanup
    return db


def _cleanup_db(db):
    db.engine.dispose()
    try:
        os.remove(db._test_path)
    except OSError:
        pass


def _override(db):
    app.dependency_overrides[get_session_repo] = lambda: SQLAlchemySessionRepository(db)
    app.dependency_overrides[get_telemetry_repo] = lambda: SQLAlchemyTelemetryRepository(db)
    app.dependency_overrides[get_result_repo] = lambda: SQLAlchemyResultRepository(db)


def _clear():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _valid_jpeg_b64() -> str:
    """64x64 solid-colour JPEG as plain base64 string."""
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[:, :] = [80, 160, 200]
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode()


def _corrupt_b64() -> str:
    return base64.b64encode(b"THIS_IS_NOT_A_JPEG").decode()


# ---------------------------------------------------------------------------
# MediaPipe result builders
# ---------------------------------------------------------------------------

def _mp_no_pose():
    r = MagicMock()
    r.pose_landmarks = None
    return r


def _mp_valid_pose():
    """33 landmarks, with realistic LEFT_SHOULDER/ELBOW/WRIST positions."""
    landmarks = []
    for _ in range(33):
        lm = MagicMock()
        lm.x, lm.y, lm.z, lm.visibility = 0.5, 0.5, 0.0, 0.99
        landmarks.append(lm)
    # MediaPipe indices: LEFT_SHOULDER=11, LEFT_ELBOW=13, LEFT_WRIST=15
    landmarks[11].x, landmarks[11].y = 0.3, 0.2
    landmarks[13].x, landmarks[13].y = 0.3, 0.5
    landmarks[15].x, landmarks[15].y = 0.5, 0.5

    r = MagicMock()
    r.pose_landmarks = MagicMock()
    r.pose_landmarks.landmark = landmarks
    return r


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _start_session(db, patient="P_TEST", exercise="elbow_flexion") -> str:
    return SQLAlchemySessionRepository(db).start_session(patient, exercise)


def _complete_session(db, sid: str):
    SQLAlchemySessionRepository(db).end_session(sid)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWebSocket(unittest.TestCase):

    def setUp(self):
        self.db = _make_file_db()
        _override(self.db)
        # raise_server_exceptions=False so WS protocol errors surface as messages
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        _clear()
        _cleanup_db(self.db)

    # -----------------------------------------------------------------------
    # 1. ACTIVE session can connect and receives a valid message
    # -----------------------------------------------------------------------
    def test_01_active_session_connects(self):
        sid = _start_session(self.db)
        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_no_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_valid_jpeg_b64())
                msg = ws.receive_json()

        self.assertIn(msg["type"], {"ANALYSIS_RESULT", "NO_POSE", "ANALYSIS_ERROR"},
                      "Active session must produce a valid WS message type")

    # -----------------------------------------------------------------------
    # 2. Invalid session_id is rejected
    # -----------------------------------------------------------------------
    def test_02_invalid_session_rejected(self):
        with self.client.websocket_connect("/api/analysis/ws/DOES-NOT-EXIST-XYZ") as ws:
            msg = ws.receive_json()

        self.assertEqual(msg["type"], "SESSION_REJECTED")
        self.assertIn("does not exist", msg["message"])

    # -----------------------------------------------------------------------
    # 3. COMPLETED session is rejected
    # -----------------------------------------------------------------------
    def test_03_completed_session_rejected(self):
        sid = _start_session(self.db)
        _complete_session(self.db, sid)

        with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
            msg = ws.receive_json()

        self.assertEqual(msg["type"], "SESSION_REJECTED")
        self.assertIn("not ACTIVE", msg["message"])

    # -----------------------------------------------------------------------
    # 4. Valid JPEG with no-pose returns NO_POSE (no crash)
    # -----------------------------------------------------------------------
    def test_04_valid_image_no_crash(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_no_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_valid_jpeg_b64())
                msg = ws.receive_json()

        self.assertIn(msg["type"], {"NO_POSE", "ANALYSIS_RESULT"})

    # -----------------------------------------------------------------------
    # 5. Corrupt image does NOT crash the connection
    # -----------------------------------------------------------------------
    def test_05_corrupt_image_no_crash(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_no_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                # Send corrupt data first
                ws.send_text(_corrupt_b64())
                err = ws.receive_json()
                self.assertEqual(err["type"], "ANALYSIS_ERROR")

                # Connection is still alive — valid frame works
                ws.send_text(_valid_jpeg_b64())
                msg2 = ws.receive_json()
                self.assertIn(msg2["type"], {"NO_POSE", "ANALYSIS_RESULT"})

    # -----------------------------------------------------------------------
    # 6. No-pose frame returns NO_POSE
    # -----------------------------------------------------------------------
    def test_06_no_pose_returns_no_pose(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_no_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_valid_jpeg_b64())
                msg = ws.receive_json()

        self.assertEqual(msg["type"], "NO_POSE")

    # -----------------------------------------------------------------------
    # 7. No-pose frames do NOT create telemetry rows
    # -----------------------------------------------------------------------
    def test_07_no_pose_no_telemetry(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_no_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(10):
                    ws.send_text(_valid_jpeg_b64())
                    ws.receive_json()

        from digital_thread.models import Frame
        with self.db.session() as s:
            count = s.query(Frame).filter_by(session_id=sid).count()
        self.assertEqual(count, 0, "No-pose frames must NOT produce telemetry rows")

    # -----------------------------------------------------------------------
    # 8. Telemetry is persisted every 5th VALID frame
    # -----------------------------------------------------------------------
    def test_08_telemetry_every_5th_frame(self):
        sid = _start_session(self.db)

        fake_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW":    {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST":    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
        }
        fake_pose_frame = {
            "timestamp": 1.0,
            "angles": {"left_elbow": 120.0},
            "visibility": {},
            "landmarks": fake_landmarks,
        }

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("pose_estimation.landmark_extractor.extract_landmarks",
                   return_value=fake_landmarks), \
             patch("pose_estimation.angle_utils.calculate_angle", return_value=120.0), \
             patch("pose_estimation.pose_output.create_pose_frame",
                   return_value=fake_pose_frame):

            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_valid_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(10):  # 10 valid frames → 2 telemetry writes
                    ws.send_text(_valid_jpeg_b64())
                    ws.receive_json()

        from digital_thread.models import Frame
        with self.db.session() as s:
            count = s.query(Frame).filter_by(session_id=sid).count()
        self.assertEqual(count, 2, f"10 valid frames → 2 telemetry rows (got {count})")

    # -----------------------------------------------------------------------
    # 9. Telemetry does NOT store JPEG/image bytes
    # -----------------------------------------------------------------------
    def test_09_telemetry_no_image_bytes(self):
        sid = _start_session(self.db)

        fake_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW":    {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST":    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
        }
        fake_pose_frame = {
            "timestamp": 1.0,
            "angles": {"left_elbow": 90.0},
            "visibility": {},
            "landmarks": fake_landmarks,
        }

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("pose_estimation.landmark_extractor.extract_landmarks",
                   return_value=fake_landmarks), \
             patch("pose_estimation.angle_utils.calculate_angle", return_value=90.0), \
             patch("pose_estimation.pose_output.create_pose_frame",
                   return_value=fake_pose_frame):

            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_valid_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(5):  # 5 valid frames → 1 telemetry write
                    ws.send_text(_valid_jpeg_b64())
                    ws.receive_json()

        from digital_thread.models import Frame
        with self.db.session() as s:
            frames = s.query(Frame).filter_by(session_id=sid).all()
            for frame in frames:
                raw = json.dumps(frame.landmarks)
                self.assertNotIn("data:image", raw)
                self.assertLess(len(raw), 1024 * 10,
                                "Telemetry landmarks field is suspiciously large (image bytes?)")

    # -----------------------------------------------------------------------
    # 10. END_SESSION uses pipeline.get_current_state()
    # -----------------------------------------------------------------------
    def test_10_end_session_uses_pipeline_state(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_mp.solutions.pose.Pose.return_value = MagicMock()

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                msg = ws.receive_json()

        self.assertEqual(msg["type"], "FINAL_RESULT")
        self.assertIn("repetitions", msg)
        self.assertIn("performance_score", msg)
        self.assertIn("rom_min", msg)
        self.assertIn("rom_max", msg)

    # -----------------------------------------------------------------------
    # 11. Final result is persisted via IResultRepository
    # -----------------------------------------------------------------------
    def test_11_final_result_persisted(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_mp.solutions.pose.Pose.return_value = MagicMock()

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                ws.receive_json()

        result = SQLAlchemyResultRepository(self.db).get_result(sid)
        self.assertIsNotNone(result, "Result must be persisted after END_SESSION")

    # -----------------------------------------------------------------------
    # 12. Repeated finalization is idempotent
    # -----------------------------------------------------------------------
    def test_12_repeated_finalization_idempotent(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_mp.solutions.pose.Pose.return_value = MagicMock()

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                ws.receive_json()

        # Call record_result multiple additional times
        rr = SQLAlchemyResultRepository(self.db)
        rr.record_result(sid, 5, 30.0, 150.0, 90.0, 80.0, "Good")
        rr.record_result(sid, 7, 30.0, 155.0, 92.0, 82.0, "Great")

        from digital_thread.models import Result
        with self.db.session() as s:
            count = s.query(Result).filter_by(session_id=sid).count()
        self.assertEqual(count, 1, "Should remain exactly 1 result row (idempotent)")

    # -----------------------------------------------------------------------
    # 13. END_SESSION WS does NOT mark session COMPLETED
    # -----------------------------------------------------------------------
    def test_13_end_session_ws_not_completed(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_mp.solutions.pose.Pose.return_value = MagicMock()

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                ws.receive_json()

        sess = SQLAlchemySessionRepository(self.db).get_session(sid)
        self.assertEqual(
            sess["status"], "ACTIVE",
            "WebSocket END_SESSION must NOT mark session COMPLETED; only REST /end does that"
        )

    # -----------------------------------------------------------------------
    # 14. REST /sessions/{id}/end marks session COMPLETED
    # -----------------------------------------------------------------------
    def test_14_rest_end_marks_completed(self):
        sid = _start_session(self.db)
        SQLAlchemyResultRepository(self.db).record_result(
            session_id=sid,
            repetitions=5,
            rom_min=45.0,
            rom_max=155.0,
            rom_average=100.0,
            performance_score=85.0,
            feedback="Completed",
        )

        resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp.status_code, 200)

        sess = SQLAlchemySessionRepository(self.db).get_session(sid)
        self.assertEqual(sess["status"], "COMPLETED")

    # -----------------------------------------------------------------------
    # 15. Unexpected disconnect does NOT mark session COMPLETED
    # -----------------------------------------------------------------------
    def test_15_disconnect_not_completed(self):
        sid = _start_session(self.db)

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_no_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_valid_jpeg_b64())
                ws.receive_json()
                # Abrupt close (no END_SESSION)

        sess = SQLAlchemySessionRepository(self.db).get_session(sid)
        self.assertEqual(
            sess["status"], "ACTIVE",
            "Abrupt disconnect must NOT complete the session"
        )

    # -----------------------------------------------------------------------
    # 16. Two simultaneous sessions are isolated
    # -----------------------------------------------------------------------
    def test_16_two_sessions_isolated(self):
        sid_a = _start_session(self.db, "PATIENT_A")
        sid_b = _start_session(self.db, "PATIENT_B")

        fake_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW":    {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST":    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
        }
        fake_pose_frame = {
            "timestamp": 1.0,
            "angles": {"left_elbow": 90.0},
            "visibility": {},
            "landmarks": fake_landmarks,
        }

        landmarks = []
        for _ in range(33):
            lm = MagicMock()
            lm.x, lm.y, lm.z, lm.visibility = 0.5, 0.5, 0.0, 0.99
            landmarks.append(lm)
        landmarks[11].x, landmarks[11].y = 0.3, 0.2
        landmarks[13].x, landmarks[13].y = 0.3, 0.5
        landmarks[15].x, landmarks[15].y = 0.5, 0.5

        r_pose = MagicMock()
        r_pose.pose_landmarks = MagicMock()
        r_pose.pose_landmarks.landmark = landmarks

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("pose_estimation.landmark_extractor.extract_landmarks", return_value=fake_landmarks), \
             patch("pose_estimation.angle_utils.calculate_angle", return_value=90.0), \
             patch("pose_estimation.pose_output.create_pose_frame", return_value=fake_pose_frame):

            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_valid_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            # Open BOTH WebSocket connections concurrently
            with self.client.websocket_connect(f"/api/analysis/ws/{sid_a}") as ws_a, \
                 self.client.websocket_connect(f"/api/analysis/ws/{sid_b}") as ws_b:

                # Send 5 valid frames to session A only (triggers 1 telemetry record)
                for _ in range(5):
                    ws_a.send_text(_valid_jpeg_b64())
                    msg_a = ws_a.receive_json()
                    self.assertEqual(msg_a["type"], "ANALYSIS_RESULT")

                # Send END_SESSION independently to both
                ws_a.send_text(json.dumps({"type": "END_SESSION"}))
                final_a = ws_a.receive_json()

                ws_b.send_text(json.dumps({"type": "END_SESSION"}))
                final_b = ws_b.receive_json()

        # Verify each receives FINAL_RESULT
        self.assertEqual(final_a["type"], "FINAL_RESULT")
        self.assertEqual(final_b["type"], "FINAL_RESULT")

        # Verify FINAL_RESULT.session_id matches its own session
        self.assertEqual(final_a["session_id"], sid_a)
        self.assertEqual(final_b["session_id"], sid_b)
        self.assertNotEqual(sid_a, sid_b)

        # Verify both Result rows belong to the correct session
        from digital_thread.models import Result, Frame
        with self.db.session() as s:
            row_a = s.query(Result).filter_by(session_id=sid_a).first()
            row_b = s.query(Result).filter_by(session_id=sid_b).first()
            frames_a = s.query(Frame).filter_by(session_id=sid_a).count()
            frames_b = s.query(Frame).filter_by(session_id=sid_b).count()

        self.assertIsNotNone(row_a)
        self.assertIsNotNone(row_b)
        self.assertEqual(row_a.session_id, sid_a)
        self.assertEqual(row_b.session_id, sid_b)

        # Verify state/result data from one connection cannot leak into the other
        self.assertEqual(frames_a, 1, "Session A processed 5 valid frames -> 1 telemetry row")
        self.assertEqual(frames_b, 0, "Session B processed 0 frames -> 0 telemetry rows")

        rr = SQLAlchemyResultRepository(self.db)
        self.assertIsNotNone(rr.get_result(sid_a))
        self.assertIsNotNone(rr.get_result(sid_b))


    # -----------------------------------------------------------------------
    # 17. Shoulder flexion session streams and analyzes shoulder angle
    # -----------------------------------------------------------------------
    def test_17_websocket_shoulder_flexion_session(self):
        sid = _start_session(self.db, "PATIENT_SHOULDER", "shoulder_flexion")

        shoulder_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW":    {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST":    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_HIP":      {"x": 0.3, "y": 0.7, "z": 0.0, "visibility": 0.99},
            "LEFT_KNEE":     {"x": 0.3, "y": 0.9, "z": 0.0, "visibility": 0.99},
            "LEFT_ANKLE":    {"x": 0.3, "y": 1.1, "z": 0.0, "visibility": 0.99},
            "RIGHT_SHOULDER":{"x": 0.7, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "RIGHT_ELBOW":   {"x": 0.7, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "RIGHT_WRIST":   {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "RIGHT_HIP":     {"x": 0.7, "y": 0.7, "z": 0.0, "visibility": 0.99},
            "RIGHT_KNEE":    {"x": 0.7, "y": 0.9, "z": 0.0, "visibility": 0.99},
            "RIGHT_ANKLE":   {"x": 0.7, "y": 1.1, "z": 0.0, "visibility": 0.99},
        }
        shoulder_pose_frame = {
            "timestamp": 1.0,
            "angles": {"left_shoulder": 55.0},
            "visibility": {k: 0.99 for k in shoulder_landmarks},
            "landmarks": shoulder_landmarks,
        }

        r_pose = MagicMock()
        r_pose.pose_landmarks = MagicMock()

        with patch("backend.routes.analysis.mp") as mock_mp,              patch("backend.routes.analysis.extract_landmarks", return_value=shoulder_landmarks),              patch("backend.routes.analysis.calculate_angle", return_value=55.0),              patch("backend.routes.analysis.create_pose_frame", return_value=shoulder_pose_frame):

            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_valid_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_valid_jpeg_b64())
                msg = ws.receive_json()
                self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                self.assertEqual(msg["raw_angle"], 55.0)
                self.assertIsNotNone(msg["valid_angle"])
                self.assertEqual(msg["valid_angle"], 55.0)

                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_msg = ws.receive_json()

        self.assertEqual(final_msg["type"], "FINAL_RESULT")
        rr = SQLAlchemyResultRepository(self.db)
        self.assertIsNotNone(rr.get_result(sid))

    # -----------------------------------------------------------------------
    # 18. Knee flexion session streams and records knee telemetry
    # -----------------------------------------------------------------------
    def test_18_websocket_knee_flexion_session(self):
        sid = _start_session(self.db, "PATIENT_KNEE", "knee_flexion")

        knee_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW":    {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST":    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_HIP":      {"x": 0.3, "y": 0.7, "z": 0.0, "visibility": 0.99},
            "LEFT_KNEE":     {"x": 0.3, "y": 0.9, "z": 0.0, "visibility": 0.99},
            "LEFT_ANKLE":    {"x": 0.3, "y": 1.1, "z": 0.0, "visibility": 0.99},
            "RIGHT_SHOULDER":{"x": 0.7, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "RIGHT_ELBOW":   {"x": 0.7, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "RIGHT_WRIST":   {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "RIGHT_HIP":     {"x": 0.7, "y": 0.7, "z": 0.0, "visibility": 0.99},
            "RIGHT_KNEE":    {"x": 0.7, "y": 0.9, "z": 0.0, "visibility": 0.99},
            "RIGHT_ANKLE":   {"x": 0.7, "y": 1.1, "z": 0.0, "visibility": 0.99},
        }
        knee_pose_frame = {
            "timestamp": 1.0,
            "angles": {"left_knee": 115.0},
            "visibility": {k: 0.99 for k in knee_landmarks},
            "landmarks": knee_landmarks,
        }

        r_pose = MagicMock()
        r_pose.pose_landmarks = MagicMock()

        with patch("backend.routes.analysis.mp") as mock_mp,              patch("backend.routes.analysis.extract_landmarks", return_value=knee_landmarks),              patch("backend.routes.analysis.calculate_angle", return_value=115.0),              patch("backend.routes.analysis.create_pose_frame", return_value=knee_pose_frame):

            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_valid_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(5):
                    ws.send_text(_valid_jpeg_b64())
                    msg = ws.receive_json()
                    self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                    self.assertEqual(msg["raw_angle"], 115.0)
                    self.assertIsNotNone(msg["valid_angle"])
                    self.assertEqual(msg["valid_angle"], 115.0)

                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_msg = ws.receive_json()

        self.assertEqual(final_msg["type"], "FINAL_RESULT")

        # Verify knee telemetry was recorded with left_knee angle
        from digital_thread.models import Frame
        with self.db.session() as s:
            frames = s.query(Frame).filter_by(session_id=sid).all()
            self.assertEqual(len(frames), 1)
            self.assertEqual(frames[0].joint_angles.get("left_knee"), 115.0)

    # -----------------------------------------------------------------------
    # 19. Final result scoring uses exercise_def.target_rom
    # -----------------------------------------------------------------------
    def test_19_websocket_scoring_uses_target_rom(self):
        # Shoulder flexion target ROM is 160.0 degrees
        sid_shoulder = _start_session(self.db, "P_SHOULDER", "shoulder_flexion")
        # Elbow flexion target ROM is 130.0 degrees
        sid_elbow = _start_session(self.db, "P_ELBOW", "elbow_flexion")

        # Mock get_current_state to return avg ROM of 80.0
        mock_state = {
            "repetitions": 1,
            "rom": {"min_angle": 60.0, "max_angle": 100.0},
            "state": "HOLDING_FLEXION",
        }

        with patch("backend.routes.analysis.mp") as mock_mp,              patch("rehabilitation.analysis_pipeline.GenericAnalysisPipeline.get_current_state", return_value=mock_state):
            mock_mp.solutions.pose.Pose.return_value = MagicMock()

            # rom_average remains the midpoint: (60.0 + 100.0) / 2 = 80.0
            # rom_excursion = 100.0 - 60.0 = 40.0
            # Shoulder: 40.0 / 160.0 * 100 = 25.0%
            with self.client.websocket_connect(f"/api/analysis/ws/{sid_shoulder}") as ws:
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_shoulder = ws.receive_json()

            # Elbow: 40.0 / 130.0 * 100 = 30.769...%
            with self.client.websocket_connect(f"/api/analysis/ws/{sid_elbow}") as ws:
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_elbow = ws.receive_json()

        # Verify rom_average remains the midpoint
        self.assertEqual(final_shoulder["rom_average"], 80.0)
        self.assertEqual(final_elbow["rom_average"], 80.0)

        # Verify performance_score uses excursion
        self.assertAlmostEqual(final_shoulder["performance_score"], 25.0, places=1)
        self.assertAlmostEqual(final_elbow["performance_score"], 30.8, places=1)
        self.assertNotEqual(final_shoulder["performance_score"], final_elbow["performance_score"])

    # -----------------------------------------------------------------------
    # 20. Unknown exercise in session is rejected with code 4004
    # -----------------------------------------------------------------------
    def test_20_websocket_unknown_exercise_rejected(self):
        # Insert session with unknown exercise directly into repository
        sid = _start_session(self.db, "P_UNKNOWN", "unsupported_squat")

        with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
            msg = ws.receive_json()

        self.assertEqual(msg["type"], "SESSION_REJECTED")
        self.assertIn("Unsupported exercise", msg["message"])

    # -----------------------------------------------------------------------
    # 21. Simultaneous sessions with different exercises are completely isolated
    # -----------------------------------------------------------------------
    def test_21_simultaneous_different_exercise_sessions(self):
        sid_elbow = _start_session(self.db, "P_ELBOW", "elbow_flexion")
        sid_shoulder = _start_session(self.db, "P_SHOULDER", "shoulder_flexion")

        elbow_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW":    {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST":    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_HIP":      {"x": 0.3, "y": 0.7, "z": 0.0, "visibility": 0.99},
            "LEFT_KNEE":     {"x": 0.3, "y": 0.9, "z": 0.0, "visibility": 0.99},
            "LEFT_ANKLE":    {"x": 0.3, "y": 1.1, "z": 0.0, "visibility": 0.99},
            "RIGHT_SHOULDER":{"x": 0.7, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "RIGHT_ELBOW":   {"x": 0.7, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "RIGHT_WRIST":   {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "RIGHT_HIP":     {"x": 0.7, "y": 0.7, "z": 0.0, "visibility": 0.99},
            "RIGHT_KNEE":    {"x": 0.7, "y": 0.9, "z": 0.0, "visibility": 0.99},
            "RIGHT_ANKLE":   {"x": 0.7, "y": 1.1, "z": 0.0, "visibility": 0.99},
        }

        r_pose = MagicMock()
        r_pose.pose_landmarks = MagicMock()

        current_elbow_angle = [165.0]
        current_shoulder_angle = [50.0]

        def mock_calc_angle(p1, p2, p3):
            if p2 == elbow_landmarks["LEFT_SHOULDER"]:
                return current_shoulder_angle[0]
            return current_elbow_angle[0]

        def mock_create_pose(lm, angles):
            return {
                "timestamp": 1.0,
                "angles": angles,
                "visibility": {k: v.get("visibility", 0.99) for k, v in lm.items()},
                "landmarks": lm,
            }

        with patch("backend.routes.analysis.mp") as mock_mp,              patch("backend.routes.analysis.extract_landmarks", return_value=elbow_landmarks),              patch("backend.routes.analysis.calculate_angle", side_effect=mock_calc_angle),              patch("backend.routes.analysis.create_pose_frame", side_effect=mock_create_pose):

            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_valid_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid_elbow}") as ws_e,                  self.client.websocket_connect(f"/api/analysis/ws/{sid_shoulder}") as ws_s:

                # Frame 1: Extended position (165 deg) - pipeline state transitions from UNKNOWN to EXTENDED
                ws_e.send_text(_valid_jpeg_b64())
                msg_e1 = ws_e.receive_json()
                self.assertEqual(msg_e1["type"], "ANALYSIS_RESULT")
                self.assertEqual(msg_e1["raw_angle"], 165.0)
                self.assertIsNotNone(msg_e1["valid_angle"])
                self.assertEqual(msg_e1["valid_angle"], 165.0)
                self.assertEqual(msg_e1["state"], "EXTENDED")
                self.assertIsNotNone(msg_e1["rom"].get("min_angle"))

                # Frames 2-5: Flexing position (95 deg) - ROM updates and telemetry triggered on frame 5
                current_elbow_angle[0] = 95.0
                for _ in range(4):
                    ws_e.send_text(_valid_jpeg_b64())
                    msg_e = ws_e.receive_json()
                    self.assertEqual(msg_e["type"], "ANALYSIS_RESULT")
                    self.assertEqual(msg_e["raw_angle"], 95.0)
                    self.assertIsNotNone(msg_e["valid_angle"])
                    self.assertEqual(msg_e["valid_angle"], 95.0)

                self.assertLess(msg_e["rom"]["min_angle"], 165.0)
                self.assertGreater(msg_e["rom"]["rom"], 0.0)

                # Shoulder Frame 1: Extended position at rest (50 deg)
                ws_s.send_text(_valid_jpeg_b64())
                msg_s1 = ws_s.receive_json()
                self.assertEqual(msg_s1["type"], "ANALYSIS_RESULT")
                self.assertEqual(msg_s1["raw_angle"], 50.0)
                self.assertIsNotNone(msg_s1["valid_angle"])
                self.assertEqual(msg_s1["valid_angle"], 50.0)
                self.assertEqual(msg_s1["state"], "EXTENDED")
                self.assertIsNotNone(msg_s1["rom"].get("min_angle"))

                # Shoulder Frames 2-6: Raising arm overhead (165 deg) to saturate 5-frame moving average
                current_shoulder_angle[0] = 165.0
                for _ in range(5):
                    ws_s.send_text(_valid_jpeg_b64())
                    msg_s = ws_s.receive_json()
                    self.assertEqual(msg_s["type"], "ANALYSIS_RESULT")
                    self.assertEqual(msg_s["raw_angle"], 165.0)
                    self.assertIsNotNone(msg_s["valid_angle"])
                    self.assertEqual(msg_s["valid_angle"], 165.0)

                self.assertLess(msg_s["rom"]["min_angle"], 165.0)
                self.assertGreater(msg_s["rom"]["rom"], 0.0)

                ws_e.send_text(json.dumps({"type": "END_SESSION"}))
                final_e = ws_e.receive_json()

                ws_s.send_text(json.dumps({"type": "END_SESSION"}))
                final_s = ws_s.receive_json()

        self.assertEqual(final_e["type"], "FINAL_RESULT")
        self.assertEqual(final_s["type"], "FINAL_RESULT")
        self.assertEqual(final_e["session_id"], sid_elbow)
        self.assertEqual(final_s["session_id"], sid_shoulder)
        self.assertIsNotNone(final_e["rom_min"])
        self.assertIsNotNone(final_s["rom_min"])
        self.assertEqual(final_e["rom_max"], 165.0)
        self.assertEqual(final_s["rom_max"], 165.0)

        from digital_thread.models import Frame
        with self.db.session() as s:
            frames_e = s.query(Frame).filter_by(session_id=sid_elbow).all()
            frames_s = s.query(Frame).filter_by(session_id=sid_shoulder).all()
            self.assertEqual(len(frames_e), 1)
            self.assertEqual(len(frames_s), 1)
            self.assertIn("left_elbow", frames_e[0].joint_angles)
            self.assertEqual(frames_e[0].joint_angles["left_elbow"], 95.0)
            self.assertIn("left_shoulder", frames_s[0].joint_angles)
            self.assertEqual(frames_s[0].joint_angles["left_shoulder"], 165.0)

        from digital_thread.models import Result
        with self.db.session() as s:
            res_row_e = s.query(Result).filter_by(session_id=sid_elbow).first()
            res_row_s = s.query(Result).filter_by(session_id=sid_shoulder).first()
            self.assertIsNotNone(res_row_e)
            self.assertIsNotNone(res_row_s)
            self.assertEqual(res_row_e.session_id, sid_elbow)
            self.assertEqual(res_row_s.session_id, sid_shoulder)

        rr = SQLAlchemyResultRepository(self.db)
        res_e = rr.get_result(sid_elbow)
        res_s = rr.get_result(sid_shoulder)
        self.assertIsNotNone(res_e)
        self.assertIsNotNone(res_s)
        self.assertEqual(res_e["exercise"], "elbow_flexion")
        self.assertEqual(res_s["exercise"], "shoulder_flexion")


    # -----------------------------------------------------------------------
    # 22. Low-visibility frames do NOT advance valid_frame_count or write telemetry
    # -----------------------------------------------------------------------
    def test_22_websocket_low_visibility_not_counted_as_valid_telemetry(self):
        sid = _start_session(self.db, "P_LOW_VIS", "elbow_flexion")

        # Landmarks where visibility is below 0.5 (e.g. 0.2)
        low_vis_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.2},
            "LEFT_ELBOW":    {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.2},
            "LEFT_WRIST":    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.2},
            "LEFT_HIP":      {"x": 0.3, "y": 0.7, "z": 0.0, "visibility": 0.2},
            "LEFT_KNEE":     {"x": 0.3, "y": 0.9, "z": 0.0, "visibility": 0.2},
            "LEFT_ANKLE":    {"x": 0.3, "y": 1.1, "z": 0.0, "visibility": 0.2},
            "RIGHT_SHOULDER":{"x": 0.7, "y": 0.2, "z": 0.0, "visibility": 0.2},
            "RIGHT_ELBOW":   {"x": 0.7, "y": 0.5, "z": 0.0, "visibility": 0.2},
            "RIGHT_WRIST":   {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.2},
            "RIGHT_HIP":     {"x": 0.7, "y": 0.7, "z": 0.0, "visibility": 0.2},
            "RIGHT_KNEE":    {"x": 0.7, "y": 0.9, "z": 0.0, "visibility": 0.2},
            "RIGHT_ANKLE":   {"x": 0.7, "y": 1.1, "z": 0.0, "visibility": 0.2},
        }

        # Landmarks where visibility is high (0.99)
        high_vis_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW":    {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST":    {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_HIP":      {"x": 0.3, "y": 0.7, "z": 0.0, "visibility": 0.99},
            "LEFT_KNEE":     {"x": 0.3, "y": 0.9, "z": 0.0, "visibility": 0.99},
            "LEFT_ANKLE":    {"x": 0.3, "y": 1.1, "z": 0.0, "visibility": 0.99},
            "RIGHT_SHOULDER":{"x": 0.7, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "RIGHT_ELBOW":   {"x": 0.7, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "RIGHT_WRIST":   {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "RIGHT_HIP":     {"x": 0.7, "y": 0.7, "z": 0.0, "visibility": 0.99},
            "RIGHT_KNEE":    {"x": 0.7, "y": 0.9, "z": 0.0, "visibility": 0.99},
            "RIGHT_ANKLE":   {"x": 0.7, "y": 1.1, "z": 0.0, "visibility": 0.99},
        }

        current_landmarks = [low_vis_landmarks]

        def mock_extract(mp_res, w, h):
            return current_landmarks[0]

        def mock_create(lm, angles):
            return {
                "timestamp": 1.0,
                "angles": angles,
                "visibility": {k: v.get("visibility", 0.0) for k, v in lm.items()},
                "landmarks": lm,
            }

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", side_effect=mock_extract), \
             patch("backend.routes.analysis.calculate_angle", return_value=120.0), \
             patch("backend.routes.analysis.create_pose_frame", side_effect=mock_create):

            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_valid_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                # 1. Send 6 frames with low visibility (< 0.5)
                # This exceeds the 5-frame telemetry threshold IF invalid frames were counted.
                current_landmarks[0] = low_vis_landmarks
                for _ in range(6):
                    ws.send_text(_valid_jpeg_b64())
                    msg = ws.receive_json()
                    self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                    self.assertIsNone(msg["valid_angle"], "Low visibility must yield valid_angle=None")

                # Verify NO telemetry was recorded in database despite 6 frames sent
                from digital_thread.models import Frame
                with self.db.session() as s:
                    count_after_low_vis = s.query(Frame).filter_by(session_id=sid).count()
                self.assertEqual(count_after_low_vis, 0, "Low-visibility frames must NOT trigger telemetry persistence")

                # 2. Now switch to high-visibility frames (>= 0.5)
                # Send 4 valid frames -> valid_frame_count = 4 (still no telemetry)
                current_landmarks[0] = high_vis_landmarks
                for _ in range(4):
                    ws.send_text(_valid_jpeg_b64())
                    msg = ws.receive_json()
                    self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                    self.assertIsNotNone(msg["valid_angle"], "High visibility must yield valid_angle")

                with self.db.session() as s:
                    count_after_4_valid = s.query(Frame).filter_by(session_id=sid).count()
                self.assertEqual(count_after_4_valid, 0, "4 valid frames must not trigger 1:5 telemetry yet")

                # 3. Send 5th valid frame -> valid_frame_count = 5 -> triggers telemetry persistence!
                ws.send_text(_valid_jpeg_b64())
                msg = ws.receive_json()
                self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                self.assertIsNotNone(msg["valid_angle"])

                with self.db.session() as s:
                    count_after_5th_valid = s.query(Frame).filter_by(session_id=sid).count()
                self.assertEqual(count_after_5th_valid, 1, "Exactly 1 telemetry row should exist after 5th VALID frame")

                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_msg = ws.receive_json()
                self.assertEqual(final_msg["type"], "FINAL_RESULT")


if __name__ == "__main__":
    unittest.main()
