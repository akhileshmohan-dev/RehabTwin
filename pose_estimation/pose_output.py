"""
pose_output.py

Builds the structured PoseFrame output consumed by the Rehabilitation
Analysis module (Member 2).

This module has no dependency on any specific exercise — it just packages
whatever angles/landmarks are passed in.
"""

import time

# Landmarks the rehabilitation module needs, at minimum
REQUIRED_LANDMARKS = [
    "LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST",
    "RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST",
]


def create_pose_frame(landmarks, angles):
    """
    Build a structured PoseFrame for a single processed video frame.

    Args:
        landmarks: dict returned by extract_landmarks() (or None if no
                   pose was detected in this frame).
        angles: dict with keys like "left_elbow", "right_elbow",
                "left_shoulder", "right_shoulder" (or None if angles
                could not be calculated).

    Returns:
        A dict shaped like:
        {
            "timestamp": float,
            "angles": {...},
            "visibility": {...},
            "landmarks": {...}
        }
        or None if no pose was detected (landmarks is None) — the
        rehabilitation module should treat None as an invalid/unavailable
        frame and skip it, not fabricate values.
    """
    if landmarks is None:
        return None

    timestamp = time.perf_counter()

    visibility = {}
    landmark_coords = {}

    for name in REQUIRED_LANDMARKS:
        lm = landmarks.get(name)
        if lm is None:
            continue
        visibility[name] = lm["visibility"]
        landmark_coords[name] = {
            "x": lm["x"],
            "y": lm["y"],
            "z": lm["z"],
        }

    return {
        "timestamp": timestamp,
        "angles": angles,
        "visibility": visibility,
        "landmarks": landmark_coords,
    }