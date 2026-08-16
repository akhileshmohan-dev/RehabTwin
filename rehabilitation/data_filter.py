LANDMARKS_FOR_ANGLE = {
    "left_elbow": [
        "LEFT_SHOULDER",
        "LEFT_ELBOW",
        "LEFT_WRIST"
    ],
    "right_elbow": [
        "RIGHT_SHOULDER",
        "RIGHT_ELBOW",
        "RIGHT_WRIST"
    ],
    "left_shoulder": [
        "LEFT_HIP",
        "LEFT_SHOULDER",
        "LEFT_ELBOW"
    ],
    "right_shoulder": [
        "RIGHT_HIP",
        "RIGHT_SHOULDER",
        "RIGHT_ELBOW"
    ]
}


def is_valid_measurement(angle, visibility, min_visibility=0.5):
    """Check whether an angle measurement is reliable."""

    if angle is None:
        return False

    if visibility is None:
        return False

    if visibility < min_visibility:
        return False

    return True


def get_valid_angle(pose_frame, angle_name, min_visibility=0.5):
    """
    Extract an angle from a PoseFrame only when all landmarks
    required for that angle have sufficient visibility.

    Returns None if the measurement is unreliable.
    """

    if pose_frame is None:
        return None

    angles = pose_frame.get("angles")
    visibility = pose_frame.get("visibility")

    if angles is None or visibility is None:
        return None

    if angle_name not in LANDMARKS_FOR_ANGLE:
        raise ValueError(f"Unknown angle: {angle_name}")

    angle = angles.get(angle_name)

    required_landmarks = LANDMARKS_FOR_ANGLE[angle_name]

    for landmark in required_landmarks:
        landmark_visibility = visibility.get(landmark)

        if landmark_visibility is None:
            return None

        if landmark_visibility < min_visibility:
            return None

    return angle