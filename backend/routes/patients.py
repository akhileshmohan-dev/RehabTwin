"""
FastAPI router handling patient endpoints.
"""
from fastapi import APIRouter, Depends, status

from digital_thread.thread import DigitalThread
from backend.core.dependencies import get_digital_thread
from backend.services.patient_service import PatientService
from backend.schemas.patient import PatientHistoryResponse, PatientListResponse

router = APIRouter(
    prefix="/api/patients",
    tags=["Patients"]
)


def get_patient_service(dt: DigitalThread = Depends(get_digital_thread)) -> PatientService:
    return PatientService(digital_thread=dt)


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
