"""
Patient service handling patient session history retrieval and patient indexing
via DigitalThread persistence layer.
"""
from typing import List, Optional
from sqlalchemy import func

from digital_thread.thread import DigitalThread
from backend.schemas.patient import (
    PatientHistoryResponse,
    PatientSessionHistoryItem,
    ResultSummary,
    PatientListResponse,
    PatientSummary,
)


class PatientService:
    """Service layer for patient session history and summary listings."""

    def __init__(self, digital_thread: Optional[DigitalThread] = None):
        self.digital_thread = digital_thread or DigitalThread()

    def get_patient_history(self, patient_id: str) -> PatientHistoryResponse:
        """
        Retrieve complete session and result history for a given patient_id
        using DigitalThread.history().
        """
        raw_history = self.digital_thread.history(patient_id)
        
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
        Query distinct active patients and session counts from the DigitalThread database.
        """
        patients_list: List[PatientSummary] = []
        
        with self.digital_thread.db.session() as db:
            from digital_thread.models import Session
            
            # Group sessions by patient_id to summarize session counts and latest activity
            records = (
                db.query(
                    Session.patient_id,
                    func.count(Session.session_id).label("session_count"),
                    func.max(Session.started_at).label("last_active")
                )
                .group_by(Session.patient_id)
                .all()
            )

            for rec in records:
                last_active_str = rec.last_active.isoformat() if rec.last_active else None
                patients_list.append(
                    PatientSummary(
                        patient_id=rec.patient_id,
                        total_sessions=rec.session_count,
                        last_active=last_active_str
                    )
                )

        return PatientListResponse(
            total_patients=len(patients_list),
            patients=patients_list
        )
