"""
Session service orchestrating session lifecycle and telemetry persistence
via DigitalThread API.
"""
from typing import Any, Dict, Optional
import os

from digital_thread.thread import DigitalThread
from backend.schemas.session import (
    StartSessionRequest,
    StartSessionResponse,
    SessionResponse,
    EndSessionResponse,
    RecordFrameRequest,
    RecordFrameResponse,
    RecordResultRequest,
    RecordResultResponse,
    ExportSessionResponse,
)


class SessionNotFoundException(Exception):
    """Raised when a requested session_id does not exist in DigitalThread."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' not found.")


class SessionService:
    """Service layer wrapping DigitalThread for session business logic."""

    def __init__(self, digital_thread: Optional[DigitalThread] = None):
        self.digital_thread = digital_thread or DigitalThread()

    def start_session(self, request: StartSessionRequest) -> StartSessionResponse:
        """Start a new rehabilitation session in DigitalThread."""
        sid = self.digital_thread.start_session(
            patient_id=request.patient_id,
            exercise=request.exercise,
            session_id=request.session_id
        )
        session_data = self.digital_thread.get_session(sid)
        return StartSessionResponse(
            session_id=sid,
            patient_id=session_data["patient_id"],
            exercise=session_data["exercise"],
            status=session_data["status"],
            started_at=session_data.get("started_at")
        )

    def get_session(self, session_id: str) -> SessionResponse:
        """Retrieve details of an existing session."""
        try:
            session_data = self.digital_thread.get_session(session_id)
            return SessionResponse(
                session_id=session_data["session_id"],
                patient_id=session_data["patient_id"],
                exercise=session_data["exercise"],
                started_at=session_data["started_at"],
                ended_at=session_data.get("ended_at"),
                status=session_data["status"]
            )
        except KeyError:
            raise SessionNotFoundException(session_id)

    def end_session(self, session_id: str) -> EndSessionResponse:
        """End an active session in DigitalThread."""
        # Ensure session exists first
        self.get_session(session_id)
        
        # Set active session on DigitalThread instance and end it
        self.digital_thread.session_id = session_id
        self.digital_thread.end_session()

        return EndSessionResponse(
            session_id=session_id,
            status="COMPLETED",
            message=f"Session '{session_id}' ended successfully."
        )

    def record_frame(self, session_id: str, request: RecordFrameRequest) -> RecordFrameResponse:
        """Record telemetry frame data for an active session."""
        # Verify session existence
        self.get_session(session_id)

        self.digital_thread.session_id = session_id
        self.digital_thread.record_frame(
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
        self.get_session(session_id)

        self.digital_thread.session_id = session_id
        self.digital_thread.record_result(
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

        actual_path = self.digital_thread.export_session(
            session_id=session_id,
            output_path=output_path
        )
        return ExportSessionResponse(
            session_id=session_id,
            output_path=actual_path,
            message=f"Session exported successfully to {actual_path}"
        )