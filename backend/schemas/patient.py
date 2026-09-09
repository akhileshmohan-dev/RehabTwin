"""
Pydantic schemas for patient management, session history, and patient listing.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class PatientCreateRequest(BaseModel):
    patient_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        json_schema_extra={"example": "P100"}
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        json_schema_extra={"example": "John Doe"}
    )
    age: Optional[int] = Field(
        None,
        ge=0,
        le=150,
        json_schema_extra={"example": 45}
    )
    gender: Optional[str] = Field(
        None,
        max_length=32,
        json_schema_extra={"example": "male"}
    )
    phone: Optional[str] = Field(
        None,
        max_length=32,
        json_schema_extra={"example": "+1-555-0100"}
    )
    email: Optional[str] = Field(
        None,
        max_length=128,
        json_schema_extra={"example": "john@example.com"}
    )
    notes: Optional[str] = Field(
        None,
        json_schema_extra={"example": "Post-surgery recovery plan"}
    )
    status: str = Field(
        "ACTIVE",
        json_schema_extra={"example": "ACTIVE"}
    )

    @field_validator("patient_id")
    @classmethod
    def validate_patient_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("patient_id cannot be empty.")
        return cleaned

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("name cannot be empty.")
        return cleaned

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        upper_v = v.strip().upper()
        if upper_v not in ("ACTIVE", "INACTIVE"):
            raise ValueError("status must be 'ACTIVE' or 'INACTIVE'.")
        return upper_v


class PatientUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = Field(None, max_length=32)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=128)
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("name cannot be empty.")
            return cleaned
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            upper_v = v.strip().upper()
            if upper_v not in ("ACTIVE", "INACTIVE"):
                raise ValueError("status must be 'ACTIVE' or 'INACTIVE'.")
            return upper_v
        return v


class PatientResponse(BaseModel):
    patient_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


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
    name: Optional[str] = None
    status: str = "ACTIVE"
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    total_sessions: int = 0
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
