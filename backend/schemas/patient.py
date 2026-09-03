"""
Pydantic schemas for patient session history and patient listing.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ResultSummary(BaseModel):
    repetitions: int
    rom_min: Optional[float] = None
    rom_max: Optional[float] = None
    rom_average: Optional[float] = None
    performance_score: Optional[float] = None
    feedback: str = ""


class PatientSessionHistoryItem(BaseModel):
    session_id: str
    patient_id: str
    exercise: str
    started_at: str
    status: str
    results: List[ResultSummary] = []


class PatientHistoryResponse(BaseModel):
    patient_id: str
    total_sessions: int
    sessions: List[PatientSessionHistoryItem]


class PatientSummary(BaseModel):
    patient_id: str
    total_sessions: int
    last_active: Optional[str] = None


class PatientListResponse(BaseModel):
    total_patients: int
    patients: List[PatientSummary]
