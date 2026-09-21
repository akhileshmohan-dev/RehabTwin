from rehabilitation.feature_extractor import extract_features
from rehabilitation.prediction import MovementQualityPredictor


class SessionAssessment:
    """
    Performs movement-quality assessment for a completed
    rehabilitation session.
    """

    def __init__(self, predictor=None, model_path=None):
        self.predictor = predictor
        self.model_path = model_path

    def assess(
        self,
        exercise,
        angle_history,
        repetitions,
    ):
        """
        Extract session features and predict movement quality.
        """

        features = extract_features(
            exercise=exercise,
            angle_history=angle_history,
            repetitions=repetitions,
        )

        required_features = [
            "min_angle",
            "max_angle",
            "rom",
            "average_angle",
            "angle_variability",
        ]

        if any(
            features[key] is None
            for key in required_features
        ):
            return {
                "features": features,
                "movement_quality": None,
            }

        if self.predictor is None:
            if self.model_path is None:
                self.predictor = MovementQualityPredictor()
            else:
                self.predictor = MovementQualityPredictor(
                    model_path=self.model_path
                )

        movement_quality = self.predictor.predict(
            features
        )

        return {
            "features": features,
            "movement_quality": movement_quality,
        }
