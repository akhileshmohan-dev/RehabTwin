from rehabilitation.posture_detector import detect_posture, _default_detector


def make_landmarks(hip_y, knee_y, ankle_y):
    return {
        "LEFT_SHOULDER": {"x": 0.5, "y": 0.0, "z": 0.0},
        "LEFT_HIP": {"x": 0.5, "y": hip_y, "z": 0.0},
        "LEFT_KNEE": {"x": 0.5, "y": knee_y, "z": 0.0},
        "LEFT_ANKLE": {"x": 0.5, "y": ankle_y, "z": 0.0},

        "RIGHT_SHOULDER": {"x": 0.6, "y": 0.0, "z": 0.0},
        "RIGHT_HIP": {"x": 0.6, "y": hip_y, "z": 0.0},
        "RIGHT_KNEE": {"x": 0.6, "y": knee_y, "z": 0.0},
        "RIGHT_ANKLE": {"x": 0.6, "y": ankle_y, "z": 0.0},
    }


def test_standing_posture():
    _default_detector.reset()

    landmarks = make_landmarks(
        hip_y=0.30,
        knee_y=0.60,
        ankle_y=0.90,
    )

    result = None

    for _ in range(6):
        result = detect_posture(landmarks)

    assert result == "STANDING"


def test_sitting_posture():
    _default_detector.reset()

    landmarks = make_landmarks(
        hip_y=0.50,
        knee_y=0.60,
        ankle_y=0.90,
    )

    result = None

    for _ in range(6):
        result = detect_posture(landmarks)

    assert result == "SITTING"


def test_unknown_when_landmarks_missing():
    _default_detector.reset()

    landmarks = {
        "LEFT_HIP": {"x": 0.5, "y": 0.3, "z": 0.0},
        "LEFT_KNEE": {"x": 0.5, "y": 0.6, "z": 0.0},
    }

    assert detect_posture(landmarks) == "UNKNOWN"