"""HTTP contract and security tests for the arrivals batch API."""

import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.trip_context_schema import TripContext
from app.services.trip_context_provider import (
    TripContextInvalidResponse,
    TripContextNotFound,
    TripContextRevisionMismatch,
    TripContextUnavailable,
)
from tests.support.arrivals import make_arrivals_payload, make_arrivals_plan


JSON_API = "application/vnd.api+json"
TRIP_ID = UUID("11111111-1111-4111-8111-111111111111")
URL = f"/api/v1/eta/trips/{TRIP_ID}/arrivals"
AUTHORIZATION = {"Authorization": "Bearer batch-service-test"}


class BatchArrivalsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        environment = patch.dict(
            os.environ,
            {
                "ETA_SERVICE_KEY": "batch-service-test",
                "TRIP_CONTEXT_BASE_URL": "https://dashboard.test",
                "TRIP_CONTEXT_TOKEN": "dashboard-service-test",
            },
        )
        environment.start()
        self.addCleanup(environment.stop)

    @contextmanager
    def dashboard(self, plan=None):
        with (
            patch("app.api.v1.arrivals.open_trip_context_provider") as factory,
            patch("app.api.v1.arrivals.datetime") as clock,
        ):
            clock.now.return_value = datetime(2026, 10, 21, 15, 5, tzinfo=timezone.utc)
            provider = factory.return_value.__enter__.return_value
            provider.get_context.return_value = TripContext.model_validate(
                make_arrivals_plan() if plan is None else plan
            )
            yield factory, provider

    def assert_json_api_error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers["content-type"], JSON_API)
        error = response.json()["errors"][0]
        self.assertEqual(error["status"], str(status))
        self.assertEqual(error["code"], code)
        return error

    def test_returns_an_exact_nested_pointer_and_localized_detail(self):
        payload = make_arrivals_payload()
        payload["targets"][0]["remaining_distance_m"] = "1000"
        response = self.client.post(
            URL, json=payload, headers={**AUTHORIZATION, "Accept-Language": "es"}
        )

        error = self.assert_json_api_error(response, 422, "invalid_input")
        self.assertEqual(error["source"], {"pointer": "/targets/0/remaining_distance_m"})
        self.assertEqual(error["title"], "Error de validación")
        self.assertEqual(error["detail"], "El valor no cumple el contrato de llegadas.")

    def test_returns_ordered_json_api_estimates_and_preserves_the_source(self):
        payload = make_arrivals_payload()
        with self.dashboard() as (factory, provider):
            response = self.client.post(URL, json=payload, headers=AUTHORIZATION)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], JSON_API)
        data = response.json()["data"]
        self.assertEqual(data["type"], "trip-arrival-estimates")
        self.assertEqual(data["id"], str(TRIP_ID))
        attributes = data["attributes"]
        self.assertEqual(attributes["contract_version"], 1)
        self.assertEqual(attributes["trip_id"], str(TRIP_ID))
        self.assertEqual(attributes["route_revision"], payload["route_revision"])
        self.assertEqual(attributes["position_version"], payload["position_version"])
        self.assertEqual(attributes["observed_at"], payload["observed_at"])
        self.assertEqual(attributes["calculated_at"], "2026-10-21T15:05:00Z")
        self.assertEqual(
            [item["eta_seconds"] for item in attributes["arrivals"]], [100, 250]
        )
        provider.get_context.assert_called_once_with(
            TRIP_ID, expected_revision=payload["route_revision"]
        )
        self.assertEqual(factory.call_args.args[0].token, "dashboard-service-test")

    def test_rejects_missing_invalid_and_forged_credentials_before_accessing_dashboard(self):
        for headers in (
            {},
            {"Authorization": "Bearer wrong-key"},
            {"Authorization": "Basic batch-service-test"},
            {"X-User-Id": str(TRIP_ID), "X-User-Role": "admin"},
        ):
            with self.subTest(headers=headers), self.dashboard() as (factory, _):
                response = self.client.post(URL, json=make_arrivals_payload(), headers=headers)
                self.assert_json_api_error(response, 401, "unauthorized_service")
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                factory.assert_not_called()

    def test_fails_closed_when_batch_or_provider_configuration_is_missing(self):
        for setting in ("ETA_SERVICE_KEY", "TRIP_CONTEXT_TOKEN"):
            with (
                self.subTest(setting=setting),
                patch.dict(os.environ, {setting: ""}),
                self.dashboard() as (factory, _),
            ):
                response = self.client.post(URL, json=make_arrivals_payload(), headers=AUTHORIZATION)
                self.assert_json_api_error(response, 503, "eta_not_ready")
                factory.assert_not_called()

    def test_reports_path_body_and_context_validation_errors(self):
        with self.dashboard() as (factory, _):
            response = self.client.post(
                URL.replace(str(TRIP_ID), "invalid-uuid"),
                json=make_arrivals_payload(),
                headers=AUTHORIZATION,
            )
            error = self.assert_json_api_error(response, 422, "invalid_input")
            self.assertEqual(error["source"], {"parameter": "trip_id"})

            malformed = self.client.post(
                URL, content="{", headers={**AUTHORIZATION, "Content-Type": "application/json"}
            )
            error = self.assert_json_api_error(malformed, 422, "invalid_input")
            self.assertEqual(error["source"], {"pointer": ""})

            payload = make_arrivals_payload()
            payload["targets"][0]["remaining_distance_m"] = float("nan")
            nonfinite = self.client.post(
                URL,
                content=json.dumps(payload),
                headers={**AUTHORIZATION, "Content-Type": "application/json"},
            )
            error = self.assert_json_api_error(nonfinite, 422, "invalid_input")
            self.assertEqual(error["source"], {"pointer": "/targets/0/remaining_distance_m"})
            factory.assert_not_called()

            payload["targets"][0]["remaining_distance_m"] = 1002.0
            inconsistent = self.client.post(URL, json=payload, headers=AUTHORIZATION)
            error = self.assert_json_api_error(inconsistent, 422, "invalid_input")
            self.assertEqual(error["source"], {"pointer": "/targets/0/remaining_distance_m"})

    def test_maps_provider_exceptions_without_exposing_upstream_details(self):
        cases = (
            (TripContextNotFound, 404, "trip_context_not_found"),
            (TripContextRevisionMismatch, 409, "route_revision_mismatch"),
            (TripContextInvalidResponse, 502, "trip_context_invalid_response"),
            (TripContextUnavailable, 503, "trip_context_unavailable"),
        )
        for error_type, status, code in cases:
            with self.subTest(error_type=error_type), self.dashboard() as (_, provider):
                provider.get_context.side_effect = error_type("private upstream details")
                response = self.client.post(URL, json=make_arrivals_payload(), headers=AUTHORIZATION)
                self.assert_json_api_error(response, status, code)
                self.assertNotIn("private upstream details", response.text)

    def test_returns_conflict_for_terminal_trips(self):
        plan = make_arrivals_plan()
        plan["status"] = "completed"
        with self.dashboard(plan):
            response = self.client.post(URL, json=make_arrivals_payload(), headers=AUTHORIZATION)
        self.assert_json_api_error(response, 409, "trip_not_estimable")

    def test_documents_the_contract_media_types_examples_and_bearer_security(self):
        spec = self.client.get("/openapi.json").json()
        operation = spec["paths"]["/api/v1/eta/trips/{trip_id}/arrivals"]["post"]
        self.assertEqual(operation["security"], [{"EtaServiceBearer": []}])
        self.assertEqual(spec["components"]["securitySchemes"]["EtaServiceBearer"]["scheme"], "bearer")
        request = operation["requestBody"]["content"]["application/json"]
        self.assertIn("moving_bus", request["examples"])
        self.assertIn("BatchArrivalsRequest", request["schema"]["$ref"])
        for code in ("200", "401", "404", "409", "422", "500", "502", "503"):
            with self.subTest(code=code):
                content = operation["responses"][code]["content"]
                self.assertIn(JSON_API, content)
                self.assertIn("schema", content[JSON_API])
        self.assertIn("example", operation["responses"]["200"]["content"][JSON_API])
        self.assertIn("WWW-Authenticate", operation["responses"]["401"]["headers"])
        legacy = spec["paths"]["/api/v1/eta/calculate"]["post"]
        self.assertNotIn("security", legacy)
        self.assertIn("application/json", legacy["responses"]["200"]["content"])
