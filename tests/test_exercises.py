import pytest
from rehabilitation.exercises import (
    get_exercise,
    get_exercise_definition,
    register_exercise,
    ExerciseDefinition,
    EXERCISE_REGISTRY,
)


def test_elbow_flexion_definition():
    exercise = get_exercise("elbow_flexion")

    assert exercise["name"] == "Elbow Flexion"
    assert exercise["joint_angle"] == "left_elbow"


def test_shoulder_flexion_definition():
    exercise = get_exercise("shoulder_flexion")

    assert exercise["name"] == "Shoulder Flexion"
    assert exercise["joint_angle"] == "left_shoulder"


def test_unknown_exercise():
    try:
        get_exercise("unknown")
        assert False
    except ValueError:
        assert True


def test_all_four_exercises_registered():
    expected = ["elbow_flexion", "shoulder_flexion", "shoulder_abduction", "knee_flexion"]
    for ex_id in expected:
        assert ex_id in EXERCISE_REGISTRY
        ex = get_exercise_definition(ex_id)
        assert len(ex.landmarks) == 3
        assert ex.flexed_threshold < ex.extended_threshold
        assert ex.target_rom > 0.0
        assert ex.smoothing_window > 0


def test_register_exercise_validation():
    # 1. Empty ID
    with pytest.raises(ValueError, match="Exercise ID"):
        register_exercise(ExerciseDefinition(
            id="", name="Test", description="d", target_joint="j",
            joint_angle="a", landmarks=("A", "B", "C"),
            flexed_threshold=60, extended_threshold=160, target_rom=100
        ))

    # 2. Empty Name
    with pytest.raises(ValueError, match="Exercise name"):
        register_exercise(ExerciseDefinition(
            id="test", name="  ", description="d", target_joint="j",
            joint_angle="a", landmarks=("A", "B", "C"),
            flexed_threshold=60, extended_threshold=160, target_rom=100
        ))

    # 3. Invalid landmarks length
    with pytest.raises(ValueError, match="exactly 3"):
        register_exercise(ExerciseDefinition(
            id="test", name="Test", description="d", target_joint="j",
            joint_angle="a", landmarks=("A", "B"),
            flexed_threshold=60, extended_threshold=160, target_rom=100
        ))

    # 4. Invalid thresholds (flexed >= extended)
    with pytest.raises(ValueError, match="flexed_threshold"):
        register_exercise(ExerciseDefinition(
            id="test", name="Test", description="d", target_joint="j",
            joint_angle="a", landmarks=("A", "B", "C"),
            flexed_threshold=160, extended_threshold=100, target_rom=100
        ))

    # 5. Invalid target ROM
    with pytest.raises(ValueError, match="target_rom"):
        register_exercise(ExerciseDefinition(
            id="test", name="Test", description="d", target_joint="j",
            joint_angle="a", landmarks=("A", "B", "C"),
            flexed_threshold=60, extended_threshold=160, target_rom=0.0
        ))

    # 6. Invalid smoothing window
    with pytest.raises(ValueError, match="smoothing_window"):
        register_exercise(ExerciseDefinition(
            id="test", name="Test", description="d", target_joint="j",
            joint_angle="a", landmarks=("A", "B", "C"),
            flexed_threshold=60, extended_threshold=160, target_rom=100,
            smoothing_window=0
        ))


def test_exercise_definition_with_side():
    ex = get_exercise_definition("elbow_flexion")
    right_ex = ex.with_side("right")
    assert right_ex.side == "right"
    assert right_ex.joint_angle == "right_elbow"
    assert right_ex.landmarks == ("RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST")

    with pytest.raises(ValueError, match="Invalid side"):
        ex.with_side("middle")


def test_exercise_movement_directions():
    elbow = get_exercise_definition("elbow_flexion")
    knee = get_exercise_definition("knee_flexion")
    shoulder_flex = get_exercise_definition("shoulder_flexion")
    shoulder_abd = get_exercise_definition("shoulder_abduction")

    assert elbow.movement_direction == "decreasing"
    assert knee.movement_direction == "decreasing"
    assert shoulder_flex.movement_direction == "increasing"
    assert shoulder_abd.movement_direction == "increasing"
