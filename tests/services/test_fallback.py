"""Unit tests for the deterministic fallback, independent of the API and ML."""

import unittest

from app.services.fallback import calculate_fallback_eta


class CalculateFallbackEtaTests(unittest.TestCase):
    def test_converts_kmh_to_meters_per_second(self):
        self.assertAlmostEqual(calculate_fallback_eta(1000, 36), 100.0)

    def test_preserves_fractional_seconds(self):
        self.assertAlmostEqual(calculate_fallback_eta(125, 36), 12.5)

    def test_zero_distance_returns_zero(self):
        self.assertEqual(calculate_fallback_eta(0, 36), 0.0)

    def test_rejects_negative_distance(self):
        with self.assertRaises(ValueError):
            calculate_fallback_eta(-1, 36)

    def test_rejects_zero_and_negative_speed(self):
        for speed in (0, -10):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    calculate_fallback_eta(1000, speed)

    def test_zero_distance_does_not_bypass_invalid_speed(self):
        with self.assertRaises(ValueError):
            calculate_fallback_eta(0, 0)

    def test_rejects_non_finite_inputs(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            for distance, speed in ((value, 36), (1000, value)):
                with self.subTest(distance=distance, speed=speed):
                    with self.assertRaises(ValueError):
                        calculate_fallback_eta(distance, speed)

    def test_rejects_speed_that_underflows_during_conversion(self):
        with self.assertRaises(ValueError):
            calculate_fallback_eta(1000, 5e-324)

    def test_rejects_eta_that_overflows(self):
        with self.assertRaises(ValueError):
            calculate_fallback_eta(1e308, 1)


if __name__ == "__main__":
    unittest.main()
