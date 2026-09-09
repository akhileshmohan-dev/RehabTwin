"""
Pydantic schemas for patient session history and patient listing.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ResultSummary(BaseModel):
    repetitions: int
    side: Optional[str] = "left"
    rom_min: Optional[float] = None
    rom_max: Optional[float] = None
    rom_average: Optional[float] = None
    performance_score: Optional[float] = None
    feedback: str = ""


class PatientSessionHistoryItem(BaseModel):
    session_id: str
    patient_id: str
    exercise: str
    side: str = "left"
    started_at: str
    ended_at: Optional[str] = None
    status: str
    results: List[ResultSummary] = []


class PatientHistoryResponse(BaseModel):
    patient_id: str
    total_sessions: int
    sessions: List[PatientSessionHistoryItem]


class PatientSummary(BaseModel):
    patient_id: str
    total_sessions: int
    active_sessions: int = 0
    completed_sessions: int = 0
    last_active: Optional[str] = None
    average_performance_score: Optional[float] = None


class PatientListResponse(BaseModel):
    total_patients: int
    total_sessions: int = 0
    active_patients: int = 0
    average_performance_score: Optional[float] = None
    patients: List[PatientSummary]
