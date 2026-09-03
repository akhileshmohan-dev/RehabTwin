import joblib
import csv
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

from rehabilitation.ml_model import MovementQualityModel, FEATURE_COLUMNS


DATASET_PATH = Path(__file__).parent / "data" / "movement_quality.csv"


def load_dataset():
    with open(DATASET_PATH, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    return rows


def prepare_data(rows):
    X = []
    y = []

    for row in rows:
        features = [
            float(row[column])
            for column in FEATURE_COLUMNS
        ]

        X.append(features)
        y.append(row["label"])

    return X, y


if __name__ == "__main__":
    rows = load_dataset()

    X, y = prepare_data(rows)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = MovementQualityModel()

    model.train(X_train, y_train)

    predictions = model.model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    print(f"Training samples: {len(X_train)}")
    print(f"Testing samples: {len(X_test)}")
    print(f"Accuracy: {accuracy:.2%}")

    print("\nClassification Report:")
    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0,
        )
    )

    # Train final model using the complete dataset
    final_model = MovementQualityModel()
    final_model.train(X, y)

    model_path = Path(__file__).parent / "movement_quality_model.joblib"

    joblib.dump(
        final_model.model,
        model_path,
    )

    print(f"\nModel saved to: {model_path}")