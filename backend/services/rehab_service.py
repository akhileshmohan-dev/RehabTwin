"""
Rehabilitation service consuming unified exercise catalog and analysis pipeline
from the rehabilitation module.
"""
from typing import Dict, Optional, Any

from rehabilitation.exercises import EXERCISE_REGISTRY, ExerciseDefinition, get_exercise_definition
from rehabilitation.analysis_pipeline import GenericAnalysisPipeline, ElbowAnalysisPipeline

from backend.schemas.analysis import (
    ExerciseInfo,
    ExerciseListResponse,
    ProcessFrameRequest,
    AnalysisResultResponse,
    ROMResult,
    PoseStatusInfo,
)


class RehabService:
    """
    Service adapter for rehabilitation domain operations.
    Consumes unified ExerciseDefinition registry and GenericAnalysisPipeline.
    """

    def __init__(self):
        pass

    def list_exercises(self) -> ExerciseListResponse:
        """Return catalog of available rehabilitation exercise definitions."""
        exercises_list = []
        for ex in EXERCISE_REGISTRY.values():
            exercises_list.append(
                ExerciseInfo(
                    id=ex.id,
                    name=ex.name,
                    joint_angle=ex.joint_angle,
                    movement_type=ex.movement_type,
                    description=ex.description,
                    supported_sides=["left", "right"],
                    side=ex.side,
                )
            )
        return ExerciseListResponse(
            total=len(exercises_list),
            exercises=exercises_list
        )

    def get_exercise_details(self, exercise_id: str, side: str = "left") -> ExerciseInfo:
        """Retrieve details for a specific exercise ID and side."""
        try:
            ex = get_exercise_definition(exercise_id, side=side)
            return ExerciseInfo(
                id=ex.id,
                name=ex.name,
                joint_angle=ex.joint_angle,
                movement_type=ex.movement_type,
                description=ex.description,
                supported_sides=["left", "right"],
                side=ex.side,
            )
        except KeyError as exc:
            raise KeyError(str(exc))

    def process_pose_frame(self, request: ProcessFrameRequest) -> AnalysisResultResponse:
        """
        Process a single PoseFrame through GenericAnalysisPipeline.
        Pure analysis responsibility — does NOT perform database persistence.
        """
        exercise_id = request.exercise_id
        if exercise_id is None or exercise_id == "":
            exercise_id = "elbow_flexion"

        side = (request.side or "left").strip().lower()
        base_def = get_exercise_definition(exercise_id, side=side)

        # Adapt thresholds/window if request specified custom values different from base
        if (
            request.smoothing_window != base_def.smoothing_window
            or request.flexed_threshold != base_def.flexed_threshold
            or request.extended_threshold != base_def.extended_threshold
        ):
            active_def = ExerciseDefinition(
                id=base_def.id,
                name=base_def.name,
                description=base_def.description,
                target_joint=base_def.target_joint,
                joint_angle=base_def.joint_angle,
                landmarks=base_def.landmarks,
                flexed_threshold=request.flexed_threshold,
                extended_threshold=request.extended_threshold,
                target_rom=base_def.target_rom,
                movement_type=base_def.movement_type,
                smoothing_window=request.smoothing_window,
                side=base_def.side,
            )
        else:
            active_def = base_def

        pipeline = GenericAnalysisPipeline(active_def)

        analysis_dict = pipeline.process(request.pose_frame)

        rom_data = analysis_dict.get("rom", {}) or {}
        rom_result = ROMResult(
            min_angle=rom_data.get("min_angle"),
            max_angle=rom_data.get("max_angle"),
            rom=rom_data.get("rom")
        )

        pose_val = analysis_dict.get("pose_validation")
        pose_status_info = (
            PoseStatusInfo(
                is_valid=pose_val.get("is_valid", True),
                status=pose_val.get("status", "VALID"),
                message=pose_val.get("message", ""),
                missing_landmarks=pose_val.get("missing_landmarks", []),
                low_visibility_landmarks=pose_val.get("low_visibility_landmarks", []),
            )
            if pose_val
            else None
        )

        return AnalysisResultResponse(
            raw_angle=analysis_dict.get("raw_angle"),
            valid_angle=analysis_dict.get("valid_angle"),
            smoothed_angle=analysis_dict.get("smoothed_angle"),
            state=analysis_dict.get("state", "UNKNOWN"),
            repetitions=analysis_dict.get("repetitions", 0),
            rom=rom_result,
            pose_status=pose_status_info,
        )
