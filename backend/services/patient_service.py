"""
Patient service handling patient lifecycle, session history retrieval, and patient indexing
via repository layer.
"""
from typing import List, Optional, Dict, Any

from backend.repositories.interfaces import IPatientRepository
from backend.schemas.patient import (
    PatientCreateRequest,
    PatientUpdateRequest,
    PatientResponse,
    PatientHistoryResponse,
    PatientSessionHistoryItem,
    ResultSummary,
    PatientListResponse,
    PatientSummary,
)


class PatientNotFoundException(Exception):
    """Raised when a requested patient does not exist."""
    def __init__(self, patient_id: str):
        self.patient_id = patient_id
        super().__init__(f"Patient '{patient_id}' not found.")


class DuplicatePatientException(Exception):
    """Raised when attempting to create a patient with an existing ID."""
    def __init__(self, patient_id: str):
        self.patient_id = patient_id
        super().__init__(f"Patient with ID '{patient_id}' already exists.")


class PatientNotActiveException(Exception):
    """Raised when an operation requires an ACTIVE patient but the patient is INACTIVE."""
    def __init__(self, patient_id: str):
        self.patient_id = patient_id
        super().__init__(f"Patient '{patient_id}' is INACTIVE.")


class PatientValidationError(Exception):
    """Raised when patient input fails domain validation."""
    pass


class PatientService:
    """Service layer for patient CRUD, session history, and summary listings."""

    def __init__(self, patient_repo: IPatientRepository):
        self.patient_repo = patient_repo

    def create_patient(self, request: PatientCreateRequest) -> PatientResponse:
        """Create a new persistent Patient record."""
        if self.patient_repo.patient_exists(request.patient_id):
            raise DuplicatePatientException(request.patient_id)

        data = request.model_dump()
        created = self.patient_repo.create_patient(data)
        return PatientResponse(**created)

    def get_patient(self, patient_id: str) -> PatientResponse:
        """Retrieve patient details by patient_id."""
        p = self.patient_repo.get_patient(patient_id)
        if not p:
            raise PatientNotFoundException(patient_id)
        return PatientResponse(**p)

    def update_patient(self, patient_id: str, request: PatientUpdateRequest) -> PatientResponse:
        """Update fields of an existing patient."""
        if not self.patient_repo.patient_exists(patient_id):
            raise PatientNotFoundException(patient_id)

        updates = request.model_dump(exclude_unset=True)
        updated = self.patient_repo.update_patient(patient_id, updates)
        if not updated:
            raise PatientNotFoundException(patient_id)
        return PatientResponse(**updated)

    def deactivate_patient(self, patient_id: str) -> PatientResponse:
        """Soft-deactivate a patient (status='INACTIVE'), preserving historical sessions/results."""
        if not self.patient_repo.patient_exists(patient_id):
            raise PatientNotFoundException(patient_id)

        deactivated = self.patient_repo.deactivate_patient(patient_id)
        if not deactivated:
            raise PatientNotFoundException(patient_id)
        return PatientResponse(**deactivated)

    def get_patient_history(self, patient_id: str) -> PatientHistoryResponse:
        """
        Retrieve complete session and result history for a given patient_id
        using IPatientRepository, ordered newest first (started_at DESC).
        """
        raw_history = self.patient_repo.get_patient_history(patient_id)
        
        sessions_list: List[PatientSessionHistoryItem] = []
        for item in raw_history:
            session_side = item.get("side", "left") or "left"
            results_list = [
                ResultSummary(
                    repetitions=r.get("repetitions", 0),
                    side=r.get("side", session_side) or session_side,
                    rom_min=r.get("rom_min"),
                    rom_max=r.get("rom_max"),
                    rom_average=r.get("rom_average"),
                    performance_score=r.get("performance_score"),
                    feedback=r.get("feedback", "")
                )
                for r in item.get("results", [])
            ]
            
            sessions_list.append(
                PatientSessionHistoryItem(
                    session_id=item["session_id"],
                    patient_id=item["patient_id"],
                    exercise=item["exercise"],
                    side=session_side,
                    started_at=item["started_at"],
                    ended_at=item.get("ended_at"),
                    status=item["status"],
                    results=results_list
                )
            )

        # Explicit newest-first ordering guarantee
        sessions_list.sort(key=lambda s: s.started_at, reverse=True)

        return PatientHistoryResponse(
            patient_id=patient_id,
            total_sessions=len(sessions_list),
            sessions=sessions_list
        )

    def list_patients(self) -> PatientListResponse:
        """
        Query distinct registered patients, session counts, and system metrics
        from the IPatientRepository.
        """
        patients_list: List[PatientSummary] = []
        
        records = self.patient_repo.list_patients()
        overview = self.patient_repo.get_system_overview()

        for rec in records:
            patients_list.append(
                PatientSummary(
                    patient_id=rec["patient_id"],
                    name=rec.get("name"),
                    status=rec.get("status", "ACTIVE"),
                    age=rec.get("age"),
                    gender=rec.get("gender"),
                    phone=rec.get("phone"),
                    email=rec.get("email"),
                    notes=rec.get("notes"),
                    created_at=rec.get("created_at"),
                    updated_at=rec.get("updated_at"),
                    total_sessions=rec.get("total_sessions", 0),
                    active_sessions=rec.get("active_sessions", 0),
                    completed_sessions=rec.get("completed_sessions", 0),
                    last_active=rec.get("last_active"),
                    average_performance_score=rec.get("average_performance_score")
                )
            )

        return PatientListResponse(
            total_patients=overview.get("total_patients", len(patients_list)),
            total_sessions=overview.get("total_sessions", sum(p.total_sessions for p in patients_list)),
            active_patients=overview.get("active_patients", sum(1 for p in patients_list if p.active_sessions > 0)),
            average_performance_score=overview.get("average_performance_score"),
            patients=patients_list
        )
