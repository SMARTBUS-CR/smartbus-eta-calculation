"""HTTP tests for ETA liveness and readiness."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


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
