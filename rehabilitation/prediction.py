import joblib
from pathlib import Path

from rehabilitation.ml_model import FEATURE_COLUMNS


MODEL_PATH = Path(__file__).parent / "movement_quality_model.joblib"


class MovementQualityPredictor:
    """Loads the trained model and predicts movement quality."""

    def __init__(self, model_path=MODEL_PATH):
        self.model = joblib.load(model_path)

    def predict(self, features):
        """Predict GOOD, MODERATE, or POOR movement quality."""

        values = [
            features[column]
            for column in FEATURE_COLUMNS
        ]

        prediction = self.model.predict([values])[0]

        return prediction