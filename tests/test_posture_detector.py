from rehabilitation.posture_detector import PostureDetector


def make_landmarks(hip_y, knee_y, ankle_y, shoulder_y):
    def point(x, y):
        return {
            "x": x,
            "y": y,
            "z": 0.0,
            "visibility": 1.0,
        }

    return {
        "LEFT_SHOULDER": point(0.50, shoulder_y),
        "LEFT_HIP": point(0.50, hip_y),
        "LEFT_KNEE": point(0.50, knee_y),
        "LEFT_ANKLE": point(0.50, ankle_y),
        "RIGHT_SHOULDER": point(0.60, shoulder_y),
        "RIGHT_HIP": point(0.60, hip_y),
        "RIGHT_KNEE": point(0.60, knee_y),
        "RIGHT_ANKLE": point(0.60, ankle_y),
    }


def test_standing_posture():
    detector = PostureDetector()
    landmarks = make_landmarks(
        hip_y=0.30,
        knee_y=0.60,
        ankle_y=0.90,
        shoulder_y=0.00,
    )

    result = None
    for _ in range(6):
        result = detector.update(landmarks)

    assert result["posture"] == "STANDING"


def test_sitting_posture():
    detector = PostureDetector()
    landmarks = make_landmarks(
        hip_y=0.50,
        knee_y=0.60,
        ankle_y=0.90,
        shoulder_y=0.00,
    )

    result = None
    for _ in range(6):
        result = detector.update(landmarks)

    assert result["posture"] == "SITTING"


def test_unknown_when_landmarks_missing():
    detector = PostureDetector()
    landmarks = {
        "LEFT_HIP": {
            "x": 0.5,
            "y": 0.3,
            "z": 0.0,
            "visibility": 1.0,
        },
        "LEFT_KNEE": {
            "x": 0.5,
            "y": 0.6,
            "z": 0.0,
            "visibility": 1.0,
        },
    }

    result = detector.update(landmarks)

    assert result["posture"] == "UNKNOWN"
