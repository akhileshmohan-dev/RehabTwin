from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class IPatientRepository(ABC):
    @abstractmethod
    def list_patients(self) -> List[Dict[str, Any]]:
        """
        Return a list of dicts with keys:
        - patient_id (str)
        - total_sessions (int)
        - last_active (str)  # ISO datetime string
        """
        pass

    @abstractmethod
    def get_patient_history(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Return a list of session history dicts for the patient.
        """
        pass


class ISessionRepository(ABC):
    @abstractmethod
    def start_session(self, patient_id: str, exercise: str, session_id: Optional[str] = None) -> str:
        """Create a session and return the new session_id."""
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieve a single session by id.
        Raises KeyError if not found.
        """
        pass

    @abstractmethod
    def end_session(self, session_id: str) -> None:
        """Mark a session as completed."""
        pass

    @abstractmethod
    def get_sessions_by_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        """Return all sessions for a specific patient."""
        pass

    @abstractmethod
    def export_session(self, session_id: str, output_path: str) -> str:
        """
        Export full session details including frames and results to JSON at output_path.
        Returns the absolute path.
        Raises KeyError if not found.
        """
        pass


class ITelemetryRepository(ABC):
    @abstractmethod
    def record_frame(
        self,
        session_id: str,
        frame_id: int,
        landmarks: Dict[str, Any],
        joint_angles: Dict[str, float],
        phase: Optional[str] = None,
    ) -> None:
        """Persist a single frame of telemetry."""
        pass


class IResultRepository(ABC):
    @abstractmethod
    def record_result(
        self,
        session_id: str,
        repetitions: int,
        rom_min: Optional[float],
        rom_max: Optional[float],
        rom_average: Optional[float],
        performance_score: Optional[float],
        feedback: str = "",
    ) -> None:
        """
        Persist or update the final result for a session.
        Must be idempotent (update if exists).
        """
        pass

    @abstractmethod
    def get_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the result for a given session, if any."""
        pass
