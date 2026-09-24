from typing import Optional, Dict, Any, List
from rehabilitation.data_filter import get_valid_angle
from rehabilitation.smoothing import MovingAverageFilter
from rehabilitation.repetition_counter import RepetitionCounter
from rehabilitation.rom_calculator import calculate_rom
from rehabilitation.exercises import ExerciseDefinition, get_exercise_definition
from rehabilitation.pose_validator import validate_pose_frame, validate_pose


class GenericAnalysisPipeline:
    """
    Generic exercise analysis pipeline driven by an ExerciseDefinition.
    Consumes exercise_def as the authoritative source of truth for
    joint angle, thresholds, smoothing window, and target ROM.

    Pipeline:
        PoseFrame
            ↓
        PoseValidator (authoritative single validation behavior)
            ↓
        angle smoothing (MovingAverageFilter)
            ↓
        repetition counting (RepetitionCounter)
            ↓
        ROM tracking (calculate_rom)
    """

    def __init__(self, exercise_def: ExerciseDefinition):
        self.exercise_def = exercise_def
        self.smoother = MovingAverageFilter(
            window_size=exercise_def.smoothing_window
        )
        self.counter = RepetitionCounter(
            flexed_threshold=exercise_def.flexed_threshold,
            extended_threshold=exercise_def.extended_threshold,
            movement_direction=exercise_def.movement_direction,
        )
        self.angle_history: List[float] = []

    @property
    def angle_name(self) -> str:
        return self.exercise_def.joint_angle

    def get_current_state(self) -> Dict[str, Any]:
        """Retrieve current repetition and ROM state safely without processing a frame."""
        return {
            "raw_angle": None,
            "valid_angle": None,
            "smoothed_angle": None,
            "state": self.counter.state,
            "repetitions": self.counter.repetitions,
            "rom": calculate_rom(self.angle_history),
        }

    def process(self, pose_frame: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a single PoseFrame according to the exercise definition.
        Validation is performed authoritatively by PoseValidator.
        """
        val_result = validate_pose_frame(pose_frame, self.exercise_def)

        # INVALID FRAME SAFETY:
        # If invalid:
        # - do not update smoothing
        # - do not append to angle history
        # - do not update repetitions
        # - do not update ROM
        # - do not alter existing movement state
        # - return structured pose validation status
        if not val_result.is_valid:
            state = self.get_current_state()
            state["raw_angle"] = val_result.raw_angle
            state["valid_angle"] = None
            state["smoothed_angle"] = None
            state["pose_validation"] = val_result.to_dict()
            return state

        # VALID FRAME:
        # raw angle -> smoothing -> repetition counting -> ROM
        raw_angle = val_result.raw_angle
        valid_angle = raw_angle
        smoothed_angle = self.smoother.update(valid_angle)

        if smoothed_angle is not None:
            self.angle_history.append(smoothed_angle)

        counter_result = self.counter.update(smoothed_angle)
        rom_result = calculate_rom(self.angle_history)

        return {
            "raw_angle": raw_angle,
            "valid_angle": valid_angle,
            "smoothed_angle": smoothed_angle,
            "state": counter_result["state"],
            "repetitions": counter_result["repetitions"],
            "rom": rom_result,
            "pose_validation": val_result.to_dict(),
        }

    def process_landmarks(
        self,
        landmarks: Optional[Dict[str, Any]],
        min_visibility: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Validate raw landmarks and process through analysis pipeline only when valid.
        When invalid, existing repetition and ROM metrics are strictly preserved.
        """
        val_result = validate_pose(
            landmarks,
            self.exercise_def,
            min_visibility=min_visibility,
        )

        if not val_result.is_valid:
            state = self.get_current_state()
            state["raw_angle"] = val_result.raw_angle
            state["valid_angle"] = None
            state["smoothed_angle"] = None
            state["pose_validation"] = val_result.to_dict()
            return state

        # Create structured pose frame for valid frame
        angles = {self.exercise_def.joint_angle: val_result.raw_angle}
        from pose_estimation.pose_output import create_pose_frame
        pose_frame = create_pose_frame(landmarks, angles)
        if pose_frame is not None:
            pose_frame["pose_validation"] = val_result.to_dict()

        return self.process(pose_frame)

    def reset(self) -> None:
        """Reset smoothing, repetition, and ROM state."""
        self.smoother.reset()
        self.counter.state = "UNKNOWN"
        self.counter.repetitions = 0
        self.angle_history.clear()


class ElbowAnalysisPipeline(GenericAnalysisPipeline):
    """
    Backward-compatible subclass for elbow rehabilitation analysis.
    Defaults to the pre-registered 'elbow_flexion' ExerciseDefinition.
    """

    def __init__(
        self,
        smoothing_window: int = 5,
        flexed_threshold: float = 100.0,
        extended_threshold: float = 160.0,
    ):
        base_def = get_exercise_definition("elbow_flexion")
        if (
            smoothing_window != base_def.smoothing_window
            or flexed_threshold != base_def.flexed_threshold
            or extended_threshold != base_def.extended_threshold
        ):
            custom_def = ExerciseDefinition(
                id=base_def.id,
                name=base_def.name,
                description=base_def.description,
                target_joint=base_def.target_joint,
                joint_angle=base_def.joint_angle,
                landmarks=base_def.landmarks,
                flexed_threshold=float(flexed_threshold),
                extended_threshold=float(extended_threshold),
                target_rom=base_def.target_rom,
                movement_type=base_def.movement_type,
                smoothing_window=int(smoothing_window),
                side=base_def.side,
                movement_direction=base_def.movement_direction,
            )
            super().__init__(custom_def)
        else:
            super().__init__(base_def)
