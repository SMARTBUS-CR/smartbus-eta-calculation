"""HTTP tests for Scalar, Swagger, ReDoc and OpenAPI documentation endpoints."""

import unittest

from fastapi.testclient import TestClient

from app.main import app


class DocsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_root_redirects_to_docs_api(self):
        response = self.client.get("/", follow_redirects=False)

        self.assertIn(response.status_code, (307, 302))
        self.assertEqual(response.headers.get("location"), "/docs/api")

    def test_docs_api_serves_scalar_html_with_navigation_links(self):
        response = self.client.get("/docs/api")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("@scalar/api-reference", response.text)
        self.assertIn("/docs/api.json", response.text)
        self.assertIn('href="/docs"', response.text)
        self.assertIn('href="/redoc"', response.text)
        self.assertIn('data-configuration=\'{"theme":"purple","darkMode":true}\'', response.text)

    def test_docs_api_json_serves_valid_openapi_specification(self):
        response = self.client.get("/docs/api.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "application/json")

        spec = response.json()
        self.assertIn("openapi", spec)
        self.assertEqual(spec.get("info", {}).get("title"), "Smartbus ETA Calculation API")
        self.assertIn("/api/v1/eta/calculate", spec.get("paths", {}))
        self.assertIn("/api/v1/eta/trips/{trip_id}/arrivals", spec.get("paths", {}))
