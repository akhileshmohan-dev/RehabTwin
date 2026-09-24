"""
Pydantic schemas for patient exercise assignments.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class CreateAssignmentRequest(BaseModel):
    exercise_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        json_schema_extra={"example": "elbow_flexion"}
    )
    side: str = Field(
        "left",
        json_schema_extra={"example": "left"}
    )
    target_rom: Optional[float] = Field(
        None,
        gt=0,
        le=360.0,
        json_schema_extra={"example": 140.0}
    )
    target_repetitions: Optional[int] = Field(
        None,
        gt=0,
        le=1000,
        json_schema_extra={"example": 10}
    )
    sessions_per_day: Optional[int] = Field(
        1,
        gt=0,
        le=24,
        json_schema_extra={"example": 2}
    )
    notes: Optional[str] = Field(
        "",
        json_schema_extra={"example": "Focus on smooth movement"}
    )

    @field_validator("exercise_id")
    @classmethod
    def validate_exercise_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("exercise_id cannot be empty.")
        return cleaned

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'.")
        return cleaned


class UpdateAssignmentRequest(BaseModel):
    target_rom: Optional[float] = Field(None, gt=0, le=360.0)
    target_repetitions: Optional[int] = Field(None, gt=0, le=1000)
    sessions_per_day: Optional[int] = Field(None, gt=0, le=24)
    notes: Optional[str] = None
    active: Optional[bool] = None


class AssignmentResponse(BaseModel):
    id: int
    patient_id: str
    exercise_id: str
    exercise_name: str
    side: str
    target_rom: Optional[float] = None
    target_repetitions: Optional[int] = None
    sessions_per_day: Optional[int] = 1
    notes: str = ""
    active: bool = True
    assigned_at: Optional[str] = None
    updated_at: Optional[str] = None


class AssignmentListResponse(BaseModel):
    patient_id: str
    total_assignments: int
    assignments: List[AssignmentResponse]
