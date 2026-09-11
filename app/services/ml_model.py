"""In-memory ETA prediction, independent of HTTP and orchestration."""

from math import isfinite
from pathlib import Path

import joblib
import numpy as np


MODEL_PATH = Path(__file__).resolve().parents[1] / "models/eta_model.joblib"


class ModelPredictionError(RuntimeError):
    """The ML model could not load or produce a usable prediction."""


class EtaModel:
    """Load a trusted local artifact once per instance, retaining load failures."""

    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self._model = None
        self._load_error = None
        try:
            self._model = joblib.load(model_path)
        except Exception as exc:
            self._load_error = exc

    def predict_eta(
        self, distancia_restante_m: float, velocidad_actual_kmh: float
    ) -> float:
        """Return seconds or signal an internal failure to the future orchestrator."""
        if self._load_error is not None:
            raise ModelPredictionError("ETA model could not be loaded") from self._load_error

        if not isfinite(distancia_restante_m) or distancia_restante_m < 0:
            raise ModelPredictionError("Distance must be finite and non-negative")
        if not isfinite(velocidad_actual_kmh) or velocidad_actual_kmh <= 0:
            raise ModelPredictionError("Speed must be finite and positive")
        # Trees do not extrapolate reliably beyond the synthetic training range.
        if distancia_restante_m > 20000 or not 5 <= velocidad_actual_kmh <= 100:
            raise ModelPredictionError("Inputs are outside the model training range")
        if distancia_restante_m == 0:
            return 0.0

        try:
            # Keep the same column order as generate_training_data.
            features = np.array([[distancia_restante_m, velocidad_actual_kmh]])
            prediction = np.asarray(self._model.predict(features))
            if prediction.shape != (1,):
                raise ValueError("Expected exactly one ETA prediction")
            eta_seconds = float(prediction[0])
            if not isfinite(eta_seconds) or eta_seconds < 0:
                raise ValueError("ETA prediction must be finite and non-negative")
        except Exception as exc:
            raise ModelPredictionError("ETA model prediction failed") from exc
        return eta_seconds


# Import once at application startup: predictions perform no disk I/O.
# Restart the process after replacing the artifact or repairing a load failure.
_default_model = EtaModel()


def predict_eta(distancia_restante_m: float, velocidad_actual_kmh: float) -> float:
    """Public entry point backed by one model instance per Python process."""
    return _default_model.predict_eta(distancia_restante_m, velocidad_actual_kmh)
