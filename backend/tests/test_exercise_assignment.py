"""
Phase 6B Automated Test Suite: Patient Exercise Assignment.

Covers:
1. Assign valid exercise (POST /api/patients/{id}/exercises -> 201)
2. Retrieve assignments (GET /api/patients/{id}/exercises/{assignment_id} -> 200)
3. List assignments for patient (GET /api/patients/{id}/exercises -> 200)
4. Update assignment (PUT /api/patients/{id}/exercises/{assignment_id} -> 200)
5. Deactivate assignment (DELETE /api/patients/{id}/exercises/{assignment_id} -> 200, active=False)
6. Unknown patient rejected (POST/GET /api/patients/UNKNOWN/exercises -> 404)
7. Unknown exercise rejected (POST with unknown exercise_id -> 404/400)
8. Invalid side rejected (POST with side="invalid" -> 400)
9. Invalid target values rejected (negative ROM, zero reps, zero sessions_per_day -> 400)
10. Duplicate patient/exercise/side rejected (POST same exercise & side twice -> 409)
11. Same exercise on opposite sides allowed (bilateral rehabilitation)
12. Assignment for Patient A cannot be accessed through Patient B (isolation)
13. Inactive patient cannot receive a new assignment (POST -> 400)
14. Session creation enforces assignment (unassigned exercise rejected when assignments exist)
"""
import os
import unittest
from fastapi.testclient import TestClient

from backend.main import app
from digital_thread.db import Database
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


class TestExerciseAssignmentPhase6B(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_assignment_{os.urandom(6).hex()}.db"
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
        self.patient_repo = SQLAlchemyPatientRepository(self.db)
        self.assignment_repo = SQLAlchemyAssignmentRepository(self.db)

        # Create base active patient for testing
        self.client.post("/api/patients", json={"patient_id": "P_ASSIGN_1", "name": "Patient One"})
        self.client.post("/api/patients", json={"patient_id": "P_ASSIGN_2", "name": "Patient Two"})

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.engine.dispose()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_01_assign_valid_exercise(self):
        """1. Assign valid exercise to patient with targets."""
        resp = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
            "target_rom": 140.0,
            "target_repetitions": 12,
            "sessions_per_day": 2,
            "notes": "Gentle stretching"
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["patient_id"], "P_ASSIGN_1")
        self.assertEqual(data["exercise_id"], "elbow_flexion")
        self.assertEqual(data["exercise_name"], "Elbow Flexion")
        self.assertEqual(data["side"], "left")
        self.assertEqual(data["target_rom"], 140.0)
        self.assertEqual(data["target_repetitions"], 12)
        self.assertEqual(data["sessions_per_day"], 2)
        self.assertTrue(data["active"])

    def test_02_retrieve_assignment(self):
        """2. Retrieve specific assignment by ID."""
        post_resp = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "shoulder_flexion",
            "side": "right",
            "target_rom": 160.0
        })
        aid = post_resp.json()["id"]

        get_resp = self.client.get(f"/api/patients/P_ASSIGN_1/exercises/{aid}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["id"], aid)
        self.assertEqual(get_resp.json()["exercise_id"], "shoulder_flexion")
        self.assertEqual(get_resp.json()["side"], "right")

    def test_03_list_assignments_for_patient(self):
        """3. List assignments for patient with active_only filtering."""
        self.client.post("/api/patients/P_ASSIGN_1/exercises", json={"exercise_id": "elbow_flexion", "side": "left"})
        self.client.post("/api/patients/P_ASSIGN_1/exercises", json={"exercise_id": "knee_flexion", "side": "left"})

        resp = self.client.get("/api/patients/P_ASSIGN_1/exercises")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_assignments"], 2)
        ex_ids = [a["exercise_id"] for a in data["assignments"]]
        self.assertIn("elbow_flexion", ex_ids)
        self.assertIn("knee_flexion", ex_ids)

    def test_04_update_assignment(self):
        """4. Update assignment target configuration."""
        post_resp = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left", "target_repetitions": 8
        })
        aid = post_resp.json()["id"]

        put_resp = self.client.put(f"/api/patients/P_ASSIGN_1/exercises/{aid}", json={
            "target_repetitions": 15,
            "target_rom": 145.0,
            "notes": "Increased target repetitions"
        })
        self.assertEqual(put_resp.status_code, 200)
        self.assertEqual(put_resp.json()["target_repetitions"], 15)
        self.assertEqual(put_resp.json()["target_rom"], 145.0)
        self.assertEqual(put_resp.json()["notes"], "Increased target repetitions")

    def test_05_deactivate_assignment(self):
        """5. Soft-deactivate an assignment (active becomes False)."""
        post_resp = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left"
        })
        aid = post_resp.json()["id"]

        del_resp = self.client.delete(f"/api/patients/P_ASSIGN_1/exercises/{aid}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(del_resp.json()["active"])

        # Active-only list excludes it
        active_resp = self.client.get("/api/patients/P_ASSIGN_1/exercises?active_only=true")
        self.assertEqual(active_resp.json()["total_assignments"], 0)

        # Full list includes it
        all_resp = self.client.get("/api/patients/P_ASSIGN_1/exercises")
        self.assertEqual(all_resp.json()["total_assignments"], 1)

    def test_06_unknown_patient_rejected(self):
        """6. Unknown patient returns 404 for assignment routes."""
        post_resp = self.client.post("/api/patients/P_NONEXISTENT/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left"
        })
        self.assertEqual(post_resp.status_code, 404)

        get_resp = self.client.get("/api/patients/P_NONEXISTENT/exercises")
        self.assertEqual(get_resp.status_code, 404)

    def test_07_unknown_exercise_rejected(self):
        """7. Unknown exercise returns 404."""
        resp = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "jumping_jacks", "side": "left"
        })
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Unknown exercise", resp.json()["detail"])

    def test_08_invalid_side_rejected(self):
        """8. Invalid side rejected with 400."""
        resp = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "middle"
        })
        self.assertIn(resp.status_code, (400, 422))

    def test_09_invalid_target_values_rejected(self):
        """9. Negative/zero targets rejected with 400/422."""
        # Negative target_rom
        r1 = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left", "target_rom": -10.0
        })
        self.assertIn(r1.status_code, (400, 422))

        # Zero target_repetitions
        r2 = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left", "target_repetitions": 0
        })
        self.assertIn(r2.status_code, (400, 422))

        # Zero sessions_per_day
        r3 = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left", "sessions_per_day": 0
        })
        self.assertIn(r3.status_code, (400, 422))

    def test_10_duplicate_patient_exercise_side_rejected(self):
        """10. Duplicate assignment of same (patient, exercise, side) rejected with 409 Conflict."""
        r1 = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left"
        })
        self.assertEqual(r1.status_code, 201)

        r2 = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left"
        })
        self.assertEqual(r2.status_code, 409)
        self.assertIn("already assigned", r2.json()["detail"])

    def test_11_same_exercise_opposite_sides_allowed(self):
        """11. Same exercise on opposite sides allowed (bilateral rehabilitation)."""
        r_left = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left"
        })
        self.assertEqual(r_left.status_code, 201)

        r_right = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "right"
        })
        self.assertEqual(r_right.status_code, 201)

        list_resp = self.client.get("/api/patients/P_ASSIGN_1/exercises")
        self.assertEqual(list_resp.json()["total_assignments"], 2)

    def test_12_patient_isolation_assignment_not_accessible_by_other_patient(self):
        """12. Isolation: Patient A's assignment cannot be accessed, modified, or deleted via Patient B."""
        # Create assignment for Patient 1
        a1 = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left"
        }).json()
        a1_id = a1["id"]

        # Try to access a1 through Patient 2's URL
        get_b = self.client.get(f"/api/patients/P_ASSIGN_2/exercises/{a1_id}")
        self.assertEqual(get_b.status_code, 404)

        # Try to update a1 through Patient 2's URL
        put_b = self.client.put(f"/api/patients/P_ASSIGN_2/exercises/{a1_id}", json={"notes": "Hacked"})
        self.assertEqual(put_b.status_code, 404)

        # Try to delete a1 through Patient 2's URL
        del_b = self.client.delete(f"/api/patients/P_ASSIGN_2/exercises/{a1_id}")
        self.assertEqual(del_b.status_code, 404)

        # Verify a1 is still active and unchanged for Patient 1
        get_a = self.client.get(f"/api/patients/P_ASSIGN_1/exercises/{a1_id}")
        self.assertEqual(get_a.status_code, 200)
        self.assertTrue(get_a.json()["active"])

    def test_13_inactive_patient_cannot_receive_assignment(self):
        """13. Inactive patient cannot receive a new assignment."""
        self.client.post("/api/patients", json={"patient_id": "P_INACTIVE_ASS", "name": "Inactive User"})
        self.client.delete("/api/patients/P_INACTIVE_ASS")

        resp = self.client.post("/api/patients/P_INACTIVE_ASS/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("INACTIVE", resp.json()["detail"])

    def test_14_session_creation_enforces_assignment(self):
        """14. Session creation respects assignments: patient cannot start unassigned exercise/side."""
        # Patient 1 is assigned only: elbow_flexion left
        self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion", "side": "left"
        })

        # Attempt to start elbow_flexion right (unassigned side) -> rejected!
        r_wrong_side = self.client.post("/api/sessions", json={
            "patient_id": "P_ASSIGN_1", "exercise": "elbow_flexion", "side": "right"
        })
        self.assertEqual(r_wrong_side.status_code, 400)
        self.assertIn("not assigned", r_wrong_side.json()["detail"])

        # Attempt to start shoulder_flexion left (unassigned exercise) -> rejected!
        r_wrong_ex = self.client.post("/api/sessions", json={
            "patient_id": "P_ASSIGN_1", "exercise": "shoulder_flexion", "side": "left"
        })
        self.assertEqual(r_wrong_ex.status_code, 400)
        self.assertIn("not assigned", r_wrong_ex.json()["detail"])

        # Start assigned exercise elbow_flexion left -> succeeds!
        r_correct = self.client.post("/api/sessions", json={
            "patient_id": "P_ASSIGN_1", "exercise": "elbow_flexion", "side": "left"
        })
        self.assertEqual(r_correct.status_code, 201)
        self.assertEqual(r_correct.json()["exercise"], "elbow_flexion")
        self.assertEqual(r_correct.json()["side"], "left")

    def test_15_inactive_assignment_reactivated_on_reassign(self):
        """
        TEST 3 — INACTIVE ASSIGNMENT CAN BE REUSED:
        1. Create: Patient A + Elbow Flexion / Left assignment
        2. Deactivate assignment
        3. Assign the same: Patient A + Elbow Flexion / Left again with new configuration
        4. Verify:
           - same assignment ID is retained
           - exactly one row exists
           - active=True
           - new configuration is applied
           - updated_at is actually later than the previous value
        """
        import time

        # 1. Initial assignment
        r1 = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
            "target_rom": 120.0,
            "target_repetitions": 8,
            "sessions_per_day": 1,
            "notes": "Initial prescription"
        })
        self.assertEqual(r1.status_code, 201)
        initial_data = r1.json()
        aid = initial_data["id"]
        initial_updated_at = initial_data["updated_at"]
        self.assertTrue(initial_data["active"])

        # 2. Deactivate assignment
        del_resp = self.client.delete(f"/api/patients/P_ASSIGN_1/exercises/{aid}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(del_resp.json()["active"])
        deact_updated_at = del_resp.json()["updated_at"]

        # Ensure measurable time elapsed so updated_at is strictly later
        time.sleep(0.05)

        # 3. Re-assign same (patient, exercise, side) with new configuration
        r2 = self.client.post("/api/patients/P_ASSIGN_1/exercises", json={
            "exercise_id": "elbow_flexion",
            "side": "left",
            "target_rom": 150.0,
            "target_repetitions": 15,
            "sessions_per_day": 2,
            "notes": "Reactivated and increased targets"
        })
        self.assertIn(r2.status_code, (200, 201))
        reassigned_data = r2.json()

        # 4. Verify requirements:
        # A. Same assignment ID is retained
        self.assertEqual(reassigned_data["id"], aid)

        # B. Exactly one row exists for this patient/exercise/side
        all_assignments = self.client.get("/api/patients/P_ASSIGN_1/exercises").json()["assignments"]
        matching = [a for a in all_assignments if a["exercise_id"] == "elbow_flexion" and a["side"] == "left"]
        self.assertEqual(len(matching), 1, "Must have exactly one row in database")

        # Direct SQL query verification
        with self.db.session() as s:
            from digital_thread.models import PatientExerciseAssignment
            rows = s.query(PatientExerciseAssignment).filter(
                PatientExerciseAssignment.patient_id == "P_ASSIGN_1",
                PatientExerciseAssignment.exercise_id == "elbow_flexion",
                PatientExerciseAssignment.side == "left",
            ).all()
            self.assertEqual(len(rows), 1, "Exactly one row must exist in patient_exercises table")

        # C. active == True
        self.assertTrue(reassigned_data["active"])

        # D. New configuration is applied
        self.assertEqual(reassigned_data["target_rom"], 150.0)
        self.assertEqual(reassigned_data["target_repetitions"], 15)
        self.assertEqual(reassigned_data["sessions_per_day"], 2)
        self.assertEqual(reassigned_data["notes"], "Reactivated and increased targets")

        # E. updated_at is actually later than the previous value
        self.assertGreater(reassigned_data["updated_at"], deact_updated_at)
        self.assertGreater(reassigned_data["updated_at"], initial_updated_at)

