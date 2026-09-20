from rehabilitation.feature_extractor import extract_features
from rehabilitation.prediction import MovementQualityPredictor


class SessionAssessment:
    """
    Performs movement-quality assessment for a completed
    rehabilitation session.
    """

    def __init__(self):
        self.predictor = MovementQualityPredictor()

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

        movement_quality = self.predictor.predict(
            features
        )

        return {
            "features": features,
            "movement_quality": movement_quality,
        }