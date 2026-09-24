"""
Pydantic schemas for session lifecycle management and telemetry.
"""
<<<<<<< HEAD
from typing import Any, Dict, Optional
=======
from typing import Any, Dict, List, Optional
>>>>>>> 8ca8ed2 (3D model 1st stage)
from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    patient_id: str = Field(..., description="Unique patient identifier", json_schema_extra={"example": "PATIENT-001"})
    assignment_id: Optional[int] = Field(None, description="Authoritative exercise assignment ID", json_schema_extra={"example": 1})
    exercise: Optional[str] = Field(None, description="Exercise key e.g. 'elbow_flexion'", json_schema_extra={"example": "elbow_flexion"})
    side: Optional[str] = Field(None, description="Body side: 'left' or 'right'", json_schema_extra={"example": "left"})
    session_id: Optional[str] = Field(None, description="Optional custom session ID", json_schema_extra={"example": "S-001"})


class StartSessionResponse(BaseModel):
    session_id: str
    patient_id: str
    exercise: str
    side: str = "left"
    status: str = "ACTIVE"
    started_at: Optional[str] = None
    assignment_id: Optional[int] = None
    target_rom: Optional[float] = None
    target_repetitions: Optional[int] = None


class SessionResponse(BaseModel):
    session_id: str
    patient_id: str
    exercise: str
    side: str = "left"
    started_at: str
    ended_at: Optional[str] = None
    status: str


class SessionResultData(BaseModel):
    exercise: str
    side: str = "left"
    repetitions: int
    rom_min: Optional[float] = None
    rom_max: Optional[float] = None
    rom_average: Optional[float] = None
    performance_score: Optional[float] = None
    feedback: str = ""


class EndSessionResponse(BaseModel):
    session_id: str
    status: str = "COMPLETED"
    message: str
    result: Optional[SessionResultData] = None


class RecordFrameRequest(BaseModel):
    frame_id: int = Field(..., description="Sequential frame index", ge=1)
    landmarks: Dict[str, Any] = Field(..., description="Pose landmark coordinates")
    joint_angles: Dict[str, float] = Field(..., description="Calculated joint angles")
    phase: Optional[str] = Field(None, description="Current movement phase e.g. 'FLEXED', 'EXTENDED'")


class RecordFrameResponse(BaseModel):
    session_id: str
    frame_id: int
    message: str = "Frame recorded successfully"


<<<<<<< HEAD
=======
class SessionFrameData(BaseModel):
    frame_id: int
    t_ms: float = Field(..., description="Milliseconds elapsed since the first stored frame")
    landmarks: Dict[str, Any] = Field(
        ...,
        description="Landmark coords normalized to 0-1 for x,y; z and visibility preserved",
    )
    joint_angles: Dict[str, float] = Field(default_factory=dict)
    phase: Optional[str] = None


class SessionFramesResponse(BaseModel):
    session_id: str
    exercise: str
    side: str = "left"
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    frame_count: int
    frames: List[SessionFrameData]


>>>>>>> 8ca8ed2 (3D model 1st stage)
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
