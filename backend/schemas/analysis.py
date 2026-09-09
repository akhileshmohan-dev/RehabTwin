"""
Pydantic schemas for rehabilitation exercise catalog and frame analysis.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExerciseInfo(BaseModel):
    id: str
    name: str
    joint_angle: str
    movement_type: str
    description: str
    supported_sides: List[str] = Field(default_factory=lambda: ["left", "right"])
    side: Optional[str] = "left"


class ExerciseListResponse(BaseModel):
    total: int
    exercises: List[ExerciseInfo]


class ProcessFrameRequest(BaseModel):
    pose_frame: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured PoseFrame dictionary with 'angles', 'landmarks', and 'visibility' keys."
    )
    exercise_id: Optional[str] = Field(
        "elbow_flexion",
        description="Exercise identifier e.g. 'elbow_flexion', 'shoulder_flexion'"
    )
    side: Optional[str] = Field(
        "left",
        description="Target body side ('left' or 'right')"
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional session ID to validate side against session record"
    )
    smoothing_window: int = Field(5, ge=1, description="Window size for moving average smoothing")
    flexed_threshold: float = Field(100.0, description="Angle threshold in degrees for flexed state")
    extended_threshold: float = Field(160.0, description="Angle threshold in degrees for extended state")


class ROMResult(BaseModel):
    min_angle: Optional[float] = None
    max_angle: Optional[float] = None
    rom: Optional[float] = None


class PoseStatusInfo(BaseModel):
    is_valid: bool
    status: str
    message: str
    missing_landmarks: List[str] = Field(default_factory=list)
    low_visibility_landmarks: List[str] = Field(default_factory=list)


class AnalysisResultResponse(BaseModel):
    raw_angle: Optional[float] = None
    valid_angle: Optional[float] = None
    smoothed_angle: Optional[float] = None
    state: str
    repetitions: int
    rom: ROMResult
    pose_status: Optional[PoseStatusInfo] = None


class WebSocketTelemetryMessage(BaseModel):
    type: str = Field(..., description="Message type e.g. 'FRAME_ANALYSIS', 'SESSION_UPDATE'")
    session_id: str
    timestamp: float
    data: Dict[str, Any]
