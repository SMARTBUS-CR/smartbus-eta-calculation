"""Tests for real model persistence, predictions, and failure handling."""

import unittest
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

import joblib
import numpy as np

from app.services.ml_model import (
    MODEL_PATH,
    EtaModel,
    ModelPredictionError,
    predict_eta,
)
from scripts.train_eta_model import generate_training_data


class FailingEstimator:
    """Serializable estimator used to verify prediction error handling."""

    def predict(self, features: np.ndarray) -> list[float]:
        raise RuntimeError("prediction failed")


class FixedEstimator:
    """Serializable estimator used to verify invalid prediction handling."""

    def __init__(self, output: list[float]) -> None:
        self.output = output

    def predict(self, features: np.ndarray) -> list[float]:
        return self.output


class EtaModelTests(unittest.TestCase):
    """Verify the public ML contract with real serialized artifacts."""

    def test_exported_model_returns_positive_seconds(self):
        self.assertGreater(predict_eta(1000, 36), 0)

    def test_zero_distance_returns_zero(self):
        self.assertEqual(predict_eta(0, 36), 0.0)

    def test_loaded_model_predicts_after_its_file_is_removed(self):
        with TemporaryDirectory() as directory:
            copied_model_path = Path(directory) / "eta_model.joblib"
            copy2(MODEL_PATH, copied_model_path)
            model = EtaModel(copied_model_path)
            copied_model_path.unlink()

            self.assertGreater(model.predict_eta(1000, 36), 0)

    def test_missing_file_signals_internal_error(self):
        with TemporaryDirectory() as directory:
            model = EtaModel(Path(directory) / "missing.joblib")

            with self.assertRaises(ModelPredictionError) as error:
                model.predict_eta(1000, 36)

            self.assertIsInstance(error.exception.__cause__, FileNotFoundError)

    def test_corrupt_file_signals_internal_error(self):
        with TemporaryDirectory() as directory:
            model_path = Path(directory) / "corrupt.joblib"
            model_path.write_bytes(b"not a model")
            model = EtaModel(model_path)

            with self.assertRaises(ModelPredictionError):
                model.predict_eta(1000, 36)

    def test_prediction_exception_is_wrapped(self):
        with TemporaryDirectory() as directory:
            model_path = Path(directory) / "failing.joblib"
            joblib.dump(FailingEstimator(), model_path)
            model = EtaModel(model_path)

            with self.assertRaises(ModelPredictionError) as error:
                model.predict_eta(1000, 36)

            self.assertIsInstance(error.exception.__cause__, RuntimeError)

    def test_invalid_outputs_are_rejected(self):
        for output in ([float("nan")], [float("inf")], [-1], [], [1, 2]):
            with self.subTest(output=output):
                with TemporaryDirectory() as directory:
                    model_path = Path(directory) / "invalid-output.joblib"
                    joblib.dump(FixedEstimator(output), model_path)
                    model = EtaModel(model_path)

                    with self.assertRaises(ModelPredictionError):
                        model.predict_eta(1000, 36)

    def test_invalid_or_out_of_range_inputs_are_rejected(self):
        invalid_inputs = (
            (-1, 36),
            (1000, 0),
            (1000, -1),
            (float("nan"), 36),
            (1000, float("inf")),
            (20001, 36),
            (1000, 4),
            (1000, 101),
        )
        for distance, speed in invalid_inputs:
            with self.subTest(distance=distance, speed=speed):
                with self.assertRaises(ModelPredictionError):
                    predict_eta(distance, speed)

    def test_synthetic_data_is_reproducible_and_physically_based(self):
        features, target = generate_training_data(100)
        repeated_features, repeated_target = generate_training_data(100)

        np.testing.assert_array_equal(features, repeated_features)
        np.testing.assert_array_equal(target, repeated_target)
        ratio = target / (features[:, 0] / (features[:, 1] / 3.6))
        self.assertTrue(np.all((ratio >= 0.97) & (ratio <= 1.03)))


if __name__ == "__main__":
    unittest.main()
