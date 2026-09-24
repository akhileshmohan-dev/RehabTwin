"""
Phase 6C + 6D Comprehensive Integration Test Suite:
Patient Portal, Therapist Portal, and Strict Assignment Enforcement.

Covers:
1. Strict Assignment Enforcement Cases A through H:
   A. Patient with zero assignments -> session blocked (400)
   B. Patient with active assignment -> session created via assignment_id (201, authoritative exercise/side/targets)
   C. Patient with active assignment -> session created without assignment_id matching (exercise, side) (201)
   D. Patient with active assignment -> unassigned exercise blocked (400)
   E. Patient with active assignment -> wrong side blocked (400)
   F. Inactive assignment -> session blocked (400)
   G. Cross-patient assignment mismatch -> session blocked (400)
   H. Non-existent assignment_id -> session blocked (400)
2. Database Persistence & Reactivation:
   - Patient demographic CRUD (name, age, gender, notes, status)
   - Assignment CRUD (create, update, soft-deactivate, reactivate retaining same ID)
   - Session creation persists assignment_id, target_rom, and target_repetitions
   - Safe history queries for sessions with or without results
"""
import os
import unittest
from fastapi.testclient import TestClient

from backend.main import app
from digital_thread.db import Database
from digital_thread.models import Session
from backend.core.dependencies import (
    get_database,
    get_patient_repo,
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
    get_assignment_repo,
)
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
    SQLAlchemyAssignmentRepository,
)


class TestPatientPortalIntegration(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_portal_{os.urandom(6).hex()}.db"
        self.db_url = f"sqlite:///{self.db_path}?check_same_thread=False"
        self.db = Database(self.db_url)
        self.db.create_schema()

        app.dependency_overrides[get_database] = lambda: self.db
        app.dependency_overrides[get_patient_repo] = lambda: SQLAlchemyPatientRepository(self.db)
        app.dependency_overrides[get_session_repo] = lambda: SQLAlchemySessionRepository(self.db)
        app.dependency_overrides[get_telemetry_repo] = lambda: SQLAlchemyTelemetryRepository(self.db)
        app.dependency_overrides[get_result_repo] = lambda: SQLAlchemyResultRepository(self.db)
        app.dependency_overrides[get_assignment_repo] = lambda: SQLAlchemyAssignmentRepository(self.db)

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.engine.dispose()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    # =========================================================================
    # STRICT ASSIGNMENT ENFORCEMENT — CASES A THROUGH H
    # =========================================================================

    def test_case_a_patient_with_zero_assignments_blocked(self):
        """Case A: Patient exists but has zero assignments -> cannot start arbitrary session."""
        self.client.post("/api/patients", json={"patient_id": "P_ZERO", "name": "Zero Assignments Patient"})

        resp = self.client.post("/api/sessions", json={
            "patient_id": "P_ZERO",
            "exercise": "elbow_flexion",
            "side": "left",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not assigned", resp.json()["detail"].lower())

    def test_case_b_start_session_with_authoritative_assignment_id(self):
        """Case B: Patient with active assignment starts session via assignment_id."""
        self.client.post("/api/patients", json={"patient_id": "P_AUTH", "name": "Authoritative Patient"})
        assign_resp = self.client.post("/api/patients/P_AUTH/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
            "target_rom": 135.0,
            "target_repetitions": 15,
            "sessions_per_day": 2,
            "notes": "Keep elbow tucked in",
        })
        self.assertEqual(assign_resp.status_code, 201)
        assignment_id = assign_resp.json()["id"]

        resp = self.client.post("/api/sessions", json={
            "patient_id": "P_AUTH",
            "assignment_id": assignment_id,
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["assignment_id"], assignment_id)
        self.assertEqual(data["exercise"], "elbow_flexion")
        self.assertEqual(data["side"], "left")
        self.assertEqual(data["target_rom"], 135.0)
        self.assertEqual(data["target_repetitions"], 15)

    def test_case_c_start_session_without_assignment_id_matches_active(self):
        """Case C: Patient starts session with matching exercise and side, no assignment_id."""
        self.client.post("/api/patients", json={"patient_id": "P_MATCH", "name": "Match Patient"})
        assign_resp = self.client.post("/api/patients/P_MATCH/exercises", json={
            "exercise_id": "shoulder_flexion",
            "side": "right",
            "target_rom": 160.0,
            "target_repetitions": 10,
        })
        self.assertEqual(assign_resp.status_code, 201)
        assign_id = assign_resp.json()["id"]

        resp = self.client.post("/api/sessions", json={
            "patient_id": "P_MATCH",
            "exercise": "shoulder_flexion",
            "side": "right",
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["assignment_id"], assign_id)
        self.assertEqual(data["exercise"], "shoulder_flexion")
        self.assertEqual(data["side"], "right")
        self.assertEqual(data["target_rom"], 160.0)

    def test_case_d_unassigned_exercise_blocked(self):
        """Case D: Patient has assignment for (elbow_flexion, left), tries knee_flexion -> blocked."""
        self.client.post("/api/patients", json={"patient_id": "P_EX", "name": "Exercise Patient"})
        self.client.post("/api/patients/P_EX/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
        })

        resp = self.client.post("/api/sessions", json={
            "patient_id": "P_EX",
            "exercise": "knee_flexion",
            "side": "left",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not assigned", resp.json()["detail"].lower())

    def test_case_e_wrong_side_blocked(self):
        """Case E: Patient has assignment for (elbow_flexion, left), tries right side -> blocked."""
        self.client.post("/api/patients", json={"patient_id": "P_SIDE", "name": "Side Patient"})
        self.client.post("/api/patients/P_SIDE/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
        })

        resp = self.client.post("/api/sessions", json={
            "patient_id": "P_SIDE",
            "exercise": "elbow_flexion",
            "side": "right",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not assigned", resp.json()["detail"].lower())

    def test_case_f_inactive_assignment_blocked(self):
        """Case F: Patient with INACTIVE assignment cannot start session with it."""
        self.client.post("/api/patients", json={"patient_id": "P_INACT", "name": "Inactive Assignment Patient"})
        assign_resp = self.client.post("/api/patients/P_INACT/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
        })
        assignment_id = assign_resp.json()["id"]

        del_resp = self.client.delete(f"/api/patients/P_INACT/exercises/{assignment_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(del_resp.json()["active"])

        resp = self.client.post("/api/sessions", json={
            "patient_id": "P_INACT",
            "assignment_id": assignment_id,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("inactive", resp.json()["detail"].lower())

    def test_case_g_cross_patient_assignment_mismatch_blocked(self):
        """Case G: Patient A tries to start session using Patient B's assignment_id -> blocked."""
        self.client.post("/api/patients", json={"patient_id": "PATIENT_A", "name": "Patient Alpha"})
        self.client.post("/api/patients", json={"patient_id": "PATIENT_B", "name": "Patient Beta"})

        assign_b = self.client.post("/api/patients/PATIENT_B/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
        }).json()
        assign_b_id = assign_b["id"]

        resp = self.client.post("/api/sessions", json={
            "patient_id": "PATIENT_A",
            "assignment_id": assign_b_id,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_case_h_nonexistent_assignment_id_blocked(self):
        """Case H: Non-existent assignment_id -> blocked (400)."""
        self.client.post("/api/patients", json={"patient_id": "P_VALID", "name": "Valid Patient"})
        resp = self.client.post("/api/sessions", json={
            "patient_id": "P_VALID",
            "assignment_id": 999999,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not found", resp.json()["detail"].lower())

    # =========================================================================
    # END-TO-END PATIENT & ASSIGNMENT CRUD AND SESSION PERSISTENCE
    # =========================================================================

    def test_patient_crud_and_assignment_reactivation(self):
        """Verify patient demographic updates, assignment reactivation retaining ID."""
        # 1. Create Patient
        create_resp = self.client.post("/api/patients", json={
            "patient_id": "P_FULL",
            "name": "Full Test Patient",
            "age": 45,
            "gender": "male",
            "phone": "+1 555-0199",
            "email": "test@rehabtwin.com",
            "notes": "Recovering from rotator cuff repair",
        })
        self.assertEqual(create_resp.status_code, 201)
        p_data = create_resp.json()
        self.assertEqual(p_data["age"], 45)
        self.assertEqual(p_data["status"], "ACTIVE")

        # 2. Update Patient demographics
        up_resp = self.client.put("/api/patients/P_FULL", json={
            "name": "Full Test Patient Updated",
            "age": 46,
            "notes": "Updated rehabilitation protocol",
        })
        self.assertEqual(up_resp.status_code, 200)
        self.assertEqual(up_resp.json()["name"], "Full Test Patient Updated")
        self.assertEqual(up_resp.json()["age"], 46)

        # 3. Create Exercise Assignment
        assign_resp = self.client.post("/api/patients/P_FULL/exercises", json={
            "exercise_id": "shoulder_abduction",
            "side": "right",
            "target_rom": 120.0,
            "target_repetitions": 8,
            "sessions_per_day": 3,
            "notes": "Gentle elevation",
        })
        self.assertEqual(assign_resp.status_code, 201)
        original_assign_id = assign_resp.json()["id"]

        # 4. Deactivate assignment
        self.client.delete(f"/api/patients/P_FULL/exercises/{original_assign_id}")

        # 5. Reactivate assignment by re-assigning same (patient, exercise, side)
        reactivate_resp = self.client.post("/api/patients/P_FULL/exercises", json={
            "exercise_id": "shoulder_abduction",
            "side": "right",
            "target_rom": 130.0,
            "target_repetitions": 10,
            "sessions_per_day": 2,
            "notes": "Reactivated and increased ROM",
        })
        self.assertEqual(reactivate_resp.status_code, 201)
        # MUST retain the exact same assignment ID
        self.assertEqual(reactivate_resp.json()["id"], original_assign_id)
        self.assertTrue(reactivate_resp.json()["active"])
        self.assertEqual(reactivate_resp.json()["target_rom"], 130.0)

        # 6. Verify exactly 1 assignment exists for patient in DB
        list_resp = self.client.get("/api/patients/P_FULL/exercises")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["assignments"]), 1)
        self.assertEqual(list_resp.json()["total_assignments"], 1)

        # 7. Start session using reactivated assignment
        sess_resp = self.client.post("/api/sessions", json={
            "patient_id": "P_FULL",
            "assignment_id": original_assign_id,
        })
        self.assertEqual(sess_resp.status_code, 201)
        sid = sess_resp.json()["session_id"]

        # 8. Record result and end session
        self.client.post(f"/api/sessions/{sid}/results", json={
            "repetitions": 10,
            "rom_min": 15.0,
            "rom_max": 125.0,
            "rom_average": 115.0,
            "performance_score": 88.0,
            "feedback": "Great range of motion",
        })
        end_resp = self.client.post(f"/api/sessions/{sid}/end")
        self.assertEqual(end_resp.status_code, 200)
        self.assertEqual(end_resp.json()["status"], "COMPLETED")
        self.assertIsNotNone(end_resp.json()["result"])

        # 9. Query patient sessions -> safely renders session with result
        patient_sessions_resp = self.client.get("/api/patients/P_FULL/sessions")
        self.assertEqual(patient_sessions_resp.status_code, 200)
        p_sessions = patient_sessions_resp.json()["sessions"]
        self.assertEqual(len(p_sessions), 1)
        self.assertEqual(len(p_sessions[0]["results"]), 1)
        self.assertEqual(p_sessions[0]["status"], "COMPLETED")
        self.assertEqual(p_sessions[0]["results"][0]["performance_score"], 88.0)

    # =========================================================================
    # PHASE 6C + 6D CORRECTIVE TESTS: DEACTIVATED PATIENT & NO-RESULT SESSIONS
    # =========================================================================

    def test_deactivated_patient_session_rejection(self):
        """
        1. Deactivated patient session rejection:
        - Create an active patient.
        - Create an active exercise assignment.
        - Deactivate the patient.
        - Attempt POST /api/sessions using the valid assignment_id.
        - Assert HTTP 400.
        - Assert no new session was created.
        """
        # Create active patient
        create_resp = self.client.post("/api/patients", json={
            "patient_id": "P_DEACT",
            "name": "Deactivated Patient",
        })
        self.assertEqual(create_resp.status_code, 201)

        # Create active exercise assignment
        assign_resp = self.client.post("/api/patients/P_DEACT/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
            "target_rom": 140.0,
            "target_repetitions": 10,
        })
        self.assertEqual(assign_resp.status_code, 201)
        assignment_id = assign_resp.json()["id"]

        # Deactivate patient
        deact_resp = self.client.delete("/api/patients/P_DEACT")
        self.assertEqual(deact_resp.status_code, 200)
        self.assertEqual(deact_resp.json()["status"], "INACTIVE")

        # Attempt POST /api/sessions using valid assignment_id
        resp = self.client.post("/api/sessions", json={
            "patient_id": "P_DEACT",
            "assignment_id": assignment_id,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("inactive", resp.json()["detail"].lower())

        # Assert no new session was created
        hist_resp = self.client.get("/api/patients/P_DEACT/sessions")
        self.assertEqual(hist_resp.status_code, 200)
        self.assertEqual(hist_resp.json()["total_sessions"], 0)
        self.assertEqual(len(hist_resp.json()["sessions"]), 0)

        with self.db.session() as s:
            sessions = s.query(Session).filter(Session.patient_id == "P_DEACT").all()
            self.assertEqual(len(sessions), 0)

    def test_completed_session_with_no_result(self):
        """
        2. Completed session with NO result:
        - Create a valid patient + active assignment.
        - Create/start a session.
        - Complete/end the session without recording a Result.
        - Request the patient's session history.
        - Assert the session is returned.
        - Assert it is represented safely as having no result.
        - Assert no fake score, ROM, or repetition values are generated.
        """
        # Create valid patient + active assignment
        create_resp = self.client.post("/api/patients", json={
            "patient_id": "P_NO_RES",
            "name": "No Result Patient",
        })
        self.assertEqual(create_resp.status_code, 201)

        assign_resp = self.client.post("/api/patients/P_NO_RES/exercises", json={
            "exercise_id": "shoulder_flexion",
            "side": "right",
            "target_rom": 150.0,
            "target_repetitions": 12,
        })
        self.assertEqual(assign_resp.status_code, 201)
        assignment_id = assign_resp.json()["id"]

        # Create/start session
        sess_resp = self.client.post("/api/sessions", json={
            "patient_id": "P_NO_RES",
            "assignment_id": assignment_id,
        })
        self.assertEqual(sess_resp.status_code, 201)
        sid = sess_resp.json()["session_id"]

        # Complete/end session without recording a Result
        SQLAlchemySessionRepository(self.db).end_session(sid)

        # Request patient's session history
        hist_resp = self.client.get("/api/patients/P_NO_RES/sessions")
        self.assertEqual(hist_resp.status_code, 200)
        history = hist_resp.json()

        # Assert session is returned
        self.assertEqual(history["total_sessions"], 1)
        self.assertEqual(len(history["sessions"]), 1)
        session_item = history["sessions"][0]
        self.assertEqual(session_item["session_id"], sid)
        self.assertEqual(session_item["patient_id"], "P_NO_RES")
        self.assertEqual(session_item["exercise"], "shoulder_flexion")
        self.assertEqual(session_item["side"], "right")
        self.assertEqual(session_item["status"], "COMPLETED")
        self.assertIsNotNone(session_item["ended_at"])

        # Assert represented safely as having no result
        self.assertEqual(session_item["results"], [])
        self.assertEqual(len(session_item["results"]), 0)

        # Assert no fake score, ROM, or repetition values are generated in overview
        overview_resp = self.client.get("/api/patients")
        self.assertEqual(overview_resp.status_code, 200)
        overview = overview_resp.json()
        p_summary = next(p for p in overview["patients"] if p["patient_id"] == "P_NO_RES")
        self.assertEqual(p_summary["total_sessions"], 1)
        self.assertEqual(p_summary["completed_sessions"], 1)
        self.assertIsNone(p_summary["average_performance_score"])

