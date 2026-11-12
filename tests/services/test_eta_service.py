"""Integration tests for ETA orchestration without mocked services."""

import unittest
from datetime import datetime
from time import perf_counter

from app.services.eta_service import (
    FALLBACK_CONFIDENCE,
    ML_CONFIDENCE,
    EtaCalculationError,
    calculate_eta,
    format_eta,
)


class EtaServiceTests(unittest.TestCase):
    """Verify ML, fallback, formatting, errors, and performance."""

    def test_ml_calculation_returns_all_required_fields(self):
        result = calculate_eta(1000, 36, route_id="R-101", stop_id="S-505")

        self.assertEqual(
            set(result),
            {
                "remaining_distance_m",
                "current_speed_kmh",
                "speed_m_s",
                "eta_seconds",
                "eta_format",
                "confidence",
                "calculated_at",
                "route_id",
                "stop_id",
            },
        )
        self.assertEqual(result["speed_m_s"], 10.0)
        self.assertGreater(result["eta_seconds"], 0)
        self.assertEqual(result["confidence"], ML_CONFIDENCE)
        self.assertEqual(result["route_id"], "R-101")
        self.assertEqual(result["stop_id"], "S-505")
        self.assertTrue(result["calculated_at"].endswith("Z"))
        datetime.fromisoformat(result["calculated_at"].replace("Z", "+00:00"))

    def test_ml_range_failure_uses_the_real_fallback(self):
        result = calculate_eta(1000, 1, route_id="R-101", stop_id="S-505")

        self.assertEqual(result["speed_m_s"], 1 / 3.6)
        self.assertEqual(result["eta_seconds"], 3600)
        self.assertEqual(result["eta_format"], "60 min 0 s")
        self.assertEqual(result["confidence"], FALLBACK_CONFIDENCE)

    def test_both_real_strategies_failing_raise_a_service_error(self):
        with self.assertRaises(EtaCalculationError):
            calculate_eta(1000, 5e-324, route_id="R-101", stop_id="S-505")

    def test_zero_distance_returns_zero_with_a_valid_speed(self):
        result = calculate_eta(0, 36, route_id="R-101", stop_id="S-505")

        self.assertEqual(result["eta_seconds"], 0)
        self.assertEqual(result["eta_format"], "0 min 0 s")
        self.assertEqual(result["confidence"], ML_CONFIDENCE)

    def test_format_eta(self):
        self.assertEqual(format_eta(355), "5 min 55 s")
        self.assertEqual(format_eta(60), "1 min 0 s")
        self.assertEqual(format_eta(45), "0 min 45 s")

    def test_calculation_is_below_500_milliseconds(self):
        start = perf_counter()
        calculate_eta(1000, 36, route_id="R-101", stop_id="S-505")
        elapsed_seconds = perf_counter() - start

        self.assertLess(elapsed_seconds, 0.5)


if __name__ == "__main__":
    unittest.main()
