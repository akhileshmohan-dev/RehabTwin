"""
Tests for bilateral exercise adaptation across all 4 core rehabilitation exercises:
1. Elbow Flexion
2. Shoulder Flexion
3. Shoulder Abduction
4. Knee Flexion
"""
import pytest
from rehabilitation.exercises import (
    get_exercise_definition,
    get_exercise,
    EXERCISE_REGISTRY,
    ExerciseDefinition,
)


CORE_EXERCISES = [
    "elbow_flexion",
    "shoulder_flexion",
    "shoulder_abduction",
    "knee_flexion",
]


@pytest.mark.parametrize("exercise_id", CORE_EXERCISES)
def test_default_left_exercise_definition(exercise_id):
    defn = get_exercise_definition(exercise_id, side="left")
    assert defn.side == "left"
    assert defn.joint_angle.startswith("left_")
    assert not defn.joint_angle.startswith("right_")
    assert len(defn.landmarks) == 3
    for lm in defn.landmarks:
        assert lm.startswith("LEFT_")
        assert not lm.startswith("RIGHT_")
        assert not lm.startswith("LEFT_LEFT_")


@pytest.mark.parametrize("exercise_id", CORE_EXERCISES)
def test_left_to_right_exercise_definition(exercise_id):
    left_defn = get_exercise_definition(exercise_id, side="left")
    right_defn = get_exercise_definition(exercise_id, side="right")

    assert right_defn.side == "right"
    # Joint angle must switch to right_ and have no left_ prefix
    assert right_defn.joint_angle.startswith("right_")
    assert not right_defn.joint_angle.startswith("left_")
    assert "left_" not in right_defn.joint_angle

    # Landmarks must all switch to RIGHT_ and have no LEFT_ prefix or duplicated prefix
    assert len(right_defn.landmarks) == 3
    for lm in right_defn.landmarks:
        assert lm.startswith("RIGHT_")
        assert not lm.startswith("LEFT_")
        assert "RIGHT_RIGHT_" not in lm

    # Check specific mapping against left landmarks
    for left_lm, right_lm in zip(left_defn.landmarks, right_defn.landmarks):
        assert right_lm == left_lm.replace("LEFT_", "RIGHT_")


@pytest.mark.parametrize("exercise_id", CORE_EXERCISES)
def test_right_to_left_round_trip(exercise_id):
    original_left = get_exercise_definition(exercise_id, side="left")
    right_defn = original_left.with_side("right")
    round_trip_left = right_defn.with_side("left")

    assert round_trip_left.side == "left"
    assert round_trip_left.joint_angle == original_left.joint_angle
    assert round_trip_left.landmarks == original_left.landmarks

    for lm in round_trip_left.landmarks:
        assert "LEFT_LEFT_" not in lm
        assert not lm.startswith("RIGHT_")


@pytest.mark.parametrize("exercise_id", CORE_EXERCISES)
def test_invalid_side_raises_value_error(exercise_id):
    defn = get_exercise_definition(exercise_id)
    with pytest.raises(ValueError, match="Invalid side"):
        defn.with_side("invalid")

    with pytest.raises(ValueError, match="Invalid side"):
        defn.with_side("both")

    with pytest.raises(ValueError, match="Invalid side"):
        defn.with_side("")

    with pytest.raises(ValueError, match="Invalid side"):
        get_exercise_definition(exercise_id, side="center")


def test_specific_joint_angle_mapping():
    # Elbow Flexion
    ef_l = get_exercise_definition("elbow_flexion", side="left")
    ef_r = get_exercise_definition("elbow_flexion", side="right")
    assert ef_l.joint_angle == "left_elbow"
    assert ef_r.joint_angle == "right_elbow"
    assert ef_r.landmarks == ("RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST")

    # Shoulder Flexion
    sf_l = get_exercise_definition("shoulder_flexion", side="left")
    sf_r = get_exercise_definition("shoulder_flexion", side="right")
    assert sf_l.joint_angle == "left_shoulder"
    assert sf_r.joint_angle == "right_shoulder"
    assert sf_r.landmarks == ("RIGHT_HIP", "RIGHT_SHOULDER", "RIGHT_ELBOW")

    # Shoulder Abduction
    sa_l = get_exercise_definition("shoulder_abduction", side="left")
    sa_r = get_exercise_definition("shoulder_abduction", side="right")
    assert sa_l.joint_angle == "left_shoulder"
    assert sa_r.joint_angle == "right_shoulder"
    assert sa_r.landmarks == ("RIGHT_HIP", "RIGHT_SHOULDER", "RIGHT_ELBOW")

    # Knee Flexion
    kf_l = get_exercise_definition("knee_flexion", side="left")
    kf_r = get_exercise_definition("knee_flexion", side="right")
    assert kf_l.joint_angle == "left_knee"
    assert kf_r.joint_angle == "right_knee"
    assert kf_r.landmarks == ("RIGHT_HIP", "RIGHT_KNEE", "RIGHT_ANKLE")


def test_legacy_dict_and_exercise_info():
    legacy_left = get_exercise("elbow_flexion", side="left")
    assert legacy_left["side"] == "left"
    assert legacy_left["joint_angle"] == "left_elbow"
    assert legacy_left["supported_sides"] == ["left", "right"]

    legacy_right = get_exercise("elbow_flexion", side="right")
    assert legacy_right["side"] == "right"
    assert legacy_right["joint_angle"] == "right_elbow"
    assert legacy_right["supported_sides"] == ["left", "right"]
