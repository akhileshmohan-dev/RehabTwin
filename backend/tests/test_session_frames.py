"""
Tests for the replay frames endpoint (GET /api/sessions/{id}/frames) and the
env-configurable telemetry persistence density.

Covers: frame ordering, coordinate normalization, unknown-session 404,
empty sessions, default every-frame persistence, and density overrides.
"""
import base64
import os
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from digital_thread.db import Database
from digital_thread.models import Patient, utc_now
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from backend.core.dependencies import (
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
    get_patient_repo,
    get_assignment_repo,
)
from backend.main import app
from backend.routes.analysis import _telemetry_every_n_valid


def _make_file_db() -> Database:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = Database(f"sqlite:///{tmp.name}?check_same_thread=False")
    db.create_schema()
    db._test_path = tmp.name
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
    app.dependency_overrides[get_patient_repo] = lambda: SQLAlchemyPatientRepository(db)
    app.dependency_overrides[get_assignment_repo] = lambda: MagicMock()


def _valid_jpeg_b64() -> str:
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[:, :] = [80, 160, 200]
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode()


def _start_session(db, patient="P_FRAMES", exercise="elbow_flexion") -> str:
    with db.session() as s:
        if not s.query(Patient).filter(Patient.patient_id == patient).first():
            s.add(Patient(patient_id=patient, name=f"Patient {patient}", status="ACTIVE"))
            s.commit()
    return SQLAlchemySessionRepository(db).start_session(patient, exercise)


# ---------------------------------------------------------------------------
# Helper: env parsing
# ---------------------------------------------------------------------------

def test_helper_density_defaults_to_one(monkeypatch):
    monkeypatch.delenv("TELEMETRY_EVERY_N_VALID", raising=False)
    assert _telemetry_every_n_valid() == 1


def test_helper_density_reads_env(monkeypatch):
    monkeypatch.setenv("TELEMETRY_EVERY_N_VALID", "3")
    assert _telemetry_every_n_valid() == 3


def test_helper_density_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("TELEMETRY_EVERY_N_VALID", "not-a-number")
    assert _telemetry_every_n_valid() == 1


def test_helper_density_floors_at_one(monkeypatch):
    monkeypatch.setenv("TELEMETRY_EVERY_N_VALID", "0")
    assert _telemetry_every_n_valid() == 1


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestSessionFramesEndpoint(unittest.TestCase):

    def setUp(self):
        self.db = _make_file_db()
        _override(self.db)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)

    def tearDown(self):
        app.dependency_overrides.clear()
        _cleanup_db(self.db)

    def _record(self, sid, frame_id, timestamp, landmarks):
        self.telemetry_repo.record_frame(
            session_id=sid,
            frame_id=frame_id,
            landmarks=landmarks,
            joint_angles={"left_elbow": 120.0},
            phase="EXTENDED",
            timestamp=timestamp,
            image_width=640,
            image_height=480,
        )

    def test_order_normalization_and_timestamps(self):
        sid = _start_session(self.db)
        base = utc_now()
        self._record(sid, 2, base + timedelta(milliseconds=200), {"NOSE": {"x": 128.0, "y": 96.0, "z": 0.1, "visibility": 0.9}})
        self._record(sid, 1, base, {"NOSE": {"x": 320.0, "y": 240.0, "z": 0.0, "visibility": 0.99}})

        resp = self.client.get(f"/api/sessions/{sid}/frames")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        self.assertEqual(body["session_id"], sid)
        self.assertEqual(body["exercise"], "elbow_flexion")
        self.assertEqual(body["side"], "left")
        self.assertEqual(body["image_width"], 640)
        self.assertEqual(body["image_height"], 480)
        self.assertEqual(body["frame_count"], 2)

        # Ordered by frame_id ascending despite out-of-order insertion
        self.assertEqual([f["frame_id"] for f in body["frames"]], [1, 2])
        self.assertEqual(body["frames"][0]["t_ms"], 0.0)
        self.assertEqual(body["frames"][1]["t_ms"], 200.0)

        # Pixel -> normalized; z and visibility preserved
        nose0 = body["frames"][0]["landmarks"]["NOSE"]
        self.assertAlmostEqual(nose0["x"], 0.5, places=4)
        self.assertAlmostEqual(nose0["y"], 0.5, places=4)
        self.assertEqual(nose0["z"], 0.0)
        self.assertEqual(nose0["visibility"], 0.99)

        nose1 = body["frames"][1]["landmarks"]["NOSE"]
        self.assertAlmostEqual(nose1["x"], 0.2, places=4)
        self.assertAlmostEqual(nose1["y"], 0.2, places=4)

    def test_unknown_session_returns_404(self):
        resp = self.client.get("/api/sessions/DOES-NOT-EXIST/frames")
        self.assertEqual(resp.status_code, 404)

    def test_empty_session_returns_zero_frames(self):
        sid = _start_session(self.db)
        resp = self.client.get(f"/api/sessions/{sid}/frames")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["frame_count"], 0)
        self.assertEqual(body["frames"], [])
        self.assertIsNone(body["image_width"])
        self.assertIsNone(body["image_height"])


# ---------------------------------------------------------------------------
# WebSocket persistence density
# ---------------------------------------------------------------------------

def _mp_valid_pose():
    landmarks = []
    for _ in range(33):
        lm = MagicMock()
        lm.x, lm.y, lm.z, lm.visibility = 0.5, 0.5, 0.0, 0.99
        landmarks.append(lm)
    landmarks[11].x, landmarks[11].y = 0.3, 0.2
    landmarks[13].x, landmarks[13].y = 0.3, 0.5
    landmarks[15].x, landmarks[15].y = 0.5, 0.5
    r = MagicMock()
    r.pose_landmarks = MagicMock()
    r.pose_landmarks.landmark = landmarks
    return r


class TestTelemetryDensity(unittest.TestCase):

    def setUp(self):
        self.db = _make_file_db()
        _override(self.db)
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        _cleanup_db(self.db)

    def _stream(self, sid, n_frames):
        fake_landmarks = {
            "LEFT_SHOULDER": {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.99},
            "LEFT_WRIST": {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99},
        }
        fake_pose_frame = {
            "timestamp": 1.0,
            "angles": {"left_elbow": 120.0},
            "visibility": {},
            "landmarks": fake_landmarks,
        }
        with patch("backend.routes.analysis.mp") as mock_mp, \
             patch("backend.routes.analysis.extract_landmarks", return_value=fake_landmarks), \
             patch("backend.routes.analysis.calculate_angle", return_value=120.0), \
             patch("backend.routes.analysis.create_pose_frame", return_value=fake_pose_frame):
            mock_inst = MagicMock()
            mock_inst.process.return_value = _mp_valid_pose()
            mock_mp.solutions.pose.Pose.return_value = mock_inst
            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(n_frames):
                    ws.send_text(_valid_jpeg_b64())
                    ws.receive_json()

    def test_default_persists_every_valid_frame(self):
        sid = _start_session(self.db, "P_DEFAULT")
        with patch.dict(os.environ, {"TELEMETRY_EVERY_N_VALID": "1"}):
            self._stream(sid, 5)
        frames = SQLAlchemyTelemetryRepository(self.db).list_frames(sid)
        self.assertEqual(len(frames), 5)
        self.assertEqual([f["frame_id"] for f in frames], [1, 2, 3, 4, 5])
        # Dimensions captured from the analysed frame
        self.assertEqual(frames[0]["image_width"], 64)
        self.assertEqual(frames[0]["image_height"], 64)

    def test_env_override_downsamples(self):
        sid = _start_session(self.db, "P_DOWN")
        with patch.dict(os.environ, {"TELEMETRY_EVERY_N_VALID": "2"}):
            self._stream(sid, 6)
        frames = SQLAlchemyTelemetryRepository(self.db).list_frames(sid)
        self.assertEqual(len(frames), 3)
        self.assertEqual([f["frame_id"] for f in frames], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
