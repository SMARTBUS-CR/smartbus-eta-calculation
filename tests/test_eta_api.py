"""Tests for ETA calculation API endpoints, Pydantic schemas validation, and i18n error handling."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.eta_service import EtaCalculationError


class EtaApiTests(unittest.TestCase):
    """Integration and unit tests for the ETA endpoints and exception handlers."""

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_calculate_eta_success_default_language(self):
        payload = {"remaining_distance_m": 3200.0, "current_speed_kmh": 32.5, "route_id": "R-101", "stop_id": "S-505"}
        response = self.client.post("/api/v1/eta/calculate", json=payload)
        self.assertEqual(response.status_code, 200)

    def test_calculate_eta_success_spanish_language(self):
        payload = {"remaining_distance_m": 3200.0, "current_speed_kmh": 32.5, "route_id": "R-101", "stop_id": "S-505"}
        headers = {"Accept-Language": "es-CR,es;q=0.9"}
        response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_validation_error_negative_distance_spanish(self):
        payload = {"remaining_distance_m": -10.0, "current_speed_kmh": 32.5, "route_id": "R-101", "stop_id": "S-505"}
        headers = {"Accept-Language": "es"}
        response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["message"], "Error de validación")
        self.assertIn("remaining_distance_m", body["errors"])

    def test_validation_error_zero_speed_english(self):
        payload = {"remaining_distance_m": 100.0, "current_speed_kmh": 0.0, "route_id": "R-101", "stop_id": "S-505"}
        headers = {"Accept-Language": "en"}
        response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertIn("current_speed_kmh", body["errors"])

    def test_validation_error_missing_field_english(self):
        payload = {"current_speed_kmh": 32.5}
        headers = {"Accept-Language": "en"}
        response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 422)
        self.assertIn("remaining_distance_m", response.json()["errors"])

    def test_eta_calculation_error_503_spanish(self):
        payload = {"remaining_distance_m": 3200.0, "current_speed_kmh": 32.5, "route_id": "R-101", "stop_id": "S-505"}
        headers = {"Accept-Language": "es"}
        
        # Mock the service to raise EtaCalculationError
        with patch("app.api.v1.eta.calculate_eta_service", side_effect=EtaCalculationError("errors.unexpected")):
            response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["message"], "Error en el cálculo de ETA")
        self.assertEqual(body["errors"]["service"][0], "Ocurrió un error inesperado.")

    def test_internal_server_error_500_spanish(self):
        payload = {"remaining_distance_m": 3200.0, "current_speed_kmh": 32.5, "route_id": "R-101", "stop_id": "S-505"}
        headers = {"Accept-Language": "es"}
        
        with patch("app.api.v1.eta.uuid.uuid4", side_effect=RuntimeError("System crash")):
            response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["message"], "Error interno del servidor")

    def test_internal_server_error_500_english(self):
        payload = {"remaining_distance_m": 3200.0, "current_speed_kmh": 32.5, "route_id": "R-101", "stop_id": "S-505"}
        headers = {"Accept-Language": "en"}
        
        with patch("app.api.v1.eta.uuid.uuid4", side_effect=RuntimeError("System crash")):
            response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["message"], "Internal Server Error")

if __name__ == "__main__":
    unittest.main()