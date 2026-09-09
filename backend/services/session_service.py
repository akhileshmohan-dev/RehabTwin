"""
Session service orchestrating session lifecycle and telemetry persistence
via repository interfaces.
"""
from typing import Any, Dict, Optional
import os
from rehabilitation.exercises import EXERCISE_REGISTRY

from backend.repositories.interfaces import (
    ISessionRepository,
    ITelemetryRepository,
    IResultRepository,
    IPatientRepository,
    IAssignmentRepository,
)
from backend.schemas.session import (
    StartSessionRequest,
    StartSessionResponse,
    SessionResponse,
    SessionResultData,
    EndSessionResponse,
    RecordFrameRequest,
    RecordFrameResponse,
    RecordResultRequest,
    RecordResultResponse,
    ExportSessionResponse,
)


class SessionNotFoundException(Exception):
    """Raised when a requested session_id does not exist."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' not found.")


class SessionNotActiveException(Exception):
    """Raised when attempting to record data to a non-ACTIVE session."""
    def __init__(self, session_id: str, status: str):
        self.session_id = session_id
        self.status = status
        super().__init__(f"Session '{session_id}' is not ACTIVE (current status: {status}).")


class InvalidExerciseException(Exception):
    """Raised when attempting to start a session with an unknown/unregistered exercise."""
    def __init__(self, exercise: str):
        self.exercise = exercise
        super().__init__(f"Unknown or unsupported exercise: '{exercise}'.")


class InvalidSideException(Exception):
    """Raised when an invalid side is specified."""
    def __init__(self, side: str):
        self.side = side
        super().__init__(f"Invalid side '{side}'. Must be 'left' or 'right'.")


class SessionNoResultException(Exception):
    """Raised when attempting to end an ACTIVE session that has no recorded result."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' cannot be ended because no result has been recorded.")


VALID_SIDES = {"left", "right"}


def normalize_side(side: Optional[str]) -> str:
    """Normalize and validate exercise side."""
    if side is None:
        return "left"
    cleaned = side.strip().lower()
    if cleaned not in VALID_SIDES:
        raise InvalidSideException(side)
    return cleaned


class SessionService:
    """Service layer wrapping repository interfaces for session business logic."""

    def __init__(
        self,
        session_repo: ISessionRepository,
        telemetry_repo: ITelemetryRepository,
        result_repo: IResultRepository,
        patient_repo: Optional[IPatientRepository] = None,
        assignment_repo: Optional[IAssignmentRepository] = None,
    ):
        self.session_repo = session_repo
        self.telemetry_repo = telemetry_repo
        self.result_repo = result_repo
        self.patient_repo = patient_repo
        self.assignment_repo = assignment_repo

    def start_session(self, request: StartSessionRequest) -> StartSessionResponse:
        """Start a new rehabilitation session."""
        from backend.services.patient_service import (
            PatientNotFoundException,
            PatientNotActiveException,
        )
        from backend.services.assignment_service import (
            AssignmentNotFoundException,
            ExerciseNotAssignedException,
        )
        from backend.repositories.interfaces import PatientNotFoundInRepoException

        # 1. Patient verification: patient must exist and be ACTIVE
        if self.patient_repo:
            patient = self.patient_repo.get_patient(request.patient_id)
            if not patient:
                raise PatientNotFoundException(request.patient_id)
            if patient.get("status") == "INACTIVE":
                raise PatientNotActiveException(request.patient_id)

        target_rom: Optional[float] = None
        target_repetitions: Optional[int] = None
        assignment_id: Optional[int] = None
        exercise: str = ""
        side: str = ""

        # 2. Assignment verification
        if request.assignment_id is not None:
            if not self.assignment_repo:
                raise ExerciseNotAssignedException("Exercise assignment repository not configured.")
            assignment = self.assignment_repo.get_assignment(request.assignment_id)
            if not assignment or assignment.get("patient_id") != request.patient_id:
                raise AssignmentNotFoundException(request.assignment_id)
            if not assignment.get("active"):
                raise ExerciseNotAssignedException(f"Assignment '{request.assignment_id}' is inactive.")

            exercise = assignment["exercise_id"]
            side = assignment["side"]
            assignment_id = assignment["id"]
            target_rom = assignment.get("target_rom")
            target_repetitions = assignment.get("target_repetitions")
        else:
            if not request.exercise:
                raise InvalidExerciseException("Exercise must be specified when assignment_id is omitted.")
            if request.exercise not in EXERCISE_REGISTRY:
                raise InvalidExerciseException(request.exercise)
            side = normalize_side(request.side)
            exercise = request.exercise

            if self.assignment_repo:
                active_assignments = self.assignment_repo.list_assignments(request.patient_id, active_only=True)
                matches = [
                    a for a in active_assignments
                    if a["exercise_id"] == exercise and a["side"] == side
                ]
                if not matches:
                    raise ExerciseNotAssignedException(
                        f"Exercise '{exercise}' ({side}) is not assigned to patient '{request.patient_id}'."
                    )
                assignment = matches[0]
                assignment_id = assignment["id"]
                target_rom = assignment.get("target_rom")
                target_repetitions = assignment.get("target_repetitions")

        if exercise not in EXERCISE_REGISTRY:
            raise InvalidExerciseException(exercise)

        try:
            sid = self.session_repo.start_session(
                patient_id=request.patient_id,
                exercise=exercise,
                side=side,
                session_id=request.session_id
            )
        except PatientNotFoundInRepoException:
            raise PatientNotFoundException(request.patient_id)

        session_data = self.session_repo.get_session(sid)
        return StartSessionResponse(
            session_id=sid,
            patient_id=session_data["patient_id"],
            exercise=session_data["exercise"],
            side=session_data.get("side", "left"),
            status=session_data["status"],
            started_at=session_data.get("started_at"),
            assignment_id=assignment_id,
            target_rom=target_rom,
            target_repetitions=target_repetitions,
        )

    def get_session(self, session_id: str) -> SessionResponse:
        """Retrieve details of an existing session."""
        try:
            session_data = self.session_repo.get_session(session_id)
            return SessionResponse(
                session_id=session_data["session_id"],
                patient_id=session_data["patient_id"],
                exercise=session_data["exercise"],
                side=session_data.get("side", "left"),
                started_at=session_data["started_at"],
                ended_at=session_data.get("ended_at"),
                status=session_data["status"]
            )
        except KeyError:
            raise SessionNotFoundException(session_id)

    def end_session(self, session_id: str) -> EndSessionResponse:
        """End an active session."""
        # Ensure session exists first
        session = self.get_session(session_id)

        raw_result = self.result_repo.get_result(session_id)

        # Critical: An ACTIVE session with NO persisted Result must NOT be marked COMPLETED
        if session.status == "ACTIVE" and raw_result is None:
            raise SessionNoResultException(session_id)

        self.session_repo.end_session(session_id)

        result_data: Optional[SessionResultData] = None
        if raw_result is not None:
            result_data = SessionResultData(
                exercise=str(raw_result.get("exercise", "")),
                side=str(raw_result.get("side", "left")),
                repetitions=int(raw_result.get("repetitions", 0)),
                rom_min=float(raw_result["rom_min"]) if raw_result.get("rom_min") is not None else None,
                rom_max=float(raw_result["rom_max"]) if raw_result.get("rom_max") is not None else None,
                rom_average=float(raw_result["rom_average"]) if raw_result.get("rom_average") is not None else None,
                performance_score=float(raw_result["performance_score"]) if raw_result.get("performance_score") is not None else None,
                feedback=str(raw_result.get("feedback", "")),
            )

        return EndSessionResponse(
            session_id=session_id,
            status="COMPLETED",
            message=f"Session '{session_id}' ended successfully.",
            result=result_data,
        )

    def record_frame(self, session_id: str, request: RecordFrameRequest) -> RecordFrameResponse:
        """Record telemetry frame data for an active session."""
        # Verify session existence and ACTIVE status
        session = self.get_session(session_id)
        if session.status != "ACTIVE":
            raise SessionNotActiveException(session_id, session.status)

        self.telemetry_repo.record_frame(
            session_id=session_id,
            frame_id=request.frame_id,
            landmarks=request.landmarks,
            joint_angles=request.joint_angles,
            phase=request.phase
        )
        return RecordFrameResponse(
            session_id=session_id,
            frame_id=request.frame_id,
            message="Frame recorded successfully."
        )

    def record_result(self, session_id: str, request: RecordResultRequest) -> RecordResultResponse:
        """Record final performance metrics/results for a session."""
        session = self.get_session(session_id)
        if session.status != "ACTIVE":
            raise SessionNotActiveException(session_id, session.status)

        self.result_repo.record_result(
            session_id=session_id,
            repetitions=request.repetitions,
            rom_min=request.rom_min,
            rom_max=request.rom_max,
            rom_average=request.rom_average,
            performance_score=request.performance_score,
            feedback=request.feedback
        )
        return RecordResultResponse(
            session_id=session_id,
            message="Result recorded successfully."
        )

    def export_session(self, session_id: str, output_path: Optional[str] = None) -> ExportSessionResponse:
        """Export session payload (frames and results) to a JSON file."""
        self.get_session(session_id)

        if not output_path:
            export_dir = os.path.join(os.getcwd(), "data", "exports")
            output_path = os.path.join(export_dir, f"{session_id}_export.json")

        actual_path = self.session_repo.export_session(
            session_id=session_id,
            output_path=output_path
        )
        return ExportSessionResponse(
            session_id=session_id,
            output_path=actual_path,
            message=f"Session exported successfully to {actual_path}"
        )