"""Tests for operational Trip context configuration."""

import os
import unittest
from unittest.mock import patch

from app.config import TripContextSettings


class TripContextSettingsTests(unittest.TestCase):
    """Verify explicit environment configuration for the provider."""

    def test_loads_trip_context_settings_from_environment(self):
        environment = {
            "TRIP_CONTEXT_BASE_URL": "https://dashboard.test",
            "TRIP_CONTEXT_TOKEN": "test-service-token",
            "TRIP_CONTEXT_TIMEOUT_SECONDS": "1.5",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = TripContextSettings.from_environment()

        self.assertEqual(settings.base_url, "https://dashboard.test")
        self.assertEqual(settings.token, "test-service-token")
        self.assertEqual(settings.timeout_seconds, 1.5)

    def test_rejects_missing_or_blank_base_url(self):
        for environment in (
            {},
            {"TRIP_CONTEXT_BASE_URL": ""},
            {"TRIP_CONTEXT_BASE_URL": "   "},
        ):
            with self.subTest(environment=environment):
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(ValueError):
                        TripContextSettings.from_environment()

    def test_rejects_invalid_base_urls(self):
        for base_url in (
            "dashboard.test",
            "/api/internal",
            "https://",
            "ftp://dashboard.test",
        ):
            with self.subTest(base_url=base_url):
                environment = {
                    "TRIP_CONTEXT_BASE_URL": base_url,
                }

                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(ValueError):
                        TripContextSettings.from_environment()

    def test_rejects_invalid_timeout_values_from_environment(self):
        for timeout in ("0", "-1", "nan", "inf", "-inf", "invalid", ""):
            with self.subTest(timeout=timeout):
                environment = {
                    "TRIP_CONTEXT_BASE_URL": "https://dashboard.test",
                    "TRIP_CONTEXT_TIMEOUT_SECONDS": timeout,
                }

                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(ValueError):
                        TripContextSettings.from_environment()

    def test_rejects_blank_service_tokens_from_environment(self):
        for token in ("", "   ", "\t", "\n"):
            with self.subTest(token=repr(token)):
                environment = {
                    "TRIP_CONTEXT_BASE_URL": "https://dashboard.test",
                    "TRIP_CONTEXT_TOKEN": token,
                }

                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(ValueError):
                        TripContextSettings.from_environment()