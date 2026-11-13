"""HTTP tests for ETA liveness and readiness."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

SETTINGS = {
    "TRIP_CONTEXT_BASE_URL": "https://dashboard.test",
}
JSON_API = "application/vnd.api+json"


class HealthApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_liveness_is_public_even_when_the_service_is_unconfigured(self):
        with patch.dict(os.environ, clear=True):
            response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.json(), {"status": "alive"})

    def test_readiness_reports_local_capability_without_contacting_dashboard(self):
        with (
            patch.dict(os.environ, SETTINGS, clear=True),
            patch("httpx2.HTTPTransport.handle_request") as outbound,
        ):
            response = self.client.get("/health/ready")
            outbound.assert_not_called()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(
            response.json(),
            {"status": "ready", "calculation": "available", "ml": "disabled"},
        )

    def test_invalid_readiness_configuration_returns_a_generic_503(self):
        for override in (
            {"TRIP_CONTEXT_BASE_URL": "dashboard.test"},
            {"TRIP_CONTEXT_TIMEOUT_SECONDS": "0"},
            {"ETA_MAX_ACCURACY_METERS": "-1"},
        ):
            with (
                self.subTest(override=override),
                patch.dict(os.environ, {**SETTINGS, **override}, clear=True),
            ):
                response = self.client.get(
                    "/health/ready",
                    headers={"Accept-Language": "es"},
                )

                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.headers["content-type"], JSON_API)
                error = response.json()["errors"][0]
                self.assertEqual(error["code"], "eta_not_ready")
                self.assertEqual(error["detail"], "La API de llegadas no está configurada.")
                for configured_value in SETTINGS.values():
                    self.assertNotIn(configured_value, response.text)

    def test_openapi_describes_health_response_media_types(self):
        spec = self.client.get("/openapi.json").json()
        live = spec["paths"]["/health/live"]["get"]
        ready = spec["paths"]["/health/ready"]["get"]

        self.assertEqual(live["security"], [])
        self.assertEqual(ready["security"], [])
        self.assertEqual(set(ready["responses"]["200"]["content"]), {"application/json"})
        for code in ("503",):
            with self.subTest(code=code):
                content = ready["responses"][code]["content"]
                self.assertEqual(set(content), {JSON_API})
                schema = content[JSON_API]["schema"]["$ref"].rsplit("/", 1)[-1]
                self.assertIn(schema, spec["components"]["schemas"])
