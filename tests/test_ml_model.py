import pytest

from rehabilitation.ml_model import MovementQualityModel


def test_model_can_train_and_predict():
    X = [
        [30, 170, 140, 100, 10, 10],
        [35, 165, 130, 105, 12, 9],
        [40, 160, 120, 110, 15, 8],

        [55, 150, 95, 110, 22, 7],
        [60, 145, 85, 115, 25, 6],
        [65, 140, 75, 120, 28, 5],

        [85, 130, 45, 110, 35, 4],
        [90, 125, 35, 115, 40, 3],
        [95, 120, 25, 120, 45, 2],
    ]

    y = [
        "GOOD",
        "GOOD",
        "GOOD",
        "MODERATE",
        "MODERATE",
        "MODERATE",
        "POOR",
        "POOR",
        "POOR",
    ]

    model = MovementQualityModel()
    model.train(X, y)

    assert model.is_trained is True


def test_model_predicts_valid_class():
    X = [
        [30, 170, 140, 100, 10, 10],
        [35, 165, 130, 105, 12, 9],
        [55, 150, 95, 110, 22, 7],
        [60, 145, 85, 115, 25, 6],
        [85, 130, 45, 110, 35, 4],
        [90, 125, 35, 115, 40, 3],
    ]

    y = [
        "GOOD",
        "GOOD",
        "MODERATE",
        "MODERATE",
        "POOR",
        "POOR",
    ]

    model = MovementQualityModel()
    model.train(X, y)

    features = {
        "min_angle": 32,
        "max_angle": 168,
        "rom": 136,
        "average_angle": 102,
        "angle_variability": 11,
        "repetitions": 10,
    }

    prediction = model.predict(features)

    assert prediction in {"GOOD", "MODERATE", "POOR"}


def test_prediction_before_training_fails():
    model = MovementQualityModel()

    features = {
        "min_angle": 32,
        "max_angle": 168,
        "rom": 136,
        "average_angle": 102,
        "angle_variability": 11,
        "repetitions": 10,
    }

    with pytest.raises(RuntimeError):
        model.predict(features)