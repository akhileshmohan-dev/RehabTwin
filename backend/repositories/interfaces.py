from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class RepositoryException(Exception):
    """Base exception for repository layer operations."""
    pass


class PatientNotFoundInRepoException(RepositoryException):
    """Raised by repositories when an operation requires an existing patient."""
    def __init__(self, patient_id: str):
        self.patient_id = patient_id
        super().__init__(f"Patient '{patient_id}' not found in repository.")


class IPatientRepository(ABC):
    @abstractmethod
    def create_patient(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new persistent Patient record.
        Returns the created patient dict.
        """
        pass

    @abstractmethod
    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve patient record by patient_id.
        Returns None if patient does not exist.
        """
        pass

    @abstractmethod
    def list_patients(self) -> List[Dict[str, Any]]:
        """
        Return a list of dicts with patient metadata and session stats:
        - patient_id (str)
        - name (str)
        - status (str)
        - age (Optional[int])
        - gender (Optional[str])
        - phone (Optional[str])
        - email (Optional[str])
        - notes (Optional[str])
        - created_at (str)
        - updated_at (str)
        - total_sessions (int)
        - active_sessions (int)
        - completed_sessions (int)
        - last_active (Optional[str])  # ISO datetime string
        - average_performance_score (Optional[float])
        """
        pass

    @abstractmethod
    def update_patient(self, patient_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update attributes of an existing patient.
        Returns updated patient dict, or None if patient not found.
        """
        pass

    @abstractmethod
    def deactivate_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Soft-deactivate patient (status='INACTIVE').
        Preserves historical sessions and results.
        Returns updated patient dict, or None if patient not found.
        """
        pass

    @abstractmethod
    def patient_exists(self, patient_id: str) -> bool:
        """Return True if patient_id exists in persistent store."""
        pass

    @abstractmethod
    def get_patient_history(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Return a list of session history dicts for the patient.
        """
        pass

    @abstractmethod
    def get_system_overview(self) -> Dict[str, Any]:
        """
        Return system-wide summary statistics dict:
        - total_patients (int)
        - total_sessions (int)
        - active_patients (int)
        - average_performance_score (Optional[float])
        """
        pass


class IAssignmentRepository(ABC):
    @abstractmethod
    def assign_exercise(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new PatientExerciseAssignment record.
        Returns the created assignment dict.
        """
        pass

    @abstractmethod
    def get_assignment(self, assignment_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve assignment by ID. Returns None if not found."""
        pass

    @abstractmethod
    def get_assignment_by_exercise_and_side(
        self, patient_id: str, exercise_id: str, side: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check for an existing assignment for a specific (patient_id, exercise_id, side).
        Returns assignment dict or None.
        """
        pass

    @abstractmethod
    def list_assignments(self, patient_id: str, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        List exercise assignments for a specific patient.
        If active_only is True, return only assignments where active=True.
        """
        pass

    @abstractmethod
    def update_assignment(self, assignment_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update fields of an assignment (e.g. target_rom, target_repetitions, sessions_per_day, notes, active).
        Returns updated assignment dict, or None if not found.
        """
        pass

    @abstractmethod
    def deactivate_assignment(self, assignment_id: int) -> Optional[Dict[str, Any]]:
        """
        Soft-deactivate an assignment (active=False).
        Returns updated assignment dict, or None if not found.
        """
        pass


class ISessionRepository(ABC):
    @abstractmethod
    def start_session(self, patient_id: str, exercise: str, side: str = "left", session_id: Optional[str] = None) -> str:
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
