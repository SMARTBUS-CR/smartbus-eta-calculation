"""Tests for ETA calculation API endpoints, Pydantic schemas validation, and i18n error handling."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app


class EtaApiTests(unittest.TestCase):
    """Integration and unit tests for the ETA endpoints and exception handlers."""

    def setUp(self) -> None:
        """Initialize the FastAPI TestClient before each test."""
        self.client = TestClient(app, raise_server_exceptions=False)

    # ==========================================
    # 1. SUCCESSFUL RESPONSES (200 OK)
    # ==========================================

    def test_calculate_eta_success_default_language(self):
        """Test POST /api/v1/eta/calculate returns 200 OK with JSON:API structure in English by default."""
        payload = {
            "remaining_distance_m": 3200.0,
            "current_speed_kmh": 32.5,
            "route_id": "R-101",
            "stop_id": "S-505"
        }
        response = self.client.post("/api/v1/eta/calculate", json=payload)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("data", data)
        self.assertEqual(data["data"]["type"], "eta")
        
        attributes = data["data"]["attributes"]
        self.assertEqual(attributes["eta_seconds"], 600)
        self.assertEqual(attributes["confidence"], 0.82)
        self.assertIn("eta_format", attributes)
        self.assertIn("calculated_at", attributes)

    def test_calculate_eta_success_spanish_language(self):
        """Test POST /api/v1/eta/calculate formats text properly when Accept-Language is Spanish."""
        payload = {
            "remaining_distance_m": 3200.0,
            "current_speed_kmh": 32.5,
            "route_id": "R-101",
            "stop_id": "S-505"
        }
        headers = {"Accept-Language": "es-CR,es;q=0.9"}
        response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 200)
        attributes = response.json()["data"]["attributes"]
        self.assertEqual(attributes["eta_format"], "10 min 0 s")

    # ==========================================
    # 2. VALIDATION ERRORS (422 UNPROCESSABLE ENTITY)
    # ==========================================

    def test_validation_error_negative_distance_spanish(self):
        """Test 422 error when distance is < 0 with Spanish error translations."""
        payload = {
            "remaining_distance_m": -10.0,
            "current_speed_kmh": 32.5,
            "route_id": "R-101",
            "stop_id": "S-505"
        }
        headers = {"Accept-Language": "es"}
        response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["message"], "Error de validación")
        self.assertIn("El valor debe ser mayor o igual a 0", body["errors"]["remaining_distance_m"])

    def test_validation_error_zero_speed_english(self):
        """Test 422 error when speed is 0 with English error translations."""
        payload = {
            "remaining_distance_m": 100.0,
            "current_speed_kmh": 0.0,
            "route_id": "R-101",
            "stop_id": "S-505"
        }
        headers = {"Accept-Language": "en"}
        response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertIn("Input should be greater than 0", body["errors"]["current_speed_kmh"])

    def test_validation_error_missing_field_english(self):
        """Test 422 error when a required field is missing with English error translations."""
        payload = {
            "current_speed_kmh": 32.5
        }
        headers = {"Accept-Language": "en"}
        response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 422)
        self.assertIn("Field required", response.json()["errors"]["remaining_distance_m"])

    # ==========================================
    # 3. SERVER ERRORS (500 INTERNAL SERVER ERROR)
    # ==========================================

    def test_internal_server_error_500_spanish(self):
        """Test global 500 error handler captures unhandled exceptions and translates to Spanish."""
        payload = {
            "remaining_distance_m": 3200.0,
            "current_speed_kmh": 32.5,
            "route_id": "R-101",
            "stop_id": "S-505"
        }
        headers = {"Accept-Language": "es"}
        
        with patch("app.api.v1.eta.uuid.uuid4", side_effect=RuntimeError("Unexpected error")):
            response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["message"], "Error interno del servidor")

    def test_internal_server_error_500_english(self):
        """Test global 500 error handler translates error message to English."""
        payload = {
            "remaining_distance_m": 3200.0,
            "current_speed_kmh": 32.5,
            "route_id": "R-101",
            "stop_id": "S-505"
        }
        headers = {"Accept-Language": "en"}
        
        with patch("app.api.v1.eta.uuid.uuid4", side_effect=RuntimeError("Unexpected error")):
            response = self.client.post("/api/v1/eta/calculate", json=payload, headers=headers)
        
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["message"], "Internal Server Error")


if __name__ == "__main__":
    unittest.main()