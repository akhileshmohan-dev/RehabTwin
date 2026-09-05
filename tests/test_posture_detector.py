from rehabilitation.posture_detector import detect_posture


def make_landmarks(
    hip_y,
    knee_y,
    ankle_y,
):
    return {
        "LEFT_HIP": {"x": 0.5, "y": hip_y},
        "LEFT_KNEE": {"x": 0.5, "y": knee_y},
        "LEFT_ANKLE": {"x": 0.5, "y": ankle_y},

        "RIGHT_HIP": {"x": 0.6, "y": hip_y},
        "RIGHT_KNEE": {"x": 0.6, "y": knee_y},
        "RIGHT_ANKLE": {"x": 0.6, "y": ankle_y},
    }


def test_standing_posture():
    landmarks = make_landmarks(
        hip_y=0.30,
        knee_y=0.60,
        ankle_y=0.90,
    )

    assert detect_posture(landmarks) == "STANDING"


def test_sitting_posture():
    landmarks = make_landmarks(
        hip_y=0.50,
        knee_y=0.60,
        ankle_y=0.90,
    )

    assert detect_posture(landmarks) == "SITTING"


def test_unknown_when_landmarks_missing():
    landmarks = {
        "LEFT_HIP": {"x": 0.5, "y": 0.3},
        "LEFT_KNEE": {"x": 0.5, "y": 0.6},
    }

    assert detect_posture(landmarks) == "UNKNOWN"