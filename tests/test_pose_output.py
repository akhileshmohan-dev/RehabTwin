"""
Focused tests for pose_estimation/pose_output.py.

Verifies None handling, REQUIRED_LANDMARKS filtering, per-landmark
x/y/z/visibility, top-level visibility consistency, round-trip re-feeding,
and that the timestamp is an absolute Unix epoch value.
"""
import time

from pose_estimation.pose_output import REQUIRED_LANDMARKS, create_pose_frame

EPOCH_FLOOR = 1_000_000_000  # anything above this is a Unix epoch, not perf_counter uptime


def _landmarks(include_extra=False):
    landmarks = {
        name: {"x": float(i), "y": float(i) + 1.0, "z": 0.1, "visibility": 0.8}
        for i, name in enumerate(REQUIRED_LANDMARKS)
    }
    if include_extra:
        landmarks["NOSE"] = {"x": 1.0, "y": 1.0, "z": 0.0, "visibility": 0.99}
    return landmarks


def test_none_landmarks_returns_none():
    assert create_pose_frame(None, {"left_elbow": 90.0}) is None


def test_only_required_landmarks_emitted():
    output = create_pose_frame(_landmarks(include_extra=True), {"left_elbow": 90.0})

    assert set(output["landmarks"].keys()) == set(REQUIRED_LANDMARKS)
    assert "NOSE" not in output["landmarks"]


def test_every_landmark_contains_xyz_and_visibility():
    output = create_pose_frame(_landmarks(), {"left_elbow": 90.0})

    for landmark in output["landmarks"].values():
        assert set(landmark.keys()) == {"x", "y", "z", "visibility"}


def test_top_level_visibility_matches_per_landmark():
    output = create_pose_frame(_landmarks(), {"left_elbow": 90.0})

    assert set(output["visibility"].keys()) == set(output["landmarks"].keys())
    for name, landmark in output["landmarks"].items():
        assert output["visibility"][name] == landmark["visibility"]


def test_angles_structure_unchanged():
    angles = {"left_elbow": 123.0}
    output = create_pose_frame(_landmarks(), angles)

    assert output["angles"] is angles


def test_output_landmarks_can_be_re_fed_without_key_error():
    output = create_pose_frame(_landmarks(), {"left_elbow": 90.0})

    again = create_pose_frame(output["landmarks"], output["angles"])

    assert again is not None
    assert again["landmarks"] == output["landmarks"]
    assert again["visibility"] == output["visibility"]


def test_timestamp_is_absolute_unix_epoch():
    before = time.time()
    output = create_pose_frame(_landmarks(), {"left_elbow": 90.0})
    after = time.time()

    assert before <= output["timestamp"] <= after
    assert output["timestamp"] > EPOCH_FLOOR
