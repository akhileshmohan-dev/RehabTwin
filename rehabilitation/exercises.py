"""
Unified rehabilitation exercise registry and definitions.
Supports extensible exercise configurations for kinematics,
repetition counting, ROM calculation, and performance scoring.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class ExerciseDefinition:
    """Unified rehabilitation exercise definition."""
    id: str
    name: str
    description: str
    target_joint: str
    joint_angle: str
    landmarks: Tuple[str, str, str]  # (point_a, vertex, point_c)
    flexed_threshold: float
    extended_threshold: float
    target_rom: float
    movement_type: str = "flexion_extension"
    smoothing_window: int = 5
    side: str = "left"
    movement_direction: str = "decreasing"

    def with_side(self, side: str) -> "ExerciseDefinition":
        """Return a copy of this definition adapted for 'left' or 'right' side."""
        side = side.lower()
        if side not in ("left", "right"):
            raise ValueError(f"Invalid side '{side}'. Must be 'left' or 'right'.")
        old_prefix = "LEFT_" if self.side == "left" else "RIGHT_"
        new_prefix = f"{side.upper()}_"
        old_angle_prefix = "left_" if self.side == "left" else "right_"
        new_angle_prefix = f"{side}_"

        new_landmarks = tuple(
            lm.replace(old_prefix, new_prefix) for lm in self.landmarks
        )
        new_joint_angle = self.joint_angle.replace(old_angle_prefix, new_angle_prefix)

        return ExerciseDefinition(
            id=self.id,
            name=self.name,
            description=self.description,
            target_joint=self.target_joint,
            joint_angle=new_joint_angle,
            landmarks=new_landmarks,  # type: ignore
            flexed_threshold=self.flexed_threshold,
            extended_threshold=self.extended_threshold,
            target_rom=self.target_rom,
            movement_type=self.movement_type,
            smoothing_window=self.smoothing_window,
            side=side,
            movement_direction=self.movement_direction,
        )

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Backward-compatible dictionary for existing callers and REST API."""
        return {
            "name": self.name,
            "joint_angle": self.joint_angle,
            "movement_type": self.movement_type,
            "description": self.description,
            "supported_sides": ["left", "right"],
            "side": self.side,
        }


EXERCISE_REGISTRY: Dict[str, ExerciseDefinition] = {}


def register_exercise(definition: ExerciseDefinition) -> None:
    """
    Register an exercise definition with validation.
    Enforces non-empty identity, valid landmark triplets,
    positive thresholds, and valid hysteresis.
    """
    if not isinstance(definition.id, str) or not definition.id.strip():
        raise ValueError("Exercise ID must be a non-empty string.")

    if not isinstance(definition.name, str) or not definition.name.strip():
        raise ValueError("Exercise name must be a non-empty string.")

    if not isinstance(definition.joint_angle, str) or not definition.joint_angle.strip():
        raise ValueError("Joint angle must be a non-empty string.")

    if (
        not isinstance(definition.landmarks, (tuple, list))
        or len(definition.landmarks) != 3
        or not all(isinstance(lm, str) and lm.strip() for lm in definition.landmarks)
    ):
        raise ValueError("Landmarks must be a tuple/list of exactly 3 non-empty landmark names.")

    if definition.flexed_threshold >= definition.extended_threshold:
        raise ValueError(
            f"flexed_threshold ({definition.flexed_threshold}) must be strictly less than "
            f"extended_threshold ({definition.extended_threshold})."
        )

    if definition.target_rom <= 0.0:
        raise ValueError(f"target_rom must be strictly positive (got {definition.target_rom}).")

    if definition.smoothing_window <= 0:
        raise ValueError(f"smoothing_window must be strictly positive (got {definition.smoothing_window}).")

    if definition.movement_direction not in ("decreasing", "increasing"):
        raise ValueError(
            f"Invalid movement_direction '{definition.movement_direction}'. Must be 'decreasing' or 'increasing'."
        )

    EXERCISE_REGISTRY[definition.id] = definition


# Pre-register the 4 core approved exercises (all left-side default)
register_exercise(ExerciseDefinition(
    id="elbow_flexion",
    name="Elbow Flexion",
    description="Bend and straighten the elbow.",
    target_joint="elbow",
    joint_angle="left_elbow",
    landmarks=("LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST"),
    flexed_threshold=100.0,
    extended_threshold=160.0,
    target_rom=130.0,
    movement_type="flexion_extension",
    smoothing_window=5,
))

register_exercise(ExerciseDefinition(
    id="shoulder_flexion",
    name="Shoulder Flexion",
    description="Raise and lower the arm in front of the body.",
    target_joint="shoulder",
    joint_angle="left_shoulder",
    landmarks=("LEFT_HIP", "LEFT_SHOULDER", "LEFT_ELBOW"),
    flexed_threshold=60.0,
    extended_threshold=160.0,
    target_rom=160.0,
    movement_type="flexion_extension",
    smoothing_window=5,
    movement_direction="increasing",
))

register_exercise(ExerciseDefinition(
    id="shoulder_abduction",
    name="Shoulder Abduction",
    description="Raise arm laterally away from the torso.",
    target_joint="shoulder",
    joint_angle="left_shoulder",
    landmarks=("LEFT_HIP", "LEFT_SHOULDER", "LEFT_ELBOW"),
    flexed_threshold=60.0,
    extended_threshold=160.0,
    target_rom=160.0,
    movement_type="flexion_extension",
    smoothing_window=5,
    movement_direction="increasing",
))

register_exercise(ExerciseDefinition(
    id="knee_flexion",
    name="Knee Flexion",
    description="Bend and straighten the knee.",
    target_joint="knee",
    joint_angle="left_knee",
    landmarks=("LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"),
    flexed_threshold=100.0,
    extended_threshold=160.0,
    target_rom=130.0,
    movement_type="flexion_extension",
    smoothing_window=5,
))


def get_exercise_definition(exercise_id: str, side: str = "left") -> ExerciseDefinition:
    """Return the complete ExerciseDefinition for an exercise ID and side."""
    if exercise_id not in EXERCISE_REGISTRY:
        raise KeyError(f"Unknown exercise: '{exercise_id}'")
    base_def = EXERCISE_REGISTRY[exercise_id]
    side = (side or "left").strip().lower()
    if side != base_def.side:
        return base_def.with_side(side)
    return base_def


def get_exercise(exercise_id: str, side: str = "left") -> Dict[str, Any]:
    """Return the backward-compatible definition of an exercise."""
    if exercise_id not in EXERCISE_REGISTRY:
        raise ValueError(f"Unknown exercise: {exercise_id}")
    return get_exercise_definition(exercise_id, side=side).to_legacy_dict()


class _ExercisesProxy(dict):
    """Backward-compatible dict view for EXERCISES."""
    def __getitem__(self, key):
        if key not in EXERCISE_REGISTRY:
            raise KeyError(key)
        return EXERCISE_REGISTRY[key].to_legacy_dict()

    def __contains__(self, key):
        return key in EXERCISE_REGISTRY

    def items(self):
        return [(k, v.to_legacy_dict()) for k, v in EXERCISE_REGISTRY.items()]

    def keys(self):
        return EXERCISE_REGISTRY.keys()

    def values(self):
        return [v.to_legacy_dict() for v in EXERCISE_REGISTRY.values()]

    def __len__(self):
        return len(EXERCISE_REGISTRY)

    def get(self, key, default=None):
        if key in EXERCISE_REGISTRY:
            return EXERCISE_REGISTRY[key].to_legacy_dict()
        return default


EXERCISES = _ExercisesProxy()
