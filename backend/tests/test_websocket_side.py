"""
WebSocket bilateral side and session isolation tests for Phase 5A.
Validates:
- WebSocket initializes pipeline using the persisted session side from SQLite.
- WebSocket computes actual right-side joint angles (e.g. right_elbow) from right landmarks.
- Mismatched frame side cannot override session side.
- Simultaneous left/right sessions run concurrently in complete isolation.
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


MOCK_BILATERAL_LANDMARKS = {
    # Left arm (forms exactly 90 degrees)
    "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
    "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
    "LEFT_WRIST": {"x": 500.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
    # Right arm (forms ~120 degrees)
    "RIGHT_SHOULDER": {"x": 700.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
    "RIGHT_ELBOW": {"x": 700.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
    "RIGHT_WRIST": {"x": 950.0, "y": 650.0, "z": 0.0, "visibility": 0.99},
}


class TestWebSocketBilateralSide(unittest.TestCase):
    def setUp(self):
        self.db = _make_test_db()
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)

        app.dependency_overrides[get_session_repo] = lambda: self.session_repo
        app.dependency_overrides[get_telemetry_repo] = lambda: self.telemetry_repo
        app.dependency_overrides[get_result_repo] = lambda: self.result_repo

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        _cleanup_db(self.db)

    def test_websocket_processes_right_side_session(self):
        # Create a right-sided session
        sid = self.session_repo.start_session(
            patient_id="PATIENT-RIGHT",
            exercise="elbow_flexion",
            side="right",
            session_id="S-RIGHT-WS"
        )

        mock_pose_result = MagicMock()
        mock_pose_result.pose_landmarks = True

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", return_value=MOCK_BILATERAL_LANDMARKS):

            mock_inst = MagicMock()
            mock_inst.process.return_value = mock_pose_result
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                # Send a frame
                ws.send_text(_dummy_jpeg_b64())
                msg = ws.receive_json()

                self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                self.assertEqual(msg["session_id"], sid)
                self.assertIsNotNone(msg["raw_angle"])
                # Right arm angle ~120 degrees
                self.assertAlmostEqual(msg["raw_angle"], 120.0, delta=5.0)

                # End session to trigger result persistence
                ws.send_json({"type": "END_SESSION"})
                final_msg = ws.receive_json()
                self.assertEqual(final_msg["type"], "FINAL_RESULT")

        # Verify persisted result in DB has side='right'
        persisted_res = self.result_repo.get_result(sid)
        self.assertIsNotNone(persisted_res)
        self.assertEqual(persisted_res["side"], "right")

    def test_simultaneous_left_and_right_sessions_isolated(self):
        # Create two concurrent sessions: one left, one right
        sid_left = self.session_repo.start_session(
            patient_id="P-LEFT",
            exercise="elbow_flexion",
            side="left",
            session_id="S-CONCURRENT-LEFT"
        )
        sid_right = self.session_repo.start_session(
            patient_id="P-RIGHT",
            exercise="elbow_flexion",
            side="right",
            session_id="S-CONCURRENT-RIGHT"
        )

        mock_pose_result = MagicMock()
        mock_pose_result.pose_landmarks = True

        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", return_value=MOCK_BILATERAL_LANDMARKS):

            mock_inst = MagicMock()
            mock_inst.process.return_value = mock_pose_result
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid_left}") as ws_left:
                with self.client.websocket_connect(f"/api/analysis/ws/{sid_right}") as ws_right:
                    # Stream 5 interleaved frames to both concurrent sessions
                    for _ in range(5):
                        ws_left.send_text(_dummy_jpeg_b64())
                        left_res = ws_left.receive_json()
                        self.assertEqual(left_res["type"], "ANALYSIS_RESULT")
                        self.assertEqual(left_res["session_id"], sid_left)
                        # ~90 deg for left
                        self.assertAlmostEqual(left_res["raw_angle"], 90.0, delta=2.0)

                        ws_right.send_text(_dummy_jpeg_b64())
                        right_res = ws_right.receive_json()
                        self.assertEqual(right_res["type"], "ANALYSIS_RESULT")
                        self.assertEqual(right_res["session_id"], sid_right)
                        # ~120 deg for right
                        self.assertAlmostEqual(right_res["raw_angle"], 120.0, delta=5.0)

                        # Assert the two angles are distinct and evaluated independently
                        self.assertNotEqual(left_res["raw_angle"], right_res["raw_angle"])

                    # End both sessions
                    ws_left.send_json({"type": "END_SESSION"})
                    ws_right.send_json({"type": "END_SESSION"})

                    final_left = ws_left.receive_json()
                    final_right = ws_right.receive_json()
                    self.assertEqual(final_left["type"], "FINAL_RESULT")
                    self.assertEqual(final_right["type"], "FINAL_RESULT")

        # Verify DB side persistence
        res_left = self.result_repo.get_result(sid_left)
        res_right = self.result_repo.get_result(sid_right)
        self.assertEqual(res_left["side"], "left")
        self.assertEqual(res_right["side"], "right")

    def test_process_frame_rejects_conflicting_side_with_http_400(self):
        sid = self.session_repo.start_session(
            patient_id="P-VAL",
            exercise="elbow_flexion",
            side="left",
            session_id="S-VAL-SIDE"
        )

        pose_frame = {
            "timestamp": 1.0,
            "angles": {"left_elbow": 90.0},
            "landmarks": {},
            "visibility": {},
        }

        # Attempt to process frame claiming side="right" on a left session
        resp = self.client.post("/api/analysis/process-frame", json={
            "session_id": sid,
            "exercise_id": "elbow_flexion",
            "side": "right",
            "pose_frame": pose_frame,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Requested side 'right' does not match session side 'left'", resp.json()["detail"])

        # Matching side succeeds
        resp_ok = self.client.post("/api/analysis/process-frame", json={
            "session_id": sid,
            "exercise_id": "elbow_flexion",
            "side": "left",
            "pose_frame": pose_frame,
        })
        self.assertEqual(resp_ok.status_code, 200)


if __name__ == "__main__":
    unittest.main()
