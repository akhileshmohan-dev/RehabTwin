import joblib
import pytest

from rehabilitation.ml_model import MovementQualityModel


@pytest.fixture
def trained_model_path(tmp_path):
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

    model_path = tmp_path / "movement_quality_model.joblib"
    joblib.dump(model.model, model_path)

    return model_path
