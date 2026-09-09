"""
FastAPI router handling session lifecycle and frame/result recording endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.core.dependencies import (
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
    get_patient_repo,
    get_assignment_repo,
)
from backend.repositories.interfaces import (
    ISessionRepository,
    ITelemetryRepository,
    IResultRepository,
    IPatientRepository,
    IAssignmentRepository,
)
from backend.services.session_service import (
    SessionService,
    SessionNotFoundException,
    SessionNotActiveException,
    SessionNoResultException,
    InvalidExerciseException,
    InvalidSideException,
)
from backend.services.patient_service import PatientNotActiveException, PatientNotFoundException
from backend.services.assignment_service import ExerciseNotAssignedException, AssignmentNotFoundException
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

router = APIRouter(
    prefix="/api/sessions",
    tags=["Sessions"]
)


def get_session_service(
    session_repo: ISessionRepository = Depends(get_session_repo),
    telemetry_repo: ITelemetryRepository = Depends(get_telemetry_repo),
    result_repo: IResultRepository = Depends(get_result_repo),
    patient_repo: IPatientRepository = Depends(get_patient_repo),
    assignment_repo: IAssignmentRepository = Depends(get_assignment_repo),
) -> SessionService:
    return SessionService(
        session_repo=session_repo,
        telemetry_repo=telemetry_repo,
        result_repo=result_repo,
        patient_repo=patient_repo,
        assignment_repo=assignment_repo,
    )


@router.post(
    "",
    response_model=StartSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new rehabilitation session"
)
def start_session(
    request: StartSessionRequest,
    service: SessionService = Depends(get_session_service)
) -> StartSessionResponse:
    try:
        return service.start_session(request)
    except (InvalidExerciseException, InvalidSideException) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except (PatientNotActiveException, ExerciseNotAssignedException, AssignmentNotFoundException) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PatientNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get details of a session"
)
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service)
) -> SessionResponse:
    try:
        return service.get_session(session_id)
    except SessionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' does not exist."
        )


@router.post(
    "/{session_id}/end",
    response_model=EndSessionResponse,
    summary="End an active session"
)
def end_session(
    session_id: str,
    service: SessionService = Depends(get_session_service)
) -> EndSessionResponse:
    try:
        return service.end_session(session_id)
    except SessionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' does not exist."
        )
    except SessionNoResultException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{session_id}/frames",
    response_model=RecordFrameResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record pose frame telemetry for a session"
)
def record_frame(
    session_id: str,
    request: RecordFrameRequest,
    service: SessionService = Depends(get_session_service)
) -> RecordFrameResponse:
    try:
        return service.record_frame(session_id, request)
    except SessionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' does not exist."
        )
    except SessionNotActiveException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/{session_id}/results",
    response_model=RecordResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record performance results for a session"
)
def record_result(
    session_id: str,
    request: RecordResultRequest,
    service: SessionService = Depends(get_session_service)
) -> RecordResultResponse:
    try:
        return service.record_result(session_id, request)
    except SessionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' does not exist."
        )
    except SessionNotActiveException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/{session_id}/export",
    response_model=ExportSessionResponse,
    summary="Export session data to JSON file"
)
def export_session(
    session_id: str,
    output_path: Optional[str] = None,
    service: SessionService = Depends(get_session_service)
) -> ExportSessionResponse:
    try:
        return service.export_session(session_id, output_path)
    except SessionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' does not exist."
        )