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


class ExerciseListResponse(BaseModel):
    total: int
    exercises: List[ExerciseInfo]


class ProcessFrameRequest(BaseModel):
    pose_frame: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured PoseFrame dictionary with 'angles', 'landmarks', and 'visibility' keys."
    )
    smoothing_window: int = Field(5, ge=1, description="Window size for moving average smoothing")
    flexed_threshold: float = Field(100.0, description="Angle threshold in degrees for flexed state")
    extended_threshold: float = Field(160.0, description="Angle threshold in degrees for extended state")


class ROMResult(BaseModel):
    min_angle: Optional[float] = None
    max_angle: Optional[float] = None
    rom: Optional[float] = None


class AnalysisResultResponse(BaseModel):
    raw_angle: Optional[float] = None
    valid_angle: Optional[float] = None
    smoothed_angle: Optional[float] = None
    state: str
    repetitions: int
    rom: ROMResult


class WebSocketTelemetryMessage(BaseModel):
    type: str = Field(..., description="Message type e.g. 'FRAME_ANALYSIS', 'SESSION_UPDATE'")
    session_id: str
    timestamp: float
    data: Dict[str, Any]
