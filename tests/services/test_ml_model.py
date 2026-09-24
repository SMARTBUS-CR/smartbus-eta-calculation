"""Tests for model persistence, feature order and internal failure handling."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import numpy as np

from app.services.ml_model import EtaModel, ModelPredictionError, predict_eta
from scripts.train_eta_model import generate_training_data


class EtaModelTests(unittest.TestCase):
    def test_exported_model_returns_positive_seconds(self):
        self.assertGreater(predict_eta(1000, 36), 0)

    def test_zero_distance_returns_zero(self):
        self.assertEqual(predict_eta(0, 36), 0.0)

    def test_loads_once_and_keeps_feature_order(self):
        estimator = Mock()
        estimator.predict.return_value = [100.0]
        with patch("app.services.ml_model.joblib.load", return_value=estimator) as loader:
            model = EtaModel()
            self.assertEqual(model.predict_eta(1000, 36), 100.0)
            model.predict_eta(500, 18)
        loader.assert_called_once()
        np.testing.assert_array_equal(estimator.predict.call_args_list[0].args[0], [[1000, 36]])
        np.testing.assert_array_equal(estimator.predict.call_args_list[1].args[0], [[500, 18]])

    def test_missing_file_signals_internal_error(self):
        with TemporaryDirectory() as directory:
            model = EtaModel(Path(directory) / "missing.joblib")
            with self.assertRaises(ModelPredictionError) as error:
                model.predict_eta(1000, 36)
            self.assertIsInstance(error.exception.__cause__, FileNotFoundError)

    def test_corrupt_file_signals_internal_error(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.joblib"
            path.write_bytes(b"not a model")
            model = EtaModel(path)
            with self.assertRaises(ModelPredictionError):
                model.predict_eta(1000, 36)

    def test_failed_load_is_not_retried_on_predictions(self):
        with patch("app.services.ml_model.joblib.load", side_effect=OSError) as loader:
            model = EtaModel()
            for _ in range(2):
                with self.assertRaises(ModelPredictionError):
                    model.predict_eta(1000, 36)
            loader.assert_called_once()

    def test_prediction_exception_is_wrapped(self):
        estimator = Mock()
        estimator.predict.side_effect = RuntimeError("prediction failed")
        with patch("app.services.ml_model.joblib.load", return_value=estimator):
            model = EtaModel()
        with self.assertRaises(ModelPredictionError) as error:
            model.predict_eta(1000, 36)
        self.assertIsInstance(error.exception.__cause__, RuntimeError)

    def test_invalid_outputs_are_rejected(self):
        estimator = Mock()
        with patch("app.services.ml_model.joblib.load", return_value=estimator):
            model = EtaModel()
        for output in ([float("nan")], [float("inf")], [-1], [], [1, 2]):
            with self.subTest(output=output):
                estimator.predict.return_value = output
                with self.assertRaises(ModelPredictionError):
                    model.predict_eta(1000, 36)

    def test_invalid_or_out_of_range_inputs_are_rejected(self):
        for distance, speed in ((-1, 36), (1000, 0), (1000, -1),
                                (float("nan"), 36), (1000, float("inf")),
                                (20001, 36), (1000, 4), (1000, 101)):
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
