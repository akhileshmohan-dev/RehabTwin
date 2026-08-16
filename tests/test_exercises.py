from rehabilitation.exercises import get_exercise


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