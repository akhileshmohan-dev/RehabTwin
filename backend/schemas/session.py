"""
Pydantic schemas for session lifecycle management and telemetry.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    patient_id: str = Field(..., description="Unique patient identifier", example="PATIENT-001")
    exercise: str = Field(..., description="Exercise key e.g. 'elbow_flexion'", example="elbow_flexion")
    session_id: Optional[str] = Field(None, description="Optional custom session ID", example="S-001")


class StartSessionResponse(BaseModel):
    session_id: str
    patient_id: str
    exercise: str
    status: str = "ACTIVE"
    started_at: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    patient_id: str
    exercise: str
    started_at: str
    ended_at: Optional[str] = None
    status: str


class EndSessionResponse(BaseModel):
    session_id: str
    status: str = "COMPLETED"
    message: str


class RecordFrameRequest(BaseModel):
    frame_id: int = Field(..., description="Sequential frame index", ge=1)
    landmarks: Dict[str, Any] = Field(..., description="Pose landmark coordinates")
    joint_angles: Dict[str, float] = Field(..., description="Calculated joint angles")
    phase: Optional[str] = Field(None, description="Current movement phase e.g. 'FLEXED', 'EXTENDED'")


class RecordFrameResponse(BaseModel):
    session_id: str
    frame_id: int
    message: str = "Frame recorded successfully"


class RecordResultRequest(BaseModel):
    repetitions: int = Field(..., ge=0, description="Total repetitions performed")
    rom_min: Optional[float] = Field(None, description="Minimum joint angle recorded")
    rom_max: Optional[float] = Field(None, description="Maximum joint angle recorded")
    rom_average: Optional[float] = Field(None, description="Average Range of Motion")
    performance_score: Optional[float] = Field(None, description="Performance evaluation score percentage")
    feedback: str = Field("", description="Therapist or automated feedback text")


class RecordResultResponse(BaseModel):
    session_id: str
    message: str = "Session result recorded successfully"


class ExportSessionResponse(BaseModel):
    session_id: str
    output_path: str
    message: str = "Session exported successfully"
