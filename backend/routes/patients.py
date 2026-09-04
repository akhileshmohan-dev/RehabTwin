"""
FastAPI router handling patient endpoints.
"""
from fastapi import APIRouter, Depends, status

from backend.core.dependencies import get_patient_repo
from backend.repositories.interfaces import IPatientRepository
from backend.services.patient_service import PatientService
from backend.schemas.patient import PatientHistoryResponse, PatientListResponse

router = APIRouter(
    prefix="/api/patients",
    tags=["Patients"]
)


def get_patient_service(patient_repo: IPatientRepository = Depends(get_patient_repo)) -> PatientService:
    return PatientService(patient_repo=patient_repo)


@router.get(
    "",
    response_model=PatientListResponse,
    summary="List patients registered in digital thread sessions"
)
def list_patients(
    service: PatientService = Depends(get_patient_service)
) -> PatientListResponse:
    return service.list_patients()


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
