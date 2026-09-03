from sklearn.ensemble import RandomForestClassifier


FEATURE_COLUMNS = [
    "min_angle",
    "max_angle",
    "rom",
    "average_angle",
    "angle_variability",
    "repetitions",
]


class MovementQualityModel:
    """
    Random Forest model for rehabilitation movement-quality classification.

    Classes:
        GOOD
        MODERATE
        POOR
    """

    def __init__(self, random_state=42):
        self.model = RandomForestClassifier(
            n_estimators=100,
            random_state=random_state,
        )
        self.is_trained = False

    def train(self, X, y):
        """
        Train the model using feature data X and labels y.
        """
        self.model.fit(X, y)
        self.is_trained = True

    def predict(self, features):
        """
        Predict movement quality from extracted features.
        """

        if not self.is_trained:
            raise RuntimeError(
                "Model must be trained before prediction."
            )

        values = [
            features[column]
            for column in FEATURE_COLUMNS
        ]

        return self.model.predict([values])[0]