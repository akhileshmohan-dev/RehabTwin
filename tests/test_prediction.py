from rehabilitation.prediction import MovementQualityPredictor


def test_prediction_returns_valid_class(trained_model_path):
    predictor = MovementQualityPredictor(trained_model_path)

    features = {
        "min_angle": 32,
        "max_angle": 168,
        "rom": 136,
        "average_angle": 102,
        "angle_variability": 11,
        "repetitions": 10,
    }

    result = predictor.predict(features)

    assert result in {"GOOD", "MODERATE", "POOR"}
