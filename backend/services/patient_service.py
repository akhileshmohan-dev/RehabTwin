"""
Patient service handling patient session history retrieval and patient indexing
via repository layer.
"""
from typing import List, Optional

from backend.repositories.interfaces import IPatientRepository
from backend.schemas.patient import (
    PatientHistoryResponse,
    PatientSessionHistoryItem,
    ResultSummary,
    PatientListResponse,
    PatientSummary,
)


class PatientService:
    """Service layer for patient session history and summary listings."""

    def __init__(self, patient_repo: IPatientRepository):
        self.patient_repo = patient_repo

    def get_patient_history(self, patient_id: str) -> PatientHistoryResponse:
        """
        Retrieve complete session and result history for a given patient_id
        using IPatientRepository.
        """
        raw_history = self.patient_repo.get_patient_history(patient_id)
        
        sessions_list: List[PatientSessionHistoryItem] = []
        for item in raw_history:
            results_list = [
                ResultSummary(
                    repetitions=r.get("repetitions", 0),
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
                    started_at=item["started_at"],
                    status=item["status"],
                    results=results_list
                )
            )

        return PatientHistoryResponse(
            patient_id=patient_id,
            total_sessions=len(sessions_list),
            sessions=sessions_list
        )

    def list_patients(self) -> PatientListResponse:
        """
        Query distinct active patients and session counts from the IPatientRepository.
        """
        patients_list: List[PatientSummary] = []
        
        records = self.patient_repo.list_patients()

        for rec in records:
            patients_list.append(
                PatientSummary(
                    patient_id=rec["patient_id"],
                    total_sessions=rec["total_sessions"],
                    last_active=rec["last_active"]
                )
            )

        return PatientListResponse(
            total_patients=len(patients_list),
            patients=patients_list
        )
