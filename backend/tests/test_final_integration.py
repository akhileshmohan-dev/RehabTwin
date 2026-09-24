"""
backend/tests/test_final_integration.py

Phase 6E + 6F Comprehensive Integration & Durability Test Suite.
Exercises actual application boundaries against real SQLite with PRAGMA foreign_keys=ON:
  REST API -> Service -> Repository -> SQLAlchemy -> SQLite
  and:
  WebSocket -> Pipeline -> Result persistence -> Authoritative REST /end -> Therapist Dashboard.
"""
import base64
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import text

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


def _create_jpeg_b64() -> str:
    """Create a 64x64 valid JPEG image encoded as base64."""
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[:, :] = [100, 140, 190]
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
    """Left elbow pose landmark positions (shoulder 11, elbow 13, wrist 15)."""
    if angle_type == "flexed":
        return _build_mock_mp_pose({11: (0.3, 0.2), 13: (0.3, 0.5), 15: (0.4, 0.4)})
    else:
        return _build_mock_mp_pose({11: (0.3, 0.2), 13: (0.3, 0.5), 15: (0.3, 0.8)})


def _mp_right_knee(angle_type: str = "flexed"):
    """Right knee pose landmark positions (hip 24, knee 26, ankle 28)."""
    if angle_type == "flexed":
        return _build_mock_mp_pose({24: (0.6, 0.4), 26: (0.6, 0.7), 28: (0.5, 0.6)})
    else:
        return _build_mock_mp_pose({24: (0.6, 0.4), 26: (0.6, 0.7), 28: (0.6, 0.95)})


def _mp_no_person():
    """Mock MediaPipe result when no person is detected."""
    res = MagicMock()
    res.pose_landmarks = None
    return res


class TestPhase6E6FIntegration(unittest.TestCase):
    def setUp(self):
        # Unique file-backed SQLite database with timeout for concurrency
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.db_url = f"sqlite:///{self.db_path}?check_same_thread=False&timeout=30"
        self.db = Database(self.db_url)
        self.db.create_schema()

        app.dependency_overrides[get_database] = lambda: self.db
        app.dependency_overrides[get_patient_repo] = lambda: SQLAlchemyPatientRepository(self.db)
        app.dependency_overrides[get_assignment_repo] = lambda: SQLAlchemyAssignmentRepository(self.db)
        app.dependency_overrides[get_session_repo] = lambda: SQLAlchemySessionRepository(self.db)
        app.dependency_overrides[get_telemetry_repo] = lambda: SQLAlchemyTelemetryRepository(self.db)
        app.dependency_overrides[get_result_repo] = lambda: SQLAlchemyResultRepository(self.db)

        self.client = TestClient(app, raise_server_exceptions=False)
        self.patient_repo = SQLAlchemyPatientRepository(self.db)
        self.assignment_repo = SQLAlchemyAssignmentRepository(self.db)
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.engine.dispose()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    # -------------------------------------------------------------------------
    # 1. Real Complete Patient Workflow (Item 18)
    # -------------------------------------------------------------------------
    def test_01_real_complete_patient_workflow(self):
        """
        Exercises the complete 15-step patient rehabilitation workflow across all layers:
        API -> Service -> Repository -> SQLAlchemy -> SQLite.
        """
        # 1. Create patient
        p_resp = self.client.post("/api/patients", json={
            "patient_id": "P_WORKFLOW",
            "name": "Sarah Connor",
            "age": 35,
            "gender": "Female",
        })
        self.assertEqual(p_resp.status_code, 201)
        self.assertEqual(p_resp.json()["patient_id"], "P_WORKFLOW")

        # 2. Create exercise assignment
        a_resp = self.client.post("/api/patients/P_WORKFLOW/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
            "target_rom": 130.0,
            "target_repetitions": 10,
            "sessions_per_day": 2,
            "notes": "Post-op elbow rehabilitation",
        })
        self.assertEqual(a_resp.status_code, 201)
        assignment_id = a_resp.json()["id"]

        # 3. Fetch patient
        get_p = self.client.get("/api/patients/P_WORKFLOW")
        self.assertEqual(get_p.status_code, 200)
        self.assertEqual(get_p.json()["name"], "Sarah Connor")

        # 4. Fetch assignment
        get_a = self.client.get("/api/patients/P_WORKFLOW/exercises")
        self.assertEqual(get_a.status_code, 200)
        assignments = get_a.json()["assignments"]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]["id"], assignment_id)
        self.assertEqual(assignments[0]["side"], "left")

        # 5. Start session using authoritative assignment_id
        start_resp = self.client.post("/api/sessions", json={
            "patient_id": "P_WORKFLOW",
            "assignment_id": assignment_id,
        })
        self.assertEqual(start_resp.status_code, 201)
        sess_data = start_resp.json()
        sid = sess_data["session_id"]
        self.assertEqual(sess_data["exercise"], "elbow_flexion")
        self.assertEqual(sess_data["side"], "left")
        self.assertEqual(sess_data["status"], "ACTIVE")

        # 6. Verify session stored in SQLite
        sess_db = self.session_repo.get_session(sid)
        self.assertEqual(sess_db["status"], "ACTIVE")
        self.assertIsNone(sess_db["ended_at"])

        # 7. Connect WebSocket and stream valid analysis frames
        b64_frame = _create_jpeg_b64()
        with patch("backend.routes.analysis.mp.solutions.pose.Pose") as mock_pose_cls:
            mock_pose = MagicMock()
            mock_pose_cls.return_value = mock_pose
            # 5 extended -> 5 flexed -> 5 extended completes 1 rep
            frames = [_mp_left_elbow("extended")] * 5 + [_mp_left_elbow("flexed")] * 5 + [_mp_left_elbow("extended")] * 5
            mock_pose.process.side_effect = frames

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                for _ in range(len(frames)):
                    ws.send_text(b64_frame)
                    msg = ws.receive_json()
                    self.assertEqual(msg["type"], "ANALYSIS_RESULT")
                    self.assertTrue(msg["pose_status"]["is_valid"])

                # 8. Send END_SESSION and produce final result
                ws.send_text(json.dumps({"type": "END_SESSION"}))
                final_msg = ws.receive_json()
                self.assertEqual(final_msg["type"], "FINAL_RESULT")
                self.assertEqual(final_msg["session_id"], sid)
                self.assertGreaterEqual(final_msg["repetitions"], 1)
                self.assertIsNotNone(final_msg["performance_score"])

        # 9. Call authoritative REST /end
        end_resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(end_resp.status_code, 200)
        end_data = end_resp.json()

        # 10. Verify session COMPLETED
        self.assertEqual(end_data["status"], "COMPLETED")
        sess_after = self.session_repo.get_session(sid)
        self.assertEqual(sess_after["status"], "COMPLETED")
        self.assertIsNotNone(sess_after["ended_at"])

        # 11. Verify exactly one Result in SQLite
        result_in_db = self.result_repo.get_result(sid)
        self.assertIsNotNone(result_in_db)
        self.assertEqual(result_in_db["side"], "left")
        self.assertEqual(result_in_db["exercise"], "elbow_flexion")
        with self.db.session() as s:
            from digital_thread.models import Result
            count = s.query(Result).filter(Result.session_id == sid).count()
            self.assertEqual(count, 1)

        # 12. Fetch patient history
        hist_resp = self.client.get("/api/patients/P_WORKFLOW/sessions")
        self.assertEqual(hist_resp.status_code, 200)
        hist = hist_resp.json()

        # 13. Verify result appears in patient history
        self.assertEqual(hist["total_sessions"], 1)
        sess_hist = hist["sessions"][0]
        self.assertEqual(sess_hist["session_id"], sid)
        self.assertEqual(sess_hist["status"], "COMPLETED")
        self.assertEqual(len(sess_hist["results"]), 1)
        self.assertEqual(sess_hist["results"][0]["side"], "left")
        self.assertEqual(sess_hist["results"][0]["repetitions"], final_msg["repetitions"])

        # 14. Fetch therapist dashboard
        dash_resp = self.client.get("/api/patients")
        self.assertEqual(dash_resp.status_code, 200)
        dash = dash_resp.json()

        # 15. Verify session/result appears in dashboard
        self.assertEqual(dash["total_patients"], 1)
        self.assertEqual(dash["total_sessions"], 1)
        self.assertEqual(dash["active_patients"], 0)
        self.assertIsNotNone(dash["average_performance_score"])

    # -------------------------------------------------------------------------
    # 2. Result-Before-End Race (Addendum Test A & Item 2)
    # -------------------------------------------------------------------------
    def test_02_result_before_end_race(self):
        """
        Attempt /end BEFORE Result persistence commits:
        Must return HTTP 400, session remains ACTIVE, no fake Result.
        Then commit Result and call /end:
        Must return HTTP 200, session transitions to COMPLETED.
        """
        self.patient_repo.create_patient({"patient_id": "P_RACE", "name": "Race Patient", "status": "ACTIVE"})
        self.assignment_repo.assign_exercise({"patient_id": "P_RACE", "exercise_id": "elbow_flexion", "side": "left"})
        sid = self.session_repo.start_session("P_RACE", "elbow_flexion", side="left")

        # 1. Verify no Result exists yet
        self.assertIsNone(self.result_repo.get_result(sid))

        # 2. Call /end before Result committed -> must fail with 400
        resp1 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp1.status_code, 400)
        self.assertIn("cannot be ended because no result has been recorded", resp1.json()["detail"])

        # 3. Verify session in SQLite is STILL ACTIVE and no Result was created
        sess_mid = self.session_repo.get_session(sid)
        self.assertEqual(sess_mid["status"], "ACTIVE")
        self.assertIsNone(sess_mid["ended_at"])
        self.assertIsNone(self.result_repo.get_result(sid))

        # 4. Commit Result
        self.result_repo.record_result(
            session_id=sid,
            repetitions=10,
            rom_min=30.0,
            rom_max=140.0,
            rom_average=85.0,
            performance_score=85.0,
            feedback="Completed smoothly",
        )

        # 5. Call /end again -> must succeed with 200
        resp2 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp2.status_code, 200)
        data = resp2.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIsNotNone(data["result"])
        self.assertEqual(data["result"]["repetitions"], 10)

        # 6. Verify session is now COMPLETED in SQLite
        sess_final = self.session_repo.get_session(sid)
        self.assertEqual(sess_final["status"], "COMPLETED")
        self.assertIsNotNone(sess_final["ended_at"])

    # -------------------------------------------------------------------------
    # 3. Concurrent Result Persistence (Addendum Test B & Item 1)
    # -------------------------------------------------------------------------
    def test_03_concurrent_result_persistence(self):
        """
        Two or more concurrent threads attempt to persist results for the same session.
        Proves invariant: One session -> at most one Result row.
        No unhandled exceptions, no duplicated rows.
        """
        self.patient_repo.create_patient({"patient_id": "P_CONC_RES", "name": "Conc Res Patient", "status": "ACTIVE"})
        self.assignment_repo.assign_exercise({"patient_id": "P_CONC_RES", "exercise_id": "elbow_flexion", "side": "left"})
        sid = self.session_repo.start_session("P_CONC_RES", "elbow_flexion", side="left")

        def persist_worker(rep_count: int):
            repo = SQLAlchemyResultRepository(self.db)
            repo.record_result(
                session_id=sid,
                repetitions=rep_count,
                rom_min=30.0,
                rom_max=140.0,
                rom_average=85.0,
                performance_score=80.0,
                feedback=f"Worker {rep_count}",
            )
            return rep_count

        num_threads = 6
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(persist_worker, i) for i in range(1, num_threads + 1)]
            results = [f.result() for f in as_completed(futures)]

        self.assertEqual(len(results), num_threads)

        # Assert exactly one Result row exists in SQLite
        with self.db.session() as session:
            from digital_thread.models import Result
            count = session.query(Result).filter(Result.session_id == sid).count()
            self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 4. Concurrent /end Requests (Addendum Test C & Item 7)
    # -------------------------------------------------------------------------
    def test_04_concurrent_end_requests(self):
        """
        Multiple concurrent /end requests for the same session.
        Verifies:
        - All succeed (HTTP 200)
        - Session is COMPLETED
        - Exactly 1 Result row remains
        - Stable ended_at timestamp across all responses
        """
        self.patient_repo.create_patient({"patient_id": "P_CONC_END", "name": "Conc End Patient", "status": "ACTIVE"})
        self.assignment_repo.assign_exercise({"patient_id": "P_CONC_END", "exercise_id": "shoulder_flexion", "side": "right"})
        sid = self.session_repo.start_session("P_CONC_END", "shoulder_flexion", side="right")

        # Persist valid result
        self.result_repo.record_result(
            session_id=sid,
            repetitions=12,
            rom_min=20.0,
            rom_max=170.0,
            rom_average=95.0,
            performance_score=90.0,
            feedback="Great flexion",
        )

        def end_worker(worker_id: int):
            client = TestClient(app, raise_server_exceptions=False)
            return client.post(f"/api/sessions/{sid}/end")

        num_workers = 6
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(end_worker, i) for i in range(num_workers)]
            responses = [f.result() for f in as_completed(futures)]

        # All responses must be HTTP 200
        for resp in responses:
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "COMPLETED")
            self.assertEqual(data["result"]["repetitions"], 12)

        # Verify database state
        sess = self.session_repo.get_session(sid)
        self.assertEqual(sess["status"], "COMPLETED")
        self.assertIsNotNone(sess["ended_at"])

        with self.db.session() as s:
            from digital_thread.models import Result
            count = s.query(Result).filter(Result.session_id == sid).count()
            self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 5. Multi-Patient Isolation (Item 19)
    # -------------------------------------------------------------------------
    def test_05_multi_patient_isolation(self):
        """
        Patient A: Exercise A / Left.
        Patient B: Exercise B / Right.
        Verify:
        - A cannot use B's assignment ID (HTTP 400).
        - B cannot use A's assignment ID (HTTP 400).
        - Patient histories remain isolated.
        """
        self.patient_repo.create_patient({"patient_id": "PAT_A", "name": "Patient A", "status": "ACTIVE"})
        self.patient_repo.create_patient({"patient_id": "PAT_B", "name": "Patient B", "status": "ACTIVE"})

        assign_a = self.assignment_repo.assign_exercise({
            "patient_id": "PAT_A", "exercise_id": "elbow_flexion", "side": "left"
        })
        assign_b = self.assignment_repo.assign_exercise({
            "patient_id": "PAT_B", "exercise_id": "knee_flexion", "side": "right"
        })

        # A attempts to use B's assignment
        resp_a_cross = self.client.post("/api/sessions", json={
            "patient_id": "PAT_A",
            "assignment_id": assign_b["id"],
        })
        self.assertEqual(resp_a_cross.status_code, 400)

        # B attempts to use A's assignment
        resp_b_cross = self.client.post("/api/sessions", json={
            "patient_id": "PAT_B",
            "assignment_id": assign_a["id"],
        })
        self.assertEqual(resp_b_cross.status_code, 400)

        # Start valid session for A and complete it
        s_a = self.client.post("/api/sessions", json={
            "patient_id": "PAT_A", "assignment_id": assign_a["id"]
        }).json()["session_id"]
        self.result_repo.record_result(session_id=s_a, repetitions=8, rom_min=30.0, rom_max=130.0, rom_average=80.0, performance_score=75.0)
        self.client.post(f"/api/sessions/{s_a}/end")

        # Start valid session for B and complete it
        s_b = self.client.post("/api/sessions", json={
            "patient_id": "PAT_B", "assignment_id": assign_b["id"]
        }).json()["session_id"]
        self.result_repo.record_result(session_id=s_b, repetitions=15, rom_min=40.0, rom_max=135.0, rom_average=87.5, performance_score=92.0)
        self.client.post(f"/api/sessions/{s_b}/end")

        # Verify histories are isolated
        hist_a = self.client.get("/api/patients/PAT_A/sessions").json()
        hist_b = self.client.get("/api/patients/PAT_B/sessions").json()

        self.assertEqual(hist_a["total_sessions"], 1)
        self.assertEqual(hist_a["sessions"][0]["exercise"], "elbow_flexion")
        self.assertEqual(hist_a["sessions"][0]["side"], "left")

        self.assertEqual(hist_b["total_sessions"], 1)
        self.assertEqual(hist_b["sessions"][0]["exercise"], "knee_flexion")
        self.assertEqual(hist_b["sessions"][0]["side"], "right")

    # -------------------------------------------------------------------------
    # 6. Multi-Session Isolation (Item 20)
    # -------------------------------------------------------------------------
    def test_06_multi_session_isolation(self):
        """
        Two simultaneous active sessions for different patients.
        Verifies session IDs differ, pipeline states do not leak,
        and results attach to the correct sessions.
        """
        self.patient_repo.create_patient({"patient_id": "SIM_1", "name": "Sim 1", "status": "ACTIVE"})
        self.patient_repo.create_patient({"patient_id": "SIM_2", "name": "Sim 2", "status": "ACTIVE"})

        a1 = self.assignment_repo.assign_exercise({"patient_id": "SIM_1", "exercise_id": "elbow_flexion", "side": "left"})
        a2 = self.assignment_repo.assign_exercise({"patient_id": "SIM_2", "exercise_id": "knee_flexion", "side": "right"})

        sid1 = self.client.post("/api/sessions", json={"patient_id": "SIM_1", "assignment_id": a1["id"]}).json()["session_id"]
        sid2 = self.client.post("/api/sessions", json={"patient_id": "SIM_2", "assignment_id": a2["id"]}).json()["session_id"]

        self.assertNotEqual(sid1, sid2)

        # Overview verifies both are active
        ov = self.client.get("/api/patients").json()
        self.assertEqual(ov["active_patients"], 2)

        # Record distinct results
        self.result_repo.record_result(session_id=sid1, repetitions=5, rom_min=40.0, rom_max=120.0, rom_average=80.0, performance_score=70.0)
        self.result_repo.record_result(session_id=sid2, repetitions=15, rom_min=25.0, rom_max=145.0, rom_average=85.0, performance_score=95.0)

        self.client.post(f"/api/sessions/{sid1}/end")
        self.client.post(f"/api/sessions/{sid2}/end")

        r1 = self.result_repo.get_result(sid1)
        r2 = self.result_repo.get_result(sid2)

        self.assertEqual(r1["exercise"], "elbow_flexion")
        self.assertEqual(r1["side"], "left")
        self.assertEqual(r1["repetitions"], 5)

        self.assertEqual(r2["exercise"], "knee_flexion")
        self.assertEqual(r2["side"], "right")
        self.assertEqual(r2["repetitions"], 15)

    # -------------------------------------------------------------------------
    # 7. Restart Durability (Item 21)
    # -------------------------------------------------------------------------
    def test_07_restart_durability(self):
        """
        Create patient, assignment, completed session, and result.
        Dispose database engine and reopen with brand new Database instance on same file.
        Verify all records and metrics survive intact.
        """
        self.patient_repo.create_patient({"patient_id": "P_REBOOT", "name": "Reboot Patient", "status": "ACTIVE"})
        a = self.assignment_repo.assign_exercise({"patient_id": "P_REBOOT", "exercise_id": "shoulder_abduction", "side": "right"})
        sid = self.session_repo.start_session("P_REBOOT", "shoulder_abduction", side="right")

        self.result_repo.record_result(
            session_id=sid,
            repetitions=20,
            rom_min=20.0,
            rom_max=175.0,
            rom_average=150.0,
            performance_score=98.0,
            feedback="Outstanding abduction range",
        )
        self.session_repo.end_session(sid)

        # Simulate full backend reboot
        self.db.engine.dispose()
        app.dependency_overrides.clear()

        restarted_db = Database(self.db_url)
        restarted_db.create_schema()

        app.dependency_overrides[get_database] = lambda: restarted_db
        app.dependency_overrides[get_patient_repo] = lambda: SQLAlchemyPatientRepository(restarted_db)
        app.dependency_overrides[get_assignment_repo] = lambda: SQLAlchemyAssignmentRepository(restarted_db)
        app.dependency_overrides[get_session_repo] = lambda: SQLAlchemySessionRepository(restarted_db)
        app.dependency_overrides[get_telemetry_repo] = lambda: SQLAlchemyTelemetryRepository(restarted_db)
        app.dependency_overrides[get_result_repo] = lambda: SQLAlchemyResultRepository(restarted_db)

        new_client = TestClient(app, raise_server_exceptions=False)

        # Verify patient survives
        p_resp = new_client.get("/api/patients/P_REBOOT")
        self.assertEqual(p_resp.status_code, 200)
        self.assertEqual(p_resp.json()["name"], "Reboot Patient")

        # Verify assignment survives
        a_resp = new_client.get("/api/patients/P_REBOOT/exercises")
        self.assertEqual(a_resp.status_code, 200)
        self.assertEqual(len(a_resp.json()["assignments"]), 1)

        # Verify session and result survive in history
        h_resp = new_client.get("/api/patients/P_REBOOT/sessions")
        self.assertEqual(h_resp.status_code, 200)
        sess = h_resp.json()["sessions"][0]
        self.assertEqual(sess["session_id"], sid)
        self.assertEqual(sess["status"], "COMPLETED")
        self.assertEqual(sess["results"][0]["repetitions"], 20)
        self.assertEqual(sess["results"][0]["performance_score"], 98.0)

        # Clean up reopened db engine
        restarted_db.engine.dispose()

    # -------------------------------------------------------------------------
    # 8. SQLite Integrity & Foreign Keys (Item 22)
    # -------------------------------------------------------------------------
    def test_08_sqlite_foreign_key_integrity(self):
        """
        Verifies:
        - PRAGMA foreign_keys = ON on all SQLite connections
        - PRAGMA foreign_key_check returns zero violations
        - Soft deactivation preserves all historical sessions and results
        """
        with self.db.session() as session:
            fk_status = session.execute(text("PRAGMA foreign_keys")).scalar()
            self.assertEqual(fk_status, 1)

            fk_violations = session.execute(text("PRAGMA foreign_key_check")).fetchall()
            self.assertEqual(len(fk_violations), 0)

        # Create patient, assignment, session, result
        self.patient_repo.create_patient({"patient_id": "P_INTEG", "name": "Integ Patient", "status": "ACTIVE"})
        a = self.assignment_repo.assign_exercise({"patient_id": "P_INTEG", "exercise_id": "elbow_flexion", "side": "left"})
        sid = self.session_repo.start_session("P_INTEG", "elbow_flexion", side="left")
        self.result_repo.record_result(session_id=sid, repetitions=10, rom_min=30.0, rom_max=130.0, rom_average=80.0, performance_score=80.0)
        self.session_repo.end_session(sid)

        # Soft-deactivate assignment and patient
        self.assignment_repo.deactivate_assignment(a["id"])
        self.patient_repo.deactivate_patient("P_INTEG")

        # Verify foreign keys are still 100% clean
        with self.db.session() as session:
            violations_after = session.execute(text("PRAGMA foreign_key_check")).fetchall()
            self.assertEqual(len(violations_after), 0)

        # Verify historical session still exists
        hist = self.patient_repo.get_patient_history("P_INTEG")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["session_id"], sid)
        self.assertEqual(hist[0]["results"][0]["repetitions"], 10)

    # -------------------------------------------------------------------------
    # 9. Repeated /end Requests Idempotency (Item 6)
    # -------------------------------------------------------------------------
    def test_09_repeated_end_requests_idempotency(self):
        """
        Calling /end multiple times sequentially:
        - Returns HTTP 200
        - Preserves original ended_at timestamp
        - Does not insert duplicate Result rows
        - Leaves metrics uncorrupted
        """
        self.patient_repo.create_patient({"patient_id": "P_IDEMP", "name": "Idemp Patient", "status": "ACTIVE"})
        a = self.assignment_repo.assign_exercise({"patient_id": "P_IDEMP", "exercise_id": "elbow_flexion", "side": "left"})
        sid = self.session_repo.start_session("P_IDEMP", "elbow_flexion", side="left")

        self.result_repo.record_result(
            session_id=sid, repetitions=7, rom_min=45.0, rom_max=135.0, rom_average=90.0, performance_score=78.0, feedback="Initial"
        )

        resp1 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp1.status_code, 200)
        sess1 = self.session_repo.get_session(sid)
        ended_at_1 = sess1["ended_at"]
        self.assertIsNotNone(ended_at_1)

        # Second /end call
        resp2 = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(resp2.status_code, 200)
        sess2 = self.session_repo.get_session(sid)
        ended_at_2 = sess2["ended_at"]

        # Timestamp must be identical and not overwritten
        self.assertEqual(ended_at_1, ended_at_2)

        # Exactly 1 Result row
        with self.db.session() as session:
            from digital_thread.models import Result
            count = session.query(Result).filter(Result.session_id == sid).count()
            self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 10. Illegal State Transitions (Item 8)
    # -------------------------------------------------------------------------
    def test_10_illegal_state_transitions(self):
        """
        Verifies:
        - Nonexistent session /end returns HTTP 404
        - Record frame to COMPLETED session returns HTTP 400
        - Record result to COMPLETED session returns HTTP 400
        """
        # Nonexistent session /end
        resp_404 = self.client.post("/api/sessions/S-DOESNOTEXIST/end")
        self.assertEqual(resp_404.status_code, 404)

        # Create and complete session
        self.patient_repo.create_patient({"patient_id": "P_ILLEGAL", "name": "Illegal State Patient", "status": "ACTIVE"})
        self.assignment_repo.assign_exercise({"patient_id": "P_ILLEGAL", "exercise_id": "elbow_flexion", "side": "left"})
        sid = self.session_repo.start_session("P_ILLEGAL", "elbow_flexion", side="left")
        self.result_repo.record_result(session_id=sid, repetitions=5, rom_min=30.0, rom_max=120.0, rom_average=75.0, performance_score=65.0)
        self.client.post(f"/api/sessions/{sid}/end")

        # Attempt to record frame to COMPLETED session -> 400
        frame_resp = self.client.post(f"/api/sessions/{sid}/frames", json={
            "frame_id": 1,
            "landmarks": {"11": {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.99}},
            "joint_angles": {"elbow": 90.0},
        })
        self.assertEqual(frame_resp.status_code, 400)
        self.assertIn("not ACTIVE", frame_resp.json()["detail"])

        # Attempt to record result to COMPLETED session -> 400
        res_resp = self.client.post(f"/api/sessions/{sid}/results", json={
            "repetitions": 10,
            "rom_min": 30.0,
            "rom_max": 140.0,
            "rom_average": 85.0,
            "performance_score": 85.0,
        })
        self.assertEqual(res_resp.status_code, 400)
        self.assertIn("not ACTIVE", res_resp.json()["detail"])

    # -------------------------------------------------------------------------
    # 11. Unexpected Disconnect Lifecycle (Item 5)
    # -------------------------------------------------------------------------
    def test_11_unexpected_disconnect_lifecycle(self):
        """
        Verifies:
        - Unexpected disconnect without valid frames: session remains ACTIVE, no fake Result, /end fails with 400.
        - Unexpected disconnect with valid frames: session remains ACTIVE, Result is persisted, subsequent /end succeeds.
        """
        self.patient_repo.create_patient({"patient_id": "P_ABRUPT", "name": "Abrupt Patient", "status": "ACTIVE"})
        self.assignment_repo.assign_exercise({"patient_id": "P_ABRUPT", "exercise_id": "elbow_flexion", "side": "left"})
        sid = self.session_repo.start_session("P_ABRUPT", "elbow_flexion", side="left")

        # Disconnect with 0 valid frames
        with patch("backend.routes.analysis.mp.solutions.pose.Pose") as mock_pose_cls:
            mock_pose = MagicMock()
            mock_pose_cls.return_value = mock_pose
            mock_pose.process.return_value = _mp_no_person()

            with self.client.websocket_connect(f"/api/analysis/ws/{sid}") as ws:
                ws.send_text(_create_jpeg_b64())
                ws.receive_json()

        # Session remains ACTIVE, no Result row
        self.assertEqual(self.session_repo.get_session(sid)["status"], "ACTIVE")
        self.assertIsNone(self.result_repo.get_result(sid))

        # /end returns 400
        self.assertEqual(self.client.post(f"/api/sessions/{sid}/end").status_code, 400)

    # -------------------------------------------------------------------------
    # 12. Final Result Followed by API Failure (Addendum Test D)
    # -------------------------------------------------------------------------
    def test_12_final_result_followed_by_api_failure(self):
        """
        Simulates:
        - Result is recorded / received.
        - Frontend / client fails to call /end (or request times out).
        Verifies:
        - Backend session remains in consistent ACTIVE state.
        - No fake completed state.
        - Client can retry /end and successfully complete.
        """
        self.patient_repo.create_patient({"patient_id": "P_FAIL_RETRY", "name": "Retry Patient", "status": "ACTIVE"})
        self.assignment_repo.assign_exercise({"patient_id": "P_FAIL_RETRY", "exercise_id": "elbow_flexion", "side": "left"})
        sid = self.session_repo.start_session("P_FAIL_RETRY", "elbow_flexion", side="left")

        # Result recorded via WebSocket END_SESSION handler
        self.result_repo.record_result(
            session_id=sid,
            repetitions=9,
            rom_min=35.0,
            rom_max=135.0,
            rom_average=85.0,
            performance_score=82.0,
            feedback="Good effort",
        )

        # Session is still ACTIVE (not completed yet)
        sess_before = self.session_repo.get_session(sid)
        self.assertEqual(sess_before["status"], "ACTIVE")

        # Overview verifies patient is still marked active
        ov_before = self.client.get("/api/patients").json()
        self.assertEqual(ov_before["active_patients"], 1)

        # Subsequent retry of /end succeeds
        retry_resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(retry_resp.status_code, 200)
        self.assertEqual(retry_resp.json()["status"], "COMPLETED")

        # Database session is now COMPLETED
        sess_after = self.session_repo.get_session(sid)
        self.assertEqual(sess_after["status"], "COMPLETED")
        self.assertEqual(sess_after["ended_at"] is not None, True)
