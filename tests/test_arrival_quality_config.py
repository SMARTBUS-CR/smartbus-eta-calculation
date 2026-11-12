"""Configuration tests for the pilot arrival quality thresholds."""

import os
import unittest
from unittest.mock import patch

from app.config import ArrivalQualityPolicy


class ArrivalQualityPolicyTests(unittest.TestCase):
    def test_uses_the_pilot_defaults_when_no_limits_are_configured(self):
        with patch.dict(os.environ, clear=True):
            policy = ArrivalQualityPolicy.from_environment()

        self.assertEqual(policy, ArrivalQualityPolicy(30, 5, 100, 30))

    def test_accepts_zero_and_fractional_limits(self):
        with patch.dict(
            os.environ,
            {"ETA_MAX_FUTURE_SKEW_SECONDS": "0", "ETA_MAX_ACCURACY_METERS": "2.5"},
            clear=True,
        ):
            policy = ArrivalQualityPolicy.from_environment()

        self.assertEqual(policy.max_future_skew_seconds, 0)
        self.assertEqual(policy.max_accuracy_meters, 2.5)

    def test_rejects_nonfinite_negative_or_invalid_limits(self):
        setting = "ETA_MAX_OBSERVATION_AGE_SECONDS"
        for value in ("NaN", "inf", "-1", "invalid", ""):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {setting: value}, clear=True),
                self.assertRaisesRegex(ValueError, setting),
            ):
                ArrivalQualityPolicy.from_environment()
