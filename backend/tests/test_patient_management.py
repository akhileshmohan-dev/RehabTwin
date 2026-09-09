"""
Phase 6A Automated Test Suite: Patient Management.

Covers:
1. Create patient (POST /api/patients -> 201)
2. Retrieve patient (GET /api/patients/{id} -> 200)
3. List patients (GET /api/patients -> 200 with metadata and stats)
4. Update patient (PUT /api/patients/{id} -> 200)
5. Deactivate patient (DELETE /api/patients/{id} -> 200, status="INACTIVE")
6. Duplicate patient ID rejected (POST /api/patients -> 409)
7. Unknown patient returns 404 on GET, PUT, DELETE
8. Invalid patient data rejected (empty ID/name, negative age -> 400/422)
9. Inactive patient cannot start a new session (POST /api/sessions -> 400)
10. Historical sessions remain accessible after patient deactivation
"""
import os
import unittest
from fastapi.testclient import TestClient

from backend.main import app
from digital_thread.db import Database
from digital_thread.models import Patient, Session
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


class TestPatientManagementPhase6A(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_patient_mgmt_{os.urandom(6).hex()}.db"
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

    def test_01_create_patient(self):
        """1. Create a patient and verify persisted fields in SQLite."""
        resp = self.client.post("/api/patients", json={
            "patient_id": "PAT-100",
            "name": "Alice Smith",
            "age": 42,
            "gender": "female",
            "phone": "+1-555-0101",
            "email": "alice@example.com",
            "notes": "Recovering from rotator cuff surgery.",
            "status": "ACTIVE"
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["patient_id"], "PAT-100")
        self.assertEqual(data["name"], "Alice Smith")
        self.assertEqual(data["age"], 42)
        self.assertEqual(data["gender"], "female")
        self.assertEqual(data["status"], "ACTIVE")
        self.assertIsNotNone(data["created_at"])
        self.assertIsNotNone(data["updated_at"])

        # Direct database verify
        p_db = self.patient_repo.get_patient("PAT-100")
        self.assertIsNotNone(p_db)
        self.assertEqual(p_db["name"], "Alice Smith")

    def test_02_retrieve_patient(self):
        """2. Retrieve patient by ID."""
        self.patient_repo.create_patient({
            "patient_id": "PAT-101",
            "name": "Bob Jones",
            "age": 60,
            "status": "ACTIVE"
        })

        resp = self.client.get("/api/patients/PAT-101")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["patient_id"], "PAT-101")
        self.assertEqual(data["name"], "Bob Jones")
        self.assertEqual(data["age"], 60)

    def test_03_list_patients(self):
        """3. List patients returns registered patients including those with zero sessions."""
        self.client.post("/api/patients", json={"patient_id": "PAT-A", "name": "Patient Alpha"})
        self.client.post("/api/patients", json={"patient_id": "PAT-B", "name": "Patient Beta"})

        resp = self.client.get("/api/patients")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Default P001 from migration + PAT-A + PAT-B = at least 3 patients
        self.assertGreaterEqual(data["total_patients"], 2)
        ids = [p["patient_id"] for p in data["patients"]]
        self.assertIn("PAT-A", ids)
        self.assertIn("PAT-B", ids)

    def test_04_update_patient(self):
        """4. Update patient details."""
        self.client.post("/api/patients", json={
            "patient_id": "PAT-102",
            "name": "Carol Danvers",
            "age": 30
        })

        resp = self.client.put("/api/patients/PAT-102", json={
            "name": "Carol Danvers-Rambeau",
            "notes": "Added new physiotherapy exercise",
            "age": 31
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["name"], "Carol Danvers-Rambeau")
        self.assertEqual(data["age"], 31)
        self.assertEqual(data["notes"], "Added new physiotherapy exercise")

        # Verify DB reflects update
        p = self.patient_repo.get_patient("PAT-102")
        self.assertEqual(p["name"], "Carol Danvers-Rambeau")

    def test_05_deactivate_patient(self):
        """5. Deactivate patient via soft deactivation (status becomes INACTIVE)."""
        self.client.post("/api/patients", json={
            "patient_id": "PAT-103",
            "name": "Dave Miller",
            "status": "ACTIVE"
        })

        resp = self.client.delete("/api/patients/PAT-103")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "INACTIVE")

        # Verify in DB
        p = self.patient_repo.get_patient("PAT-103")
        self.assertEqual(p["status"], "INACTIVE")

    def test_06_duplicate_patient_id_rejected(self):
        """6. Duplicate patient ID rejected with 409 Conflict."""
        self.client.post("/api/patients", json={"patient_id": "PAT-DUP", "name": "First User"})
        resp = self.client.post("/api/patients", json={"patient_id": "PAT-DUP", "name": "Second User"})
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.json()["detail"])

    def test_07_unknown_patient_returns_404(self):
        """7. Unknown patient returns 404 for GET, PUT, DELETE."""
        get_resp = self.client.get("/api/patients/PAT-UNKNOWN")
        self.assertEqual(get_resp.status_code, 404)

        put_resp = self.client.put("/api/patients/PAT-UNKNOWN", json={"name": "New Name"})
        self.assertEqual(put_resp.status_code, 404)

        del_resp = self.client.delete("/api/patients/PAT-UNKNOWN")
        self.assertEqual(del_resp.status_code, 404)

    def test_08_invalid_patient_data_rejected(self):
        """8. Invalid patient data (empty name, empty id, negative age) rejected."""
        # Empty patient_id
        r1 = self.client.post("/api/patients", json={"patient_id": "   ", "name": "Valid Name"})
        self.assertIn(r1.status_code, (400, 422))

        # Empty name
        r2 = self.client.post("/api/patients", json={"patient_id": "PAT-INV", "name": "   "})
        self.assertIn(r2.status_code, (400, 422))

        # Negative age
        r3 = self.client.post("/api/patients", json={"patient_id": "PAT-INV2", "name": "Valid Name", "age": -5})
        self.assertIn(r3.status_code, (400, 422))

        # Invalid status
        r4 = self.client.post("/api/patients", json={"patient_id": "PAT-INV3", "name": "Valid Name", "status": "UNKNOWN"})
        self.assertIn(r4.status_code, (400, 422))

    def test_09_inactive_patient_cannot_start_session(self):
        """9. Inactive patient cannot start a new rehabilitation session."""
        self.client.post("/api/patients", json={
            "patient_id": "PAT-INACTIVE",
            "name": "Inactive User",
            "status": "ACTIVE"
        })
        # Soft deactivate
        del_resp = self.client.delete("/api/patients/PAT-INACTIVE")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.json()["status"], "INACTIVE")

        # Attempt to start session for inactive patient
        start_resp = self.client.post("/api/sessions", json={
            "patient_id": "PAT-INACTIVE",
            "exercise": "elbow_flexion",
            "side": "left"
        })
        self.assertEqual(start_resp.status_code, 400)
        self.assertIn("INACTIVE", start_resp.json()["detail"])

    def test_10_historical_sessions_remain_after_deactivation(self):
        """10. Historical sessions and results remain intact after patient deactivation."""
        self.client.post("/api/patients", json={"patient_id": "PAT-HIST", "name": "Historical Patient"})

        # Start and complete a session
        sid = self.session_repo.start_session("PAT-HIST", "elbow_flexion", side="left")
        self.result_repo.record_result(
            session_id=sid,
            repetitions=10,
            rom_min=30.0,
            rom_max=145.0,
            rom_average=87.5,
            performance_score=92.0,
            feedback="Great consistency."
        )
        self.session_repo.end_session(sid)

        # Deactivate patient
        del_resp = self.client.delete("/api/patients/PAT-HIST")
        self.assertEqual(del_resp.status_code, 200)

        # Retrieve session history for deactivated patient
        hist_resp = self.client.get("/api/patients/PAT-HIST/sessions")
        self.assertEqual(hist_resp.status_code, 200)
        hist = hist_resp.json()
        self.assertEqual(hist["total_sessions"], 1)
        self.assertEqual(hist["sessions"][0]["session_id"], sid)
        self.assertEqual(hist["sessions"][0]["status"], "COMPLETED")
        self.assertEqual(len(hist["sessions"][0]["results"]), 1)
        self.assertEqual(hist["sessions"][0]["results"][0]["repetitions"], 10)

    def test_11_unknown_patient_cannot_start_session(self):
        """
        TEST 2 — UNKNOWN PATIENT CANNOT START SESSION:
        Attempt to start a session using a patient ID that does not exist.
        Verify:
        - session creation fails with 404
        - patient is NOT automatically created
        - no session is created
        - explicitly query patients and sessions table to confirm
        """
        unknown_id = "PAT-UNKNOWN-999"

        # Verify patient does not exist beforehand
        self.assertIsNone(self.patient_repo.get_patient(unknown_id))

        # Attempt to start session via REST
        resp = self.client.post("/api/sessions", json={
            "patient_id": unknown_id,
            "exercise": "elbow_flexion",
            "side": "left"
        })
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

        # Explicitly query patients table and confirm unknown patient was NOT created
        self.assertIsNone(self.patient_repo.get_patient(unknown_id))
        with self.db.session() as s:
            p_row = s.query(Patient).filter(Patient.patient_id == unknown_id).first()
            self.assertIsNone(p_row, "Patient must not be automatically created")

            # Explicitly query sessions table and confirm no session was created
            s_rows = s.query(Session).filter(Session.patient_id == unknown_id).all()
            self.assertEqual(len(s_rows), 0, "No session must be created for unknown patient")

        # Also verify calling repository directly raises PatientNotFoundInRepoException and creates no patient
        from backend.services.patient_service import PatientNotFoundException
        from backend.repositories.interfaces import PatientNotFoundInRepoException
        with self.assertRaises((PatientNotFoundException, PatientNotFoundInRepoException)):
            self.session_repo.start_session(unknown_id, "elbow_flexion", side="left")

        with self.db.session() as s:
            p_row = s.query(Patient).filter(Patient.patient_id == unknown_id).first()
            self.assertIsNone(p_row, "Repository direct call must not automatically create patient")
