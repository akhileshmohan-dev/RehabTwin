"""
Phase 5D Test Suite: Session Completion & Results Isolation.

Covers:
1. Normal WS END_SESSION -> FINAL_RESULT -> WebSocket termination -> REST /end
2. ACTIVE session with NO result ended safely (returns result=None, COMPLETED, no fake metrics)
3. Repeated REST /end idempotency (preserves original ended_at timestamp and result)
4. Repeated record_result idempotency (updates in place, no duplicate rows)
5. Independent repeated finalization attempts for the same session
6. Explicit result mapping to SessionResultData (handles None safely, no accidental coercion)
7. Session ID isolation:
   - Patient A vs Patient B
   - Left vs Right
   - Different exercises
8. Nonexistent session /end returns HTTP 404
9. Cannot record frames or results to COMPLETED session (HTTP 400)
10. WS connection to COMPLETED session rejected (code 4003)
11. Pipeline state integrity: final result captures complete in-memory pipeline state (not downsampled telemetry)
12. Phase 4C excursion-based scoring formula and feedback validation
"""
import base64
import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from digital_thread.db import Database
from backend.core.dependencies import (
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
    get_patient_repo,
)
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
    SQLAlchemyPatientRepository,
)
from backend.schemas.session import (
    StartSessionRequest,
    RecordResultRequest,
    EndSessionResponse,
    SessionResultData,
)


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


def _valid_jpeg_b64() -> str:
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[:, :] = [80, 160, 200]
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode()


def _mp_pose_with_angles(angle_deg: float, side: str = "left"):
    """
    Produce a mock MediaPipe Pose result with landmark positions yielding
    the specified elbow angle.
    """
    landmarks = []
    for _ in range(33):
        lm = MagicMock()
        lm.x, lm.y, lm.z, lm.visibility = 0.5, 0.5, 0.0, 0.99
        landmarks.append(lm)

    # Convert angle to radians
    rad = np.radians(angle_deg)
    # Shoulder at (0.3, 0.2), Elbow at (0.3, 0.5), Wrist rotated
    sh_idx = 11 if side == "left" else 12
    el_idx = 13 if side == "left" else 14
    wr_idx = 15 if side == "left" else 16

    landmarks[sh_idx].x, landmarks[sh_idx].y = 0.3, 0.2
    landmarks[el_idx].x, landmarks[el_idx].y = 0.3, 0.5
    # Wrist relative to elbow:
    landmarks[wr_idx].x = 0.3 + 0.3 * np.sin(rad)
    landmarks[wr_idx].y = 0.5 - 0.3 * np.cos(rad)

    r = MagicMock()
    r.pose_landmarks = MagicMock()
    r.pose_landmarks.landmark = landmarks
    return r


class TestSessionCompletionPhase5D(unittest.TestCase):

    def setUp(self):
        self.db = _make_file_db()
        app.dependency_overrides[get_session_repo] = lambda: SQLAlchemySessionRepository(self.db)
        app.dependency_overrides[get_telemetry_repo] = lambda: SQLAlchemyTelemetryRepository(self.db)
        app.dependency_overrides[get_result_repo] = lambda: SQLAlchemyResultRepository(self.db)
        app.dependency_overrides[get_patient_repo] = lambda: SQLAlchemyPatientRepository(self.db)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)
        self.patient_repo = SQLAlchemyPatientRepository(self.db)

    def tearDown(self):
        app.dependency_overrides.clear()
        _cleanup_db(self.db)

    # -----------------------------------------------------------------------
    # 1. Normal WS END_SESSION -> FINAL_RESULT -> WS Close -> REST /end
    # -----------------------------------------------------------------------
    def test_01_normal_ws_end_session_and_rest_completion(self):
        """
        Verify normal completion:
        WS END_SESSION -> FINAL_RESULT -> socket closes -> REST /end marks COMPLETED.
        """
        sid = self.session_repo.start_session("PATIENT-001", "elbow_flexion", side="left")
        b64 = _valid_jpeg_b64()

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_mp.solutions.pose.Pose.return_value = mock_inst
            mock_inst.process.return_value = _mp_pose_with_angles(90.0, "left")

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                # Send 2 frames
                ws.send_text(b64)
                msg1 = ws.receive_json()
                self.assertEqual(msg1["type"], "ANALYSIS_RESULT")

                ws.send_text(b64)
                msg2 = ws.receive_json()
                self.assertEqual(msg2["type"], "ANALYSIS_RESULT")

                # Send END_SESSION
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_msg = ws.receive_json()

                self.assertEqual(final_msg["type"], "FINAL_RESULT")
                self.assertEqual(final_msg["session_id"], sid)
                self.assertIn("repetitions", final_msg)
                self.assertIn("performance_score", final_msg)

        # Before REST /end, session in DB must still be ACTIVE
        sess_before = self.session_repo.get_session(sid)
        self.assertEqual(sess_before["status"], "ACTIVE")

        # Result was already persisted by END_SESSION handler
        res_before = self.result_repo.get_result(sid)
        self.assertIsNotNone(res_before)
        self.assertEqual(res_before["side"], "left")
        self.assertEqual(res_before["exercise"], "elbow_flexion")

        # Now call authoritative REST /end
        resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["session_id"], sid)
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIsNotNone(data["result"])
        self.assertEqual(data["result"]["exercise"], "elbow_flexion")
        self.assertEqual(data["result"]["side"], "left")
        self.assertEqual(data["result"]["repetitions"], final_msg["repetitions"])
        self.assertEqual(data["result"]["performance_score"], final_msg["performance_score"])

        # Verify DB session is now COMPLETED
        sess_after = self.session_repo.get_session(sid)
        self.assertEqual(sess_after["status"], "COMPLETED")
        self.assertIsNotNone(sess_after["ended_at"])

    # -----------------------------------------------------------------------
    # 2. ACTIVE session with NO result ended safely
    # -----------------------------------------------------------------------
    def test_02_active_session_no_result_ended_safely(self):
        """
        Verify that an ACTIVE session without any recorded results cannot be ended via REST /end.
        It must return a controlled 4xx error (400 Bad Request), remain ACTIVE, and NOT
        create or fabricate a Result row or default metrics.
        """
        sid = self.session_repo.start_session("PATIENT-NO-RES", "elbow_flexion", side="left")

        # Verify no result exists yet
        self.assertIsNone(self.result_repo.get_result(sid))

        # Call REST /end -> must return 400
        resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("cannot be ended because no result has been recorded", data["detail"])

        # Verify in DB: status remains ACTIVE, ended_at is None, and NO result row was inserted
        sess = self.session_repo.get_session(sid)
        self.assertEqual(sess["status"], "ACTIVE")
        self.assertIsNone(sess["ended_at"])
        self.assertIsNone(self.result_repo.get_result(sid))

    # -----------------------------------------------------------------------
    # 3. Repeated REST /end idempotency (preserves original ended_at)
    # -----------------------------------------------------------------------
    def test_03_repeated_rest_end_preserves_original_timestamp(self):
        """
        Calling POST /api/sessions/{id}/end repeatedly must be idempotent, return 200,
        and preserve the original ended_at timestamp.
        """
        sid = self.session_repo.start_session("PATIENT-001", "elbow_flexion", side="right")
        self.result_repo.record_result(
            session_id=sid,
            repetitions=5,
            rom_min=40.0,
            rom_max=150.0,
            rom_average=95.0,
            performance_score=85.0,
            feedback="Good effort",
        )

        # First /end
        resp1 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp1.status_code, 200)
        first_ended_at = self.session_repo.get_session(sid)["ended_at"]
        self.assertIsNotNone(first_ended_at)

        time.sleep(0.01)

        # Second /end
        resp2 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp2.status_code, 200)
        second_ended_at = self.session_repo.get_session(sid)["ended_at"]

        # Timestamp must be preserved exactly
        self.assertEqual(first_ended_at, second_ended_at)
        self.assertEqual(resp2.json()["status"], "COMPLETED")
        self.assertEqual(resp2.json()["result"]["repetitions"], 5)
        self.assertEqual(resp2.json()["result"]["side"], "right")

    # -----------------------------------------------------------------------
    # 4. Repeated record_result updates in place (no duplicates)
    # -----------------------------------------------------------------------
    def test_04_repeated_record_result_updates_in_place(self):
        """
        Calling record_result multiple times for the same session must update
        the row in place without violating unique constraints or creating duplicates.
        """
        sid = self.session_repo.start_session("PATIENT-001", "elbow_flexion", side="left")

        # Initial result
        self.result_repo.record_result(
            session_id=sid,
            repetitions=3,
            rom_min=50.0,
            rom_max=120.0,
            rom_average=85.0,
            performance_score=60.0,
            feedback="Initial",
        )
        r1 = self.result_repo.get_result(sid)
        self.assertEqual(r1["repetitions"], 3)
        self.assertEqual(r1["performance_score"], 60.0)

        # Updated result
        self.result_repo.record_result(
            session_id=sid,
            repetitions=10,
            rom_min=30.0,
            rom_max=165.0,
            rom_average=97.5,
            performance_score=95.0,
            feedback="Completed full set",
        )
        r2 = self.result_repo.get_result(sid)
        self.assertEqual(r2["repetitions"], 10)
        self.assertEqual(r2["performance_score"], 95.0)
        self.assertEqual(r2["feedback"], "Completed full set")

    # -----------------------------------------------------------------------
    # 5. Independent repeated finalization attempts for the same session
    # -----------------------------------------------------------------------
    def test_05_independent_repeated_finalization_attempts(self):
        """
        Independent finalization attempts (e.g. WS finalization followed by multiple
        REST /end requests) succeed idempotently without error.
        """
        sid = self.session_repo.start_session("PATIENT-001", "knee_flexion", side="right")
        b64 = _valid_jpeg_b64()

        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_mp.solutions.pose.Pose.return_value = mock_inst
            mock_inst.process.return_value = _mp_pose_with_angles(110.0, "right")

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(b64)
                ws.receive_json()
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                ws_res = ws.receive_json()
                self.assertEqual(ws_res["type"], "FINAL_RESULT")

        # First REST /end
        r1 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(r1.status_code, 200)

        # Second REST /end
        r2 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(r2.status_code, 200)

        # Third REST /end
        r3 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(r3.status_code, 200)

        self.assertEqual(r1.json()["result"], r3.json()["result"])

    # -----------------------------------------------------------------------
    # 6. Explicit Result Mapping & Type Safety
    # -----------------------------------------------------------------------
    def test_06_explicit_result_mapping_structure(self):
        """
        Verify that EndSessionResponse.result is explicitly typed as SessionResultData
        with all required and optional fields correctly mapped.
        """
        sid = self.session_repo.start_session("PATIENT-MAPPING", "shoulder_flexion", side="left")
        self.result_repo.record_result(
            session_id=sid,
            repetitions=7,
            rom_min=20.0,
            rom_max=170.0,
            rom_average=95.0,
            performance_score=92.5,
            feedback="7 repetition(s) completed. Average ROM: 95.0 deg. Excellent range of motion.",
        )

        resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp.status_code, 200)
        res_data = resp.json()["result"]

        self.assertIsInstance(res_data["exercise"], str)
        self.assertEqual(res_data["exercise"], "shoulder_flexion")
        self.assertEqual(res_data["side"], "left")
        self.assertEqual(res_data["repetitions"], 7)
        self.assertEqual(res_data["rom_min"], 20.0)
        self.assertEqual(res_data["rom_max"], 170.0)
        self.assertEqual(res_data["rom_average"], 95.0)
        self.assertEqual(res_data["performance_score"], 92.5)
        self.assertIn("Excellent range of motion", res_data["feedback"])

    # -----------------------------------------------------------------------
    # 7. Session ID Isolation: Patient A vs Patient B
    # -----------------------------------------------------------------------
    def test_07_isolation_patient_a_vs_patient_b(self):
        """
        Final results for Patient A and Patient B cannot cross-populate.
        """
        sid_a = self.session_repo.start_session("PATIENT-AAA", "elbow_flexion", side="left")
        sid_b = self.session_repo.start_session("PATIENT-BBB", "elbow_flexion", side="left")

        self.result_repo.record_result(
            session_id=sid_a,
            repetitions=6,
            rom_min=45.0,
            rom_max=155.0,
            rom_average=100.0,
            performance_score=80.0,
            feedback="Patient A feedback",
        )
        self.result_repo.record_result(
            session_id=sid_b,
            repetitions=14,
            rom_min=35.0,
            rom_max=165.0,
            rom_average=100.0,
            performance_score=95.0,
            feedback="Patient B feedback",
        )

        res_a = self.client.post(f"/api/sessions/{sid_a}/end").json()["result"]
        res_b = self.client.post(f"/api/sessions/{sid_b}/end").json()["result"]

        self.assertEqual(res_a["repetitions"], 6)
        self.assertEqual(res_a["performance_score"], 80.0)
        self.assertEqual(res_a["feedback"], "Patient A feedback")

        self.assertEqual(res_b["repetitions"], 14)
        self.assertEqual(res_b["performance_score"], 95.0)
        self.assertEqual(res_b["feedback"], "Patient B feedback")

        # Verify patient histories in repository
        hist_a = self.patient_repo.get_patient_history("PATIENT-AAA")
        hist_b = self.patient_repo.get_patient_history("PATIENT-BBB")

        self.assertEqual(len(hist_a), 1)
        self.assertEqual(len(hist_b), 1)
        self.assertEqual(hist_a[0]["session_id"], sid_a)
        self.assertEqual(hist_b[0]["session_id"], sid_b)
        self.assertEqual(hist_a[0]["results"][0]["repetitions"], 6)
        self.assertEqual(hist_b[0]["results"][0]["repetitions"], 14)

    # -----------------------------------------------------------------------
    # 8. Session ID Isolation: Left vs Right
    # -----------------------------------------------------------------------
    def test_08_isolation_left_vs_right_sides(self):
        """
        Left and right side sessions for the same patient remain isolated.
        """
        sid_l = self.session_repo.start_session("PATIENT-BILATERAL", "elbow_flexion", side="left")
        sid_r = self.session_repo.start_session("PATIENT-BILATERAL", "elbow_flexion", side="right")

        self.result_repo.record_result(
            session_id=sid_l,
            repetitions=4,
            rom_min=50.0,
            rom_max=140.0,
            rom_average=95.0,
            performance_score=70.0,
            feedback="Left side session",
        )
        self.result_repo.record_result(
            session_id=sid_r,
            repetitions=11,
            rom_min=30.0,
            rom_max=165.0,
            rom_average=97.5,
            performance_score=98.0,
            feedback="Right side session",
        )

        res_l = self.client.post(f"/api/sessions/{sid_l}/end").json()["result"]
        res_r = self.client.post(f"/api/sessions/{sid_r}/end").json()["result"]

        self.assertEqual(res_l["side"], "left")
        self.assertEqual(res_l["repetitions"], 4)
        self.assertEqual(res_l["performance_score"], 70.0)

        self.assertEqual(res_r["side"], "right")
        self.assertEqual(res_r["repetitions"], 11)
        self.assertEqual(res_r["performance_score"], 98.0)

    # -----------------------------------------------------------------------
    # 9. Session ID Isolation: Different Exercises
    # -----------------------------------------------------------------------
    def test_09_isolation_different_exercises(self):
        """
        Sessions with different exercises remain strictly isolated.
        """
        sid_e1 = self.session_repo.start_session("PATIENT-MULTI", "elbow_flexion", side="left")
        sid_e2 = self.session_repo.start_session("PATIENT-MULTI", "shoulder_abduction", side="left")

        self.result_repo.record_result(
            session_id=sid_e1,
            repetitions=5,
            rom_min=40.0,
            rom_max=150.0,
            rom_average=95.0,
            performance_score=85.0,
        )
        self.result_repo.record_result(
            session_id=sid_e2,
            repetitions=8,
            rom_min=20.0,
            rom_max=160.0,
            rom_average=90.0,
            performance_score=90.0,
        )

        res_e1 = self.client.post(f"/api/sessions/{sid_e1}/end").json()["result"]
        res_e2 = self.client.post(f"/api/sessions/{sid_e2}/end").json()["result"]

        self.assertEqual(res_e1["exercise"], "elbow_flexion")
        self.assertEqual(res_e1["repetitions"], 5)

        self.assertEqual(res_e2["exercise"], "shoulder_abduction")
        self.assertEqual(res_e2["repetitions"], 8)

    # -----------------------------------------------------------------------
    # 10. Nonexistent session returns HTTP 404
    # -----------------------------------------------------------------------
    def test_10_end_nonexistent_session_returns_404(self):
        resp = self.client.post("/api/sessions/NON-EXISTENT-SESSION-ID/end")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("does not exist", resp.json()["detail"])

    # -----------------------------------------------------------------------
    # 11. Cannot record frames or results to COMPLETED session
    # -----------------------------------------------------------------------
    def test_11_cannot_record_to_completed_session(self):
        sid = self.session_repo.start_session("PATIENT-001", "elbow_flexion", side="left")
        self.result_repo.record_result(
            session_id=sid,
            repetitions=2,
            rom_min=50.0,
            rom_max=140.0,
            rom_average=95.0,
            performance_score=80.0,
        )
        end_res = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(end_res.status_code, 200)

        # Attempt to record frame
        frame_payload = {
            "frame_id": 1,
            "landmarks": {"LEFT_ELBOW": {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}},
            "joint_angles": {"left_elbow": 90.0},
            "phase": "FLEXED",
        }
        resp_f = self.client.post(f"/api/sessions/{sid}/frames", json=frame_payload)
        self.assertEqual(resp_f.status_code, 400)
        self.assertIn("not ACTIVE", resp_f.json()["detail"])

        # Attempt to record result
        result_payload = {
            "repetitions": 5,
            "rom_min": 40.0,
            "rom_max": 150.0,
            "rom_average": 95.0,
            "performance_score": 85.0,
        }
        resp_r = self.client.post(f"/api/sessions/{sid}/results", json=result_payload)
        self.assertEqual(resp_r.status_code, 400)
        self.assertIn("not ACTIVE", resp_r.json()["detail"])

    # -----------------------------------------------------------------------
    # 12. WebSocket connection to COMPLETED session is rejected
    # -----------------------------------------------------------------------
    def test_12_ws_connection_to_completed_session_rejected(self):
        sid = self.session_repo.start_session("PATIENT-001", "elbow_flexion", side="left")
        self.result_repo.record_result(
            session_id=sid,
            repetitions=2,
            rom_min=50.0,
            rom_max=140.0,
            rom_average=95.0,
            performance_score=80.0,
        )
        end_res = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(end_res.status_code, 200)

        with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
            msg = ws.receive_json()
            self.assertEqual(msg["type"], "SESSION_REJECTED")
            self.assertIn("COMPLETED", msg["message"])

    # -----------------------------------------------------------------------
    # 13. Pipeline state integrity: final result uses in-memory pipeline state
    # -----------------------------------------------------------------------
    def test_13_pipeline_state_integrity_vs_telemetry_downsampling(self):
        """
        Verify that final result uses the complete in-memory pipeline state,
        not the downsampled telemetry frames (~1 every 5 valid frames).
        """
        sid = self.session_repo.start_session("PATIENT-FULL-STATE", "elbow_flexion", side="left")
        b64 = _valid_jpeg_b64()

        # Stream 8 valid frames: min angle 40, max angle 140
        # Telemetry will only record frame 5 (valid_frame_count % 5 == 0)
        # Send 5 frames at 40.0 and 5 frames at 140.0 (10 frames total)
        # to ensure moving average smoothing window reaches full excursion.
        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(5):
                    mock_inst.process.return_value = _mp_pose_with_angles(40.0, "left")
                    ws.send_text(b64)
                    ws.receive_json()

                for _ in range(5):
                    mock_inst.process.return_value = _mp_pose_with_angles(140.0, "left")
                    ws.send_text(b64)
                    ws.receive_json()

                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_res = ws.receive_json()
                self.assertEqual(final_res["type"], "FINAL_RESULT")

        # Telemetry should only have 2 frames (10 valid frames // 5 = 2 persisted frames)
        with self.db.session() as db_session:
            from digital_thread.models import Frame
            telemetry_count = db_session.query(Frame).filter_by(session_id=sid).count()
            self.assertEqual(telemetry_count, 2)

        # But final result must reflect the full min=40 and max=140 from the complete in-memory pipeline!
        end_resp = self.client.post(f"/api/sessions/{sid}/end").json()
        result = end_resp["result"]
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["rom_min"], 40.0, places=1)
        self.assertAlmostEqual(result["rom_max"], 140.0, places=1)
        self.assertAlmostEqual(result["rom_average"], 90.0, places=1)

    # -----------------------------------------------------------------------
    # 14. Phase 4C Excursion-Based Scoring Formula Validation
    # -----------------------------------------------------------------------
    def test_14_excursion_scoring_formula_validation(self):
        """
        Validate Phase 4C scoring calculation:
        excursion = rom_max - rom_min
        score = min(100.0, max(0.0, (excursion / target_rom) * 100.0))
        elbow_flexion target_rom is 130.0 deg.
        """
        sid = self.session_repo.start_session("PATIENT-SCORE", "elbow_flexion", side="left")
        b64 = _valid_jpeg_b64()

        # Send 5 frames at 30.0 and 5 frames at 160.0 -> excursion = 130.0 -> score = 100.0%
        with patch("backend.routes.analysis.mp") as mock_mp:
            mock_inst = MagicMock()
            mock_mp.solutions.pose.Pose.return_value = mock_inst

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(5):
                    mock_inst.process.return_value = _mp_pose_with_angles(30.0, "left")
                    ws.send_text(b64)
                    ws.receive_json()

                for _ in range(5):
                    mock_inst.process.return_value = _mp_pose_with_angles(160.0, "left")
                    ws.send_text(b64)
                    ws.receive_json()

                ws.send_text(json.dumps({"type": "END_SESSION"}))
                ws_res = ws.receive_json()

        resp = self.client.post(f"/api/sessions/{sid}/end")
        res = resp.json()["result"]
        self.assertAlmostEqual(res["performance_score"], 100.0, places=1)
        self.assertIn("Excellent range of motion", res["feedback"])
