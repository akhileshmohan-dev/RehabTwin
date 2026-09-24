from typing import Any, Dict, Optional
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from digital_thread.db import Database


class DigitalThread:
    """Database-agnostic digital-thread API for RehabTwin.

    Change DATABASE_URL from SQLite to PostgreSQL without changing callers.
    This class now acts as a backwards-compatible facade delegating to the Repository layer.
    """

    def __init__(self, database_url: Optional[str] = None):
        self.db = Database(database_url) if database_url else Database()
        self.db.create_schema()
        self.session_id: Optional[str] = None
        
        # Instantiate repositories using the existing Database abstraction
        self.patient_repo = SQLAlchemyPatientRepository(self.db)
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.telemetry_repo = SQLAlchemyTelemetryRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)

    def start_session(self, patient_id: str, exercise: str, side: str = "left", session_id: Optional[str] = None) -> str:
        sid = self.session_repo.start_session(patient_id, exercise, side, session_id)
        self.session_id = sid
        return sid

    def record_frame(
        self,
        frame_id: int,
        landmarks: Dict[str, Any],
        joint_angles: Dict[str, float],
        phase: Optional[str] = None,
    ) -> None:
        if not self.session_id:
            raise RuntimeError("No active digital-thread session.")
        self.telemetry_repo.record_frame(self.session_id, frame_id, landmarks, joint_angles, phase)

    def record_result(
        self,
        repetitions: int,
        rom_min: Optional[float],
        rom_max: Optional[float],
        rom_average: Optional[float],
        performance_score: Optional[float],
        feedback: str = "",
    ) -> None:
        if not self.session_id:
            raise RuntimeError("No active digital-thread session.")
        self.result_repo.record_result(
            self.session_id, repetitions, rom_min, rom_max, rom_average, performance_score, feedback
        )

    def end_session(self) -> None:
        if not self.session_id:
            return
        self.session_repo.end_session(self.session_id)
        self.session_id = None

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self.session_repo.get_session(session_id)

    def history(self, patient_id: str) -> list[Dict[str, Any]]:
        return self.patient_repo.get_patient_history(patient_id)

    def export_session(self, session_id: str, output_path: str) -> str:
        return self.session_repo.export_session(session_id, output_path)
