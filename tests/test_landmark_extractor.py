"""
Focused tests for pose_estimation/landmark_extractor.py.

Verifies pixel scaling, z/visibility preservation, None handling, and that
all 33 MediaPipe landmark names are emitted.
"""
from types import SimpleNamespace

import mediapipe as mp

from pose_estimation.landmark_extractor import extract_landmarks

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
EXPECTED_LANDMARK_COUNT = 33


def _make_landmark(x, y, z, visibility):
    return SimpleNamespace(x=x, y=y, z=z, visibility=visibility)


def _make_results(landmarks):
    """Wrap a list of fake landmarks the way MediaPipe exposes them."""
    if landmarks is None:
        return SimpleNamespace(pose_landmarks=None)
    return SimpleNamespace(pose_landmarks=SimpleNamespace(landmark=landmarks))


def _make_all_landmarks():
    return [
        _make_landmark(0.5, 0.5, 0.01 * i, 0.9)
        for i in range(EXPECTED_LANDMARK_COUNT)
    ]


def test_x_y_scaled_by_frame_dimensions():
    landmarks = _make_all_landmarks()
    landmarks[11] = _make_landmark(0.25, 0.5, -0.1, 0.9)

    result = extract_landmarks(_make_results(landmarks), FRAME_WIDTH, FRAME_HEIGHT)
    name = mp.solutions.pose.PoseLandmark(11).name

    assert result[name]["x"] == 0.25 * FRAME_WIDTH
    assert result[name]["y"] == 0.5 * FRAME_HEIGHT


def test_z_preserved():
    landmarks = _make_all_landmarks()
    landmarks[13] = _make_landmark(0.5, 0.5, -0.123, 0.9)

    result = extract_landmarks(_make_results(landmarks), FRAME_WIDTH, FRAME_HEIGHT)
    name = mp.solutions.pose.PoseLandmark(13).name

    assert result[name]["z"] == -0.123


def test_visibility_preserved():
    landmarks = _make_all_landmarks()
    landmarks[15] = _make_landmark(0.5, 0.5, 0.0, 0.42)

    result = extract_landmarks(_make_results(landmarks), FRAME_WIDTH, FRAME_HEIGHT)
    name = mp.solutions.pose.PoseLandmark(15).name

    assert result[name]["visibility"] == 0.42


def test_returns_none_for_missing_pose_landmarks():
    assert extract_landmarks(_make_results(None), FRAME_WIDTH, FRAME_HEIGHT) is None


def test_returns_none_for_empty_pose_landmarks():
    results = SimpleNamespace(pose_landmarks=[])
    assert extract_landmarks(results, FRAME_WIDTH, FRAME_HEIGHT) is None


def test_emits_all_33_landmark_names():
    result = extract_landmarks(
        _make_results(_make_all_landmarks()), FRAME_WIDTH, FRAME_HEIGHT
    )

    expected_names = {
        mp.solutions.pose.PoseLandmark(i).name
        for i in range(EXPECTED_LANDMARK_COUNT)
    }
    assert len(result) == EXPECTED_LANDMARK_COUNT
    assert set(result.keys()) == expected_names
