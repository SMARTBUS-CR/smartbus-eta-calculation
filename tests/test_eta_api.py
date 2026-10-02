"""End-to-end tests for the ETA API without mocked application components."""

import unittest

from fastapi.testclient import TestClient

from app.main import app


class EtaApiTests(unittest.TestCase):
    """Verify API validation, ML predictions, fallback, and service errors."""

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_ml_calculation_returns_the_complete_response(self):
        payload = {
            "remaining_distance_m": 1000.0,
            "current_speed_kmh": 36.0,
            "route_id": "R-101",
            "stop_id": "S-505",
        }

        response = self.client.post("/api/v1/eta/calculate", json=payload)

        self.assertEqual(response.status_code, 200)
        attributes = response.json()["data"]["attributes"]
        self.assertEqual(response.json()["data"]["type"], "eta")
        self.assertEqual(attributes["remaining_distance_m"], 1000.0)
        self.assertEqual(attributes["current_speed_kmh"], 36.0)
        self.assertEqual(attributes["speed_m_s"], 10.0)
        self.assertGreater(attributes["eta_seconds"], 0)
        self.assertEqual(attributes["confidence"], 0.82)
        self.assertEqual(attributes["route_id"], "R-101")
        self.assertEqual(attributes["stop_id"], "S-505")
        self.assertTrue(attributes["calculated_at"].endswith("Z"))

    def test_fallback_calculation_uses_lower_confidence(self):
        payload = {
            "remaining_distance_m": 1000.0,
            "current_speed_kmh": 1.0,
            "route_id": "R-101",
            "stop_id": "S-505",
        }

        response = self.client.post("/api/v1/eta/calculate", json=payload)

        self.assertEqual(response.status_code, 200)
        attributes = response.json()["data"]["attributes"]
        self.assertEqual(attributes["eta_seconds"], 3600)
        self.assertEqual(attributes["eta_format"], "60 min 0 s")
        self.assertEqual(attributes["confidence"], 0.5)

    def test_spanish_request_keeps_the_eta_response_contract(self):
        payload = {
            "remaining_distance_m": 1000.0,
            "current_speed_kmh": 36.0,
            "route_id": "R-101",
            "stop_id": "S-505",
        }

        response = self.client.post(
            "/api/v1/eta/calculate",
            json=payload,
            headers={"Accept-Language": "es-CR,es;q=0.9"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["attributes"]["confidence"], 0.82)

    def test_negative_distance_returns_localized_422(self):
        payload = {
            "remaining_distance_m": -10.0,
            "current_speed_kmh": 32.5,
            "route_id": "R-101",
            "stop_id": "S-505",
        }

        response = self.client.post(
            "/api/v1/eta/calculate",
            json=payload,
            headers={"Accept-Language": "es"},
        )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["message"], "Error de validación")
        self.assertIn("remaining_distance_m", body["errors"])

    def test_zero_speed_returns_422(self):
        payload = {
            "remaining_distance_m": 100.0,
            "current_speed_kmh": 0.0,
            "route_id": "R-101",
            "stop_id": "S-505",
        }

        response = self.client.post("/api/v1/eta/calculate", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertIn("current_speed_kmh", response.json()["errors"])

    def test_missing_required_fields_return_422(self):
        response = self.client.post(
            "/api/v1/eta/calculate", json={"current_speed_kmh": 32.5}
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("remaining_distance_m", response.json()["errors"])
        self.assertIn("route_id", response.json()["errors"])
        self.assertIn("stop_id", response.json()["errors"])

    def test_non_finite_input_returns_422(self):
        payload = {
            "remaining_distance_m": 100.0,
            "current_speed_kmh": "Infinity",
            "route_id": "R-101",
            "stop_id": "S-505",
        }

        response = self.client.post("/api/v1/eta/calculate", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertIn("current_speed_kmh", response.json()["errors"])

    def test_real_calculation_failure_returns_503(self):
        payload = {
            "remaining_distance_m": 1000.0,
            "current_speed_kmh": 5e-324,
            "route_id": "R-101",
            "stop_id": "S-505",
        }

        response = self.client.post("/api/v1/eta/calculate", json=payload)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["message"], "ETA Calculation Error")


if __name__ == "__main__":
    unittest.main()
