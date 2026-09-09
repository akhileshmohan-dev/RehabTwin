"""
tests/test_pose_validator.py

Unit tests for rehabilitation/pose_validator.py.
Validates:
- No person detected (None or empty landmarks)
- Missing required landmarks (exercise-specific)
- Low visibility / landmark confidence (< 0.5)
- Invalid angle calculation (degenerate coordinates, NaNs)
- Valid pose frame extraction and angle calculation
- Bilateral support across all 4 exercises (left and right sides)
"""
import pytest
from rehabilitation.exercises import get_exercise_definition
from rehabilitation.pose_validator import (
    validate_pose,
    PoseStatusCode,
    PoseValidationResult,
)


def _build_landmarks(vis=0.99, x_offset=0.0):
    """Build complete landmark set with customizable visibility."""
    return {
        # Left side
        "LEFT_SHOULDER": {"x": 300.0 + x_offset, "y": 200.0, "z": 0.0, "visibility": vis},
        "LEFT_ELBOW": {"x": 300.0 + x_offset, "y": 500.0, "z": 0.0, "visibility": vis},
        "LEFT_WRIST": {"x": 500.0 + x_offset, "y": 500.0, "z": 0.0, "visibility": vis},
        "LEFT_HIP": {"x": 300.0 + x_offset, "y": 800.0, "z": 0.0, "visibility": vis},
        "LEFT_KNEE": {"x": 300.0 + x_offset, "y": 1100.0, "z": 0.0, "visibility": vis},
        "LEFT_ANKLE": {"x": 300.0 + x_offset, "y": 1400.0, "z": 0.0, "visibility": vis},
        # Right side
        "RIGHT_SHOULDER": {"x": 700.0 + x_offset, "y": 200.0, "z": 0.0, "visibility": vis},
        "RIGHT_ELBOW": {"x": 700.0 + x_offset, "y": 500.0, "z": 0.0, "visibility": vis},
        "RIGHT_WRIST": {"x": 900.0 + x_offset, "y": 500.0, "z": 0.0, "visibility": vis},
        "RIGHT_HIP": {"x": 700.0 + x_offset, "y": 800.0, "z": 0.0, "visibility": vis},
        "RIGHT_KNEE": {"x": 700.0 + x_offset, "y": 1100.0, "z": 0.0, "visibility": vis},
        "RIGHT_ANKLE": {"x": 700.0 + x_offset, "y": 1400.0, "z": 0.0, "visibility": vis},
    }


def test_validate_no_person():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    res_none = validate_pose(None, ex_def)
    assert res_none.is_valid is False
    assert res_none.status == PoseStatusCode.NO_PERSON_DETECTED
    assert "No person detected" in res_none.message

    res_empty = validate_pose({}, ex_def)
    assert res_empty.is_valid is False
    assert res_empty.status == PoseStatusCode.NO_PERSON_DETECTED


def test_validate_missing_landmarks():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    landmarks = _build_landmarks()
    del landmarks["LEFT_WRIST"]

    res = validate_pose(landmarks, ex_def)
    assert res.is_valid is False
    assert res.status == PoseStatusCode.REQUIRED_LANDMARKS_MISSING
    assert "LEFT_WRIST" in res.missing_landmarks
    assert "LEFT_WRIST" not in res.low_visibility_landmarks


def test_validate_low_visibility():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    landmarks = _build_landmarks()
    landmarks["LEFT_ELBOW"]["visibility"] = 0.35  # Below 0.5 threshold

    res = validate_pose(landmarks, ex_def, min_visibility=0.5)
    assert res.is_valid is False
    assert res.status == PoseStatusCode.LOW_VISIBILITY
    assert "LEFT_ELBOW" in res.low_visibility_landmarks
    assert res.missing_landmarks == []


def test_validate_invalid_angle_degenerate():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    landmarks = _build_landmarks()
    # Degenerate: shoulder and elbow at identical location
    landmarks["LEFT_SHOULDER"]["x"] = landmarks["LEFT_ELBOW"]["x"]
    landmarks["LEFT_SHOULDER"]["y"] = landmarks["LEFT_ELBOW"]["y"]

    res = validate_pose(landmarks, ex_def)
    assert res.is_valid is False
    assert res.status == PoseStatusCode.INVALID_ANGLE
    assert "Degenerate" in res.message or "Invalid" in res.message


def test_validate_invalid_angle_nan():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    landmarks = _build_landmarks()
    landmarks["LEFT_WRIST"]["x"] = float("nan")

    res = validate_pose(landmarks, ex_def)
    assert res.is_valid is False
    assert res.status == PoseStatusCode.INVALID_ANGLE


def test_validate_valid_pose():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    landmarks = _build_landmarks()

    res = validate_pose(landmarks, ex_def)
    assert res.is_valid is True
    assert res.status == PoseStatusCode.VALID
    assert res.raw_angle is not None
    assert abs(res.raw_angle - 90.0) < 1.0


def test_bilateral_all_four_exercises():
    exercises = ["elbow_flexion", "shoulder_flexion", "shoulder_abduction", "knee_flexion"]
    for ex_id in exercises:
        # Test Left side
        left_def = get_exercise_definition(ex_id, side="left")
        left_lm = _build_landmarks()
        res_left = validate_pose(left_lm, left_def)
        assert res_left.is_valid is True, f"Failed for {ex_id} left"
        assert res_left.status == PoseStatusCode.VALID

        # Test Right side
        right_def = get_exercise_definition(ex_id, side="right")
        right_lm = _build_landmarks()
        res_right = validate_pose(right_lm, right_def)
        assert res_right.is_valid is True, f"Failed for {ex_id} right"
        assert res_right.status == PoseStatusCode.VALID

        # Test missing right landmark on right side
        p_a_right = right_def.landmarks[0]
        del right_lm[p_a_right]
        res_missing = validate_pose(right_lm, right_def)
        assert res_missing.is_valid is False
        assert res_missing.status == PoseStatusCode.REQUIRED_LANDMARKS_MISSING
        assert p_a_right in res_missing.missing_landmarks
