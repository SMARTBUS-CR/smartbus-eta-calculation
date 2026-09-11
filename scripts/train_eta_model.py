"""Train a reproducible synthetic baseline; run from any working directory."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


MODEL_PATH = Path(__file__).resolve().parents[1] / "app/models/eta_model.joblib"
RANDOM_STATE = 42


def generate_training_data(n_samples: int = 20000) -> tuple[np.ndarray, np.ndarray]:
    """Return columns [distance in meters, speed in km/h] and noisy ETA seconds."""
    rng = np.random.default_rng(RANDOM_STATE)
    distance = rng.uniform(0, 20000, n_samples)
    speed = rng.uniform(5, 100, n_samples)
    variation = rng.uniform(0.97, 1.03, n_samples)
    features = np.column_stack((distance, speed))
    target = distance / (speed / 3.6) * variation
    return features, target


def train_model(output_path: Path = MODEL_PATH) -> dict[str, float]:
    """Evaluate on held-out synthetic data and export the fitted estimator."""
    features, target = generate_training_data()
    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, random_state=RANDOM_STATE
    )
    model = RandomForestRegressor(
        n_estimators=40,
        max_depth=10,
        min_samples_leaf=2,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    metrics = {
        "mae_seconds": float(mean_absolute_error(y_test, predictions)),
        "r2": float(r2_score(y_test, predictions)),
        "linear_mae_seconds": float(
            mean_absolute_error(y_test, x_test[:, 0] / (x_test[:, 1] / 3.6))
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path, compress=3)
    return metrics


if __name__ == "__main__":
    for name, value in train_model().items():
        print(f"{name}: {value:.4f}")
    print(f"Model saved to {MODEL_PATH}")
