"""
rehabilitation/pose_validator.py

Pure domain validation module for pose estimation frames.
Provides deterministic validation of person detection, required landmark presence,
landmark visibility confidence, and joint angle computability.
"""
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional
import numpy as np

from pose_estimation.angle_utils import calculate_angle
from rehabilitation.exercises import ExerciseDefinition


class PoseStatusCode(str, Enum):
    """Enumeration of structured pose validation status codes."""
    VALID = "VALID"
    NO_PERSON_DETECTED = "NO_PERSON_DETECTED"
    REQUIRED_LANDMARKS_MISSING = "REQUIRED_LANDMARKS_MISSING"
    LOW_VISIBILITY = "LOW_VISIBILITY"
    INVALID_ANGLE = "INVALID_ANGLE"


@dataclass(frozen=True)
class PoseValidationResult:
    """Structured result of pose frame validation."""
    is_valid: bool
    status: PoseStatusCode
    message: str
    missing_landmarks: List[str] = field(default_factory=list)
    low_visibility_landmarks: List[str] = field(default_factory=list)
    raw_angle: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to serializable dictionary for schemas/JSON."""
        return {
            "is_valid": self.is_valid,
            "status": self.status.value,
            "message": self.message,
            "missing_landmarks": list(self.missing_landmarks),
            "low_visibility_landmarks": list(self.low_visibility_landmarks),
            "raw_angle": self.raw_angle,
        }


def validate_pose_frame(
    pose_frame: Optional[Dict[str, Any]],
    exercise_def: ExerciseDefinition,
    min_visibility: float = 0.5,
) -> PoseValidationResult:
    """
    Validate a PoseFrame dictionary against the specific exercise definition.
    Authoritative single validation logic for PoseFrame objects.

    Checks:
      1. Person Detection: pose_frame must not be None or empty.
      2. Required Landmark Presence: all 3 landmarks (point_a, vertex, point_c) must exist.
      3. Landmark Visibility: all 3 landmarks must have visibility >= min_visibility.
      4. Angle Computability: joint angle must be geometrically well-defined, finite, and [0, 180].

    Parameters
    ----------
    pose_frame : Optional[Dict[str, Any]]
        PoseFrame dictionary containing 'landmarks', 'visibility', 'angles', or pre-computed 'pose_validation'.
    exercise_def : ExerciseDefinition
        The active exercise definition specifying required landmark triplet and side.
    min_visibility : float
        Minimum landmark confidence threshold (default 0.5).

    Returns
    -------
    PoseValidationResult
        Structured validation outcome with status code, message, and diagnostic details.
    """
    # 1. Person Detection
    if not pose_frame or not isinstance(pose_frame, dict):
        return PoseValidationResult(
            is_valid=False,
            status=PoseStatusCode.NO_PERSON_DETECTED,
            message="No person detected. Please step into camera view.",
            missing_landmarks=[],
            low_visibility_landmarks=[],
            raw_angle=None,
        )

    # If already validated (e.g. by WebSocket route), reconstruct and return
    if "pose_validation" in pose_frame and isinstance(pose_frame["pose_validation"], dict):
        pv = pose_frame["pose_validation"]
        status_val = pv.get("status", "NO_PERSON_DETECTED")
        status_code = (
            PoseStatusCode(status_val)
            if status_val in PoseStatusCode._value2member_map_
            else PoseStatusCode.NO_PERSON_DETECTED
        )
        return PoseValidationResult(
            is_valid=bool(pv.get("is_valid", False)),
            status=status_code,
            message=str(pv.get("message", "")),
            missing_landmarks=list(pv.get("missing_landmarks", [])),
            low_visibility_landmarks=list(pv.get("low_visibility_landmarks", [])),
            raw_angle=pv.get("raw_angle"),
        )

    # Extract components
    landmarks_dict = pose_frame.get("landmarks")
    visibility_dict = pose_frame.get("visibility")
    angles_dict = pose_frame.get("angles")

    # If pose_frame doesn't have "landmarks" key, but has landmark keys at top-level
    if landmarks_dict is None and any(lm in pose_frame for lm in exercise_def.landmarks):
        landmarks_dict = pose_frame

    # Check for empty frame (no person detected)
    has_landmarks = bool(landmarks_dict)
    has_visibility = bool(visibility_dict)
    has_angles = bool(angles_dict)

    if not (has_landmarks or has_visibility or has_angles):
        return PoseValidationResult(
            is_valid=False,
            status=PoseStatusCode.NO_PERSON_DETECTED,
            message="No person detected. Please step into camera view.",
            missing_landmarks=[],
            low_visibility_landmarks=[],
            raw_angle=None,
        )

    p_a, p_vertex, p_c = exercise_def.landmarks

    # 2. Required landmark presence
    available_landmarks = set()
    if isinstance(landmarks_dict, dict):
        available_landmarks.update(landmarks_dict.keys())
    if isinstance(visibility_dict, dict):
        available_landmarks.update(visibility_dict.keys())

    missing = [lm for lm in (p_a, p_vertex, p_c) if lm not in available_landmarks]
    if missing:
        side_label = exercise_def.side.lower()
        readable_missing = ", ".join(m.replace("_", " ").title() for m in missing)
        return PoseValidationResult(
            is_valid=False,
            status=PoseStatusCode.REQUIRED_LANDMARKS_MISSING,
            message=(
                f"Essential {side_label} {exercise_def.name} landmarks not visible: {readable_missing}. "
                f"Please adjust your position so your {side_label} side is fully in view."
            ),
            missing_landmarks=missing,
            low_visibility_landmarks=[],
            raw_angle=None,
        )

    # 3. Landmark visibility
    low_visibility = []
    for lm in (p_a, p_vertex, p_c):
        vis = None
        if isinstance(visibility_dict, dict) and lm in visibility_dict:
            vis = visibility_dict[lm]
        elif isinstance(landmarks_dict, dict) and lm in landmarks_dict:
            lm_val = landmarks_dict[lm]
            if isinstance(lm_val, dict):
                vis = lm_val.get("visibility")

        if vis is None or vis < min_visibility:
            low_visibility.append(lm)

    if low_visibility:
        readable_low = ", ".join(m.replace("_", " ").title() for m in low_visibility)
        return PoseValidationResult(
            is_valid=False,
            status=PoseStatusCode.LOW_VISIBILITY,
            message=(
                f"Low tracking confidence for: {readable_low}. "
                f"Please ensure good lighting and clear contrast with the background."
            ),
            missing_landmarks=[],
            low_visibility_landmarks=low_visibility,
            raw_angle=None,
        )

    # 4. Angle calculation & coordinate validation
    coords_available = (
        isinstance(landmarks_dict, dict)
        and all(lm in landmarks_dict for lm in (p_a, p_vertex, p_c))
        and all(
            isinstance(landmarks_dict[lm], dict)
            and "x" in landmarks_dict[lm]
            and "y" in landmarks_dict[lm]
            for lm in (p_a, p_vertex, p_c)
        )
    )

    raw_angle = None
    if isinstance(angles_dict, dict):
        raw_angle = angles_dict.get(exercise_def.joint_angle)

    if coords_available:
        pt_a = landmarks_dict[p_a]
        pt_vertex = landmarks_dict[p_vertex]
        pt_c = landmarks_dict[p_c]

        # Check for NaN / inf / non-numeric
        for pt in (pt_a, pt_vertex, pt_c):
            try:
                x, y = float(pt["x"]), float(pt["y"])
                if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                    return PoseValidationResult(
                        is_valid=False,
                        status=PoseStatusCode.INVALID_ANGLE,
                        message="Non-finite coordinate detected in landmarks.",
                        missing_landmarks=[],
                        low_visibility_landmarks=[],
                        raw_angle=None,
                    )
            except (ValueError, TypeError):
                return PoseValidationResult(
                    is_valid=False,
                    status=PoseStatusCode.INVALID_ANGLE,
                    message="Non-numeric coordinates in landmarks.",
                    missing_landmarks=[],
                    low_visibility_landmarks=[],
                    raw_angle=None,
                )

        # Check for degenerate overlapping points
        a_vec = np.array([float(pt_a["x"]), float(pt_a["y"])])
        b_vec = np.array([float(pt_vertex["x"]), float(pt_vertex["y"])])
        c_vec = np.array([float(pt_c["x"]), float(pt_c["y"])])
        if np.linalg.norm(a_vec - b_vec) < 1e-4 or np.linalg.norm(c_vec - b_vec) < 1e-4:
            return PoseValidationResult(
                is_valid=False,
                status=PoseStatusCode.INVALID_ANGLE,
                message="Degenerate joint geometry: adjacent landmarks are too close or overlapping.",
                missing_landmarks=[],
                low_visibility_landmarks=[],
                raw_angle=None,
            )

        try:
            if raw_angle is None:
                computed = float(calculate_angle(pt_a, pt_vertex, pt_c))
            else:
                computed = float(raw_angle)

            if math.isnan(computed) or math.isinf(computed) or not (0.0 <= computed <= 180.0):
                return PoseValidationResult(
                    is_valid=False,
                    status=PoseStatusCode.INVALID_ANGLE,
                    message="Calculated joint angle out of realistic kinematic range (0-180 deg).",
                    missing_landmarks=[],
                    low_visibility_landmarks=[],
                    raw_angle=None,
                )
            raw_angle = computed
        except Exception as exc:
            return PoseValidationResult(
                is_valid=False,
                status=PoseStatusCode.INVALID_ANGLE,
                message=f"Failed to calculate joint angle: {exc}",
                missing_landmarks=[],
                low_visibility_landmarks=[],
                raw_angle=None,
            )
    else:
        # No coordinates, but angles_dict might have raw_angle
        if raw_angle is None:
            return PoseValidationResult(
                is_valid=False,
                status=PoseStatusCode.INVALID_ANGLE,
                message="Missing joint angle and landmark coordinates.",
                missing_landmarks=[],
                low_visibility_landmarks=[],
                raw_angle=None,
            )
        try:
            computed = float(raw_angle)
            if math.isnan(computed) or math.isinf(computed) or not (0.0 <= computed <= 180.0):
                return PoseValidationResult(
                    is_valid=False,
                    status=PoseStatusCode.INVALID_ANGLE,
                    message="Joint angle out of realistic kinematic range (0-180 deg).",
                    missing_landmarks=[],
                    low_visibility_landmarks=[],
                    raw_angle=None,
                )
            raw_angle = computed
        except (ValueError, TypeError):
            return PoseValidationResult(
                is_valid=False,
                status=PoseStatusCode.INVALID_ANGLE,
                message="Non-numeric joint angle.",
                missing_landmarks=[],
                low_visibility_landmarks=[],
                raw_angle=None,
            )

    # 5. Valid Pose Frame
    return PoseValidationResult(
        is_valid=True,
        status=PoseStatusCode.VALID,
        message="Pose tracking active.",
        missing_landmarks=[],
        low_visibility_landmarks=[],
        raw_angle=raw_angle,
    )


def validate_pose(
    landmarks: Optional[Dict[str, Any]],
    exercise_def: ExerciseDefinition,
    min_visibility: float = 0.5,
    calculated_angle: Optional[float] = None,
) -> PoseValidationResult:
    """
    Validate a frame's landmarks against the specific exercise definition.
    Backward-compatible adapter that delegates to validate_pose_frame.
    """
    if landmarks is None:
        return validate_pose_frame(None, exercise_def, min_visibility=min_visibility)

    # If landmarks is actually a pose_frame with 'landmarks' or 'visibility' keys
    if isinstance(landmarks, dict) and ("landmarks" in landmarks or "visibility" in landmarks or "angles" in landmarks):
        return validate_pose_frame(landmarks, exercise_def, min_visibility=min_visibility)

    frame: Dict[str, Any] = {"landmarks": landmarks}
    if calculated_angle is not None:
        frame["angles"] = {exercise_def.joint_angle: calculated_angle}

    return validate_pose_frame(frame, exercise_def, min_visibility=min_visibility)
