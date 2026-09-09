"""
FastAPI router handling patient management and exercise assignment endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from backend.core.dependencies import get_patient_repo, get_assignment_repo
from backend.repositories.interfaces import IPatientRepository, IAssignmentRepository
from backend.services.patient_service import (
    PatientService,
    PatientNotFoundException,
    DuplicatePatientException,
    PatientNotActiveException,
    PatientValidationError,
)
from backend.services.assignment_service import (
    AssignmentService,
    AssignmentNotFoundException,
    DuplicateAssignmentException,
    UnknownExerciseException,
    InvalidTargetException,
)
from backend.services.session_service import InvalidSideException
from backend.schemas.patient import (
    PatientCreateRequest,
    PatientUpdateRequest,
    PatientResponse,
    PatientHistoryResponse,
    PatientListResponse,
)
from backend.schemas.assignment import (
    CreateAssignmentRequest,
    UpdateAssignmentRequest,
    AssignmentResponse,
    AssignmentListResponse,
)

router = APIRouter(
    prefix="/api/patients",
    tags=["Patients"]
)


def get_patient_service(patient_repo: IPatientRepository = Depends(get_patient_repo)) -> PatientService:
    return PatientService(patient_repo=patient_repo)


def get_assignment_service(
    assignment_repo: IAssignmentRepository = Depends(get_assignment_repo),
    patient_repo: IPatientRepository = Depends(get_patient_repo),
) -> AssignmentService:
    return AssignmentService(assignment_repo=assignment_repo, patient_repo=patient_repo)


# ---------------------------------------------------------------------------
# Patient Management Endpoints (Phase 6A)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PatientListResponse,
    summary="List patients registered in digital thread sessions"
)
def list_patients(
    service: PatientService = Depends(get_patient_service)
) -> PatientListResponse:
    return service.list_patients()


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient"
)
def create_patient(
    request: PatientCreateRequest,
    service: PatientService = Depends(get_patient_service)
) -> PatientResponse:
    try:
        return service.create_patient(request)
    except DuplicatePatientException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (PatientValidationError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Retrieve details for a specific patient"
)
def get_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service)
) -> PatientResponse:
    try:
        return service.get_patient(patient_id)
    except PatientNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update details for an existing patient"
)
def update_patient(
    patient_id: str,
    request: PatientUpdateRequest,
    service: PatientService = Depends(get_patient_service)
) -> PatientResponse:
    try:
        return service.update_patient(patient_id, request)
    except PatientNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (PatientValidationError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Soft-deactivate a patient (sets status to INACTIVE)"
)
def deactivate_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service)
) -> PatientResponse:
    try:
        return service.deactivate_patient(patient_id)
    except PatientNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{patient_id}/sessions",
    response_model=PatientHistoryResponse,
    summary="Retrieve session history for a specific patient"
)
def get_patient_sessions(
    patient_id: str,
    service: PatientService = Depends(get_patient_service)
) -> PatientHistoryResponse:
    return service.get_patient_history(patient_id)


# ---------------------------------------------------------------------------
# Patient Exercise Assignment Endpoints (Phase 6B)
# ---------------------------------------------------------------------------

@router.get(
    "/{patient_id}/exercises",
    response_model=AssignmentListResponse,
    summary="List exercises assigned to a specific patient"
)
def list_patient_exercises(
    patient_id: str,
    active_only: bool = Query(False, description="Filter for active assignments only"),
    service: AssignmentService = Depends(get_assignment_service)
) -> AssignmentListResponse:
    try:
        return service.list_assignments(patient_id, active_only=active_only)
    except PatientNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{patient_id}/exercises",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a rehabilitation exercise to a patient"
)
def create_patient_exercise(
    patient_id: str,
    request: CreateAssignmentRequest,
    service: AssignmentService = Depends(get_assignment_service)
) -> AssignmentResponse:
    try:
        return service.assign_exercise(patient_id, request)
    except PatientNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PatientNotActiveException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UnknownExerciseException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DuplicateAssignmentException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (InvalidSideException, InvalidTargetException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{patient_id}/exercises/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Retrieve a specific exercise assignment for a patient"
)
def get_patient_exercise(
    patient_id: str,
    assignment_id: int,
    service: AssignmentService = Depends(get_assignment_service)
) -> AssignmentResponse:
    try:
        return service.get_assignment(patient_id, assignment_id)
    except (PatientNotFoundException, AssignmentNotFoundException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/{patient_id}/exercises/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Update an existing exercise assignment"
)
def update_patient_exercise(
    patient_id: str,
    assignment_id: int,
    request: UpdateAssignmentRequest,
    service: AssignmentService = Depends(get_assignment_service)
) -> AssignmentResponse:
    try:
        return service.update_assignment(patient_id, assignment_id, request)
    except (PatientNotFoundException, AssignmentNotFoundException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InvalidTargetException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{patient_id}/exercises/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Soft-deactivate an exercise assignment (sets active to False)"
)
def deactivate_patient_exercise(
    patient_id: str,
    assignment_id: int,
    service: AssignmentService = Depends(get_assignment_service)
) -> AssignmentResponse:
    try:
        return service.deactivate_assignment(patient_id, assignment_id)
    except (PatientNotFoundException, AssignmentNotFoundException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
