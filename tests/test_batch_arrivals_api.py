"""HTTP contract and security tests for the arrivals batch API."""

import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.api.arrivals_dependencies import extract_bearer_token
from app.api.arrivals_errors import ArrivalErrors, ArrivalsApiError
from app.main import app
from app.schemas.batch_arrivals_schema import BatchArrivalsRequest, BatchArrivalsResponse
from app.schemas.trip_context_schema import TripContext
from app.services.trip_context_provider import (
    TripContextForbidden,
    TripContextInvalidResponse,
    TripContextNotFound,
    TripContextRevisionMismatch,
    TripContextUnauthorized,
    TripContextUnavailable,
)
from tests.support.arrivals import (
    make_arrivals_payload,
    make_arrivals_plan,
    make_confirmed_arrival_payload,
)

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
                "TRIP_CONTEXT_BASE_URL": "https://dashboard.test",
                "ETA_MAX_OBSERVATION_AGE_SECONDS": "30",
                "ETA_MAX_FUTURE_SKEW_SECONDS": "5",
                "ETA_MAX_ACCURACY_METERS": "100",
                "ETA_MAX_EFFECTIVE_SPEED_AGE_SECONDS": "30",
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
        self.assertEqual([item["eta_seconds"] for item in attributes["arrivals"]], [100, 250])
        provider.get_context.assert_called_once_with(
            TRIP_ID,
            expected_revision=payload["route_revision"],
            auth_token="batch-service-test",
        )
        self.assertIsNone(factory.call_args.args[0].token)

    def test_rejects_missing_or_non_bearer_credentials_before_accessing_dashboard(self):
        for headers in (
            {},
            {"Authorization": "Basic batch-service-test"},
            {"X-User-Id": str(TRIP_ID), "X-User-Role": "admin"},
        ):
            with self.subTest(headers=headers), self.dashboard() as (factory, _):
                response = self.client.post(URL, json=make_arrivals_payload(), headers=headers)
                self.assert_json_api_error(response, 401, "unauthorized_service")
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                factory.assert_not_called()

    def test_rejects_malformed_bearer_tokens_before_accessing_dashboard(self):
        with self.dashboard() as (factory, _):
            response = self.client.post(
                URL,
                json=make_arrivals_payload(),
                headers={"Authorization": "Bearer invalid token"},
            )

        self.assert_json_api_error(response, 401, "unauthorized_service")
        factory.assert_not_called()

    def test_rejects_non_ascii_bearer_tokens_before_http_header_construction(self):
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-é")

        with self.assertRaises(ArrivalsApiError) as raised:
            extract_bearer_token(credentials)

        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(raised.exception.code, "unauthorized_service")

    def test_fails_closed_when_required_provider_configuration_is_missing(self):
        for setting in ("TRIP_CONTEXT_BASE_URL",):
            with (
                self.subTest(setting=setting),
                patch.dict(os.environ, {setting: ""}),
                self.dashboard() as (factory, _),
            ):
                response = self.client.post(
                    URL, json=make_arrivals_payload(), headers=AUTHORIZATION
                )
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
            (TripContextUnauthorized, 401, "unauthorized_service"),
            (TripContextForbidden, 403, "forbidden"),
        )
        for error_type, status, code in cases:
            with self.subTest(error_type=error_type), self.dashboard() as (_, provider):
                provider.get_context.side_effect = error_type("private upstream details")
                response = self.client.post(
                    URL, json=make_arrivals_payload(), headers=AUTHORIZATION
                )
                self.assert_json_api_error(response, status, code)
                self.assertNotIn("private upstream details", response.text)

    def test_returns_conflict_for_terminal_trips(self):
        plan = make_arrivals_plan()
        plan["status"] = "completed"
        with self.dashboard(plan):
            response = self.client.post(URL, json=make_arrivals_payload(), headers=AUTHORIZATION)
        self.assert_json_api_error(response, 409, "trip_not_estimable")

    def test_returns_confirmed_and_effective_arrivals_in_the_same_batch(self):
        payload = make_confirmed_arrival_payload()
        payload["tracking"].update(
            effective_speed_kmh=18,
            effective_speed_observed_at="2026-10-21T15:04:59Z",
        )

        with self.dashboard():
            response = self.client.post(
                URL, json=payload, headers={**AUTHORIZATION, "Accept-Language": "es"}
            )

        self.assertEqual(response.status_code, 200, response.text)
        confirmed, upcoming = response.json()["data"]["attributes"]["arrivals"]
        self.assertEqual(confirmed["method"], "arrived")
        self.assertEqual(confirmed["quality_reason"], "confirmed_arrival")
        self.assertEqual(confirmed["eta_seconds"], 0)
        self.assertEqual(upcoming["method"], "distance_speed")
        self.assertEqual(upcoming["quality_reason"], "recent_effective_speed")
        self.assertEqual(upcoming["eta_seconds"], 300)

    def test_applies_configured_observation_age_and_accuracy_at_inclusive_boundaries(self):
        limits = {
            "ETA_MAX_OBSERVATION_AGE_SECONDS": "10.25",
            "ETA_MAX_ACCURACY_METERS": "12.5",
        }
        cases = (
            ("2026-10-21T15:04:49.750001Z", 12.499999, "current_speed"),
            ("2026-10-21T15:04:49.750000Z", 12.5, "current_speed"),
            ("2026-10-21T15:04:49.749999Z", 12.5, "stale_observation"),
            ("2026-10-21T15:04:49.750001Z", 12.500001, "poor_accuracy"),
        )
        with patch.dict(os.environ, limits), self.dashboard():
            for observed_at, accuracy, reason in cases:
                with self.subTest(reason=reason):
                    payload = make_arrivals_payload()
                    payload["observed_at"] = observed_at
                    payload["tracking"]["accuracy_meters"] = accuracy

                    response = self.client.post(URL, json=payload, headers=AUTHORIZATION)

                    self.assertEqual(response.status_code, 200, response.text)
                    arrival = response.json()["data"]["attributes"]["arrivals"][0]
                    self.assertEqual(arrival["quality_reason"], reason)
                    self.assertEqual(
                        arrival["eta_seconds"], 100 if reason == "current_speed" else None
                    )

    def test_applies_configured_effective_speed_age_and_future_skew(self):
        limits = {
            "ETA_MAX_EFFECTIVE_SPEED_AGE_SECONDS": "8.5",
            "ETA_MAX_FUTURE_SKEW_SECONDS": "1.25",
        }
        payload = make_arrivals_payload()
        payload["tracking"].update(current_speed_kmh=0, effective_speed_kmh=18)
        cases = (
            ("2026-10-21T15:04:51.500000Z", 200),
            ("2026-10-21T15:04:51.499999Z", None),
            ("2026-10-21T15:05:01.249999Z", 200),
            ("2026-10-21T15:05:01.250000Z", 200),
        )
        with patch.dict(os.environ, limits), self.dashboard():
            for effective_at, seconds in cases:
                with self.subTest(effective_at=effective_at):
                    payload["tracking"]["effective_speed_observed_at"] = effective_at

                    response = self.client.post(URL, json=payload, headers=AUTHORIZATION)

                    self.assertEqual(response.status_code, 200, response.text)
                    arrival = response.json()["data"]["attributes"]["arrivals"][0]
                    self.assertEqual(arrival["eta_seconds"], seconds)

            payload["tracking"]["effective_speed_observed_at"] = "2026-10-21T15:05:01.250001Z"
            response = self.client.post(URL, json=payload, headers=AUTHORIZATION)
            error = self.assert_json_api_error(response, 422, "invalid_input")
            self.assertEqual(error["source"], {"pointer": "/tracking/effective_speed_observed_at"})

    def test_rejects_invalid_quality_configuration_before_accessing_dashboard(self):
        with (
            patch.dict(os.environ, {"ETA_MAX_FUTURE_SKEW_SECONDS": "NaN"}),
            self.dashboard() as (factory, _),
        ):
            response = self.client.post(URL, json=make_arrivals_payload(), headers=AUTHORIZATION)

        self.assert_json_api_error(response, 503, "eta_not_ready")
        factory.assert_not_called()

    def test_documents_the_contract_media_types_examples_and_bearer_security(self):
        spec = self.client.get("/openapi.json").json()
        operation = spec["paths"]["/api/v1/eta/trips/{trip_id}/arrivals"]["post"]
        self.assertEqual(operation["security"], [{"http": []}])
        self.assertEqual(spec["components"]["securitySchemes"]["http"]["scheme"], "bearer")
        request = operation["requestBody"]["content"]["application/json"]
        self.assertIn("moving_bus", request["examples"])
        self.assertIn("BatchArrivalsRequest", request["schema"]["$ref"])
        for code in ("200", "401", "403", "404", "409", "422", "500", "502", "503"):
            with self.subTest(code=code):
                content = operation["responses"][code]["content"]
                self.assertIn(JSON_API, content)
                self.assertIn("schema", content[JSON_API])
        self.assertIn("example", operation["responses"]["200"]["content"][JSON_API])
        self.assertIn("WWW-Authenticate", operation["responses"]["401"]["headers"])
        arrival = spec["components"]["schemas"]["ArrivalEstimate"]["properties"]
        self.assertIn("arrived", arrival["method"]["enum"])
        self.assertIn("confirmed_arrival", arrival["quality_reason"]["enum"])
        self.assertIn("recent_effective_speed", arrival["quality_reason"]["enum"])
        legacy = spec["paths"]["/api/v1/eta/calculate"]["post"]
        self.assertEqual(legacy["security"], [])
        self.assertIn("application/json", legacy["responses"]["200"]["content"])

    def test_openapi_examples_preserve_required_nullable_fields(self):
        spec = self.client.get("/openapi.json").json()
        operation = spec["paths"]["/api/v1/eta/trips/{trip_id}/arrivals"]["post"]
        request = operation["requestBody"]["content"]["application/json"]
        responses = operation["responses"]
        BatchArrivalsRequest.model_validate(request["examples"]["moving_bus"]["value"])
        BatchArrivalsResponse.model_validate(responses["200"]["content"][JSON_API]["example"])

    def test_openapi_documents_consumer_error_codes_and_field_pointers(self):
        spec = self.client.get("/openapi.json").json()
        responses = spec["paths"]["/api/v1/eta/trips/{trip_id}/arrivals"]["post"]["responses"]
        expected_codes = {
            "401": {"unauthorized_service"},
            "403": {"forbidden"},
            "404": {"trip_context_not_found"},
            "409": {"route_revision_mismatch", "trip_not_estimable"},
            "422": {"invalid_input"},
            "500": {"internal_error"},
            "502": {"trip_context_invalid_response"},
            "503": {"eta_not_ready", "trip_context_unavailable"},
        }
        for status, codes in expected_codes.items():
            with self.subTest(status=status):
                examples = responses[status]["content"][JSON_API]["examples"]
                self.assertEqual(set(examples), codes)
                for code, example in examples.items():
                    (error,) = ArrivalErrors.model_validate(example["value"]).errors
                    self.assertEqual(error.status, status)
                    self.assertEqual(error.code, code)
                    self.assertTrue(error.title)
                    self.assertTrue(error.detail)

        invalid = responses["422"]["content"][JSON_API]["examples"]["invalid_input"]["value"]
        self.assertEqual(
            invalid["errors"][0]["source"]["pointer"], "/targets/0/remaining_distance_m"
        )
