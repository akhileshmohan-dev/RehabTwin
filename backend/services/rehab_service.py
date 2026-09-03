"""
Rehabilitation service consuming core exercise catalog and analysis pipeline
from the rehabilitation module.
"""
from typing import Dict, Optional, Any

from rehabilitation.exercises import EXERCISES, get_exercise
from rehabilitation.analysis_pipeline import ElbowAnalysisPipeline

from backend.schemas.analysis import (
    ExerciseInfo,
    ExerciseListResponse,
    ProcessFrameRequest,
    AnalysisResultResponse,
    ROMResult,
)


class RehabService:
    """
    Service adapter for rehabilitation domain operations.
    Consumes existing core functions from rehabilitation/ without modifying algorithms.
    """

    def __init__(self):
        # Cache default pipeline instances or construct on request
        pass

    def list_exercises(self) -> ExerciseListResponse:
        """Return catalog of available rehabilitation exercise definitions."""
        exercises_list = []
        for ex_id, info in EXERCISES.items():
            exercises_list.append(
                ExerciseInfo(
                    id=ex_id,
                    name=info["name"],
                    joint_angle=info["joint_angle"],
                    movement_type=info["movement_type"],
                    description=info["description"]
                )
            )
        return ExerciseListResponse(
            total=len(exercises_list),
            exercises=exercises_list
        )

    def get_exercise_details(self, exercise_id: str) -> ExerciseInfo:
        """Retrieve details for a specific exercise ID."""
        try:
            info = get_exercise(exercise_id)
            return ExerciseInfo(
                id=exercise_id,
                name=info["name"],
                joint_angle=info["joint_angle"],
                movement_type=info["movement_type"],
                description=info["description"]
            )
        except ValueError as exc:
            raise KeyError(str(exc))

    def process_pose_frame(self, request: ProcessFrameRequest) -> AnalysisResultResponse:
        """
        Process a single PoseFrame through the core ElbowAnalysisPipeline.
        Pure analysis responsibility — does NOT perform database persistence.
        """
        pipeline = ElbowAnalysisPipeline(
            smoothing_window=request.smoothing_window,
            flexed_threshold=request.flexed_threshold,
            extended_threshold=request.extended_threshold
        )

        analysis_dict = pipeline.process(request.pose_frame)

        rom_data = analysis_dict.get("rom", {}) or {}
        rom_result = ROMResult(
            min_angle=rom_data.get("min_angle"),
            max_angle=rom_data.get("max_angle"),
            rom=rom_data.get("rom")
        )

        return AnalysisResultResponse(
            raw_angle=analysis_dict.get("raw_angle"),
            valid_angle=analysis_dict.get("valid_angle"),
            smoothed_angle=analysis_dict.get("smoothed_angle"),
            state=analysis_dict.get("state", "UNKNOWN"),
            repetitions=analysis_dict.get("repetitions", 0),
            rom=rom_result
        )
