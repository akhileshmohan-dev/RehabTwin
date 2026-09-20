import pytest

from rehabilitation.feature_extractor import extract_features


def test_extract_features_basic():
    angles = [170, 150, 120, 90, 110, 140, 170]

    features = extract_features(
        exercise="elbow_flexion",
        angle_history=angles,
        repetitions=3,
    )

    assert features["exercise"] == "elbow_flexion"
    assert features["min_angle"] == 90
    assert features["max_angle"] == 170
    assert features["rom"] == 80
    assert features["repetitions"] == 3
    assert features["average_angle"] == pytest.approx(135.71, abs=0.01)


def test_extract_features_angle_variability():
    angles = [90, 100, 110, 100, 90]

    features = extract_features(
        exercise="shoulder_flexion",
        angle_history=angles,
        repetitions=2,
    )

    assert features["angle_variability"] == pytest.approx(8.37, abs=0.01)

def test_extract_features_empty_history():
    features = extract_features(
        exercise="knee_flexion",
        angle_history=[],
        repetitions=0,
    )

    assert features["exercise"] == "knee_flexion"
    assert features["min_angle"] is None
    assert features["max_angle"] is None
    assert features["rom"] is None
    assert features["average_angle"] is None
    assert features["angle_variability"] is None
    assert features["repetitions"] == 0


def test_extract_features_single_value():
    features = extract_features(
        exercise="shoulder_abduction",
        angle_history=[120],
        repetitions=1,
    )

    assert features["min_angle"] == 120
    assert features["max_angle"] == 120
    assert features["rom"] == 0
    assert features["average_angle"] == 120
    assert features["angle_variability"] == 0.0