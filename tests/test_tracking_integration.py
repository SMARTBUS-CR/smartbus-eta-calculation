"""Integration tests using the actual Dashboard HTTP adapter."""

import os
import unittest
from datetime import datetime, timezone
from functools import partial
from unittest.mock import patch

import httpx2
from fastapi.testclient import TestClient

from app.main import app
from app.services.trip_context_provider import open_trip_context_provider
from tests.support.arrivals import (
    make_arrivals_payload,
    make_arrivals_plan,
    make_confirmed_arrival_payload,
)


class TrackingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_arrivals_plan()
        self.trip_id = self.plan["trip_id"]
        self.url = f"/api/v1/eta/trips/{self.trip_id}/arrivals"
        self.headers = {"Authorization": "Bearer eta-service-key"}
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        environment = patch.dict(
            os.environ,
            {
                "ETA_SERVICE_KEY": "eta-service-key",
                "TRIP_CONTEXT_BASE_URL": "https://dashboard.test",
                "TRIP_CONTEXT_TOKEN": "dashboard-service-token",
            },
            clear=True,
        )
        environment.start()
        self.addCleanup(environment.stop)
        clock = patch("app.api.v1.arrivals.datetime")
        clock.start().now.return_value = datetime(2026, 10, 21, 15, 5, tzinfo=timezone.utc)
        self.addCleanup(clock.stop)

    def dashboard_transport(self, handler):
        """Replace only the Dashboard transport, keeping the provider and parser real."""
        return patch(
            "app.api.v1.arrivals.open_trip_context_provider",
            new=partial(open_trip_context_provider, transport=httpx2.MockTransport(handler)),
        )

    def test_correlates_each_response_when_position_versions_arrive_out_of_order(self):
        dashboard_requests = []

        def handle_request(request):
            dashboard_requests.append(request)
            return httpx2.Response(200, json=self.plan)

        cases = (
            (22, "2026-10-21T15:05:00Z", 200.0, [80, 230]),
            (21, "2026-10-21T15:04:58Z", 0.0, [100, 250]),
            (22, "2026-10-21T15:05:00Z", 200.0, [80, 230]),
        )
        with self.dashboard_transport(handle_request):
            for version, observed_at, progress, expected_seconds in cases:
                with self.subTest(version=version):
                    payload = make_arrivals_payload()
                    payload.update(position_version=version, observed_at=observed_at)
                    payload["tracking"]["distance_along_route_m"] = progress
                    for target in payload["targets"]:
                        target["remaining_distance_m"] -= progress

                    response = self.client.post(self.url, json=payload, headers=self.headers)

                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.headers["content-type"], "application/vnd.api+json")
                    data = response.json()["data"]
                    attributes = data["attributes"]
                    self.assertEqual(data["id"], self.trip_id)
                    self.assertEqual(attributes["trip_id"], self.trip_id)
                    self.assertEqual(attributes["route_revision"], payload["route_revision"])
                    self.assertEqual(attributes["position_version"], version)
                    self.assertEqual(attributes["observed_at"], observed_at)
                    self.assertEqual(
                        [arrival["stop_occurrence_id"] for arrival in attributes["arrivals"]],
                        [target["stop_occurrence_id"] for target in payload["targets"]],
                    )
                    self.assertEqual(
                        [arrival["eta_seconds"] for arrival in attributes["arrivals"]],
                        expected_seconds,
                    )

            unauthorized = self.client.post(self.url, json=make_arrivals_payload())

        self.assertEqual(unauthorized.status_code, 401, unauthorized.text)
        self.assertEqual(len(dashboard_requests), len(cases))
        for request in dashboard_requests:
            self.assertEqual(request.method, "GET")
            self.assertEqual(
                str(request.url),
                f"https://dashboard.test/api/internal/v1/trips/{self.trip_id}"
                "/tracking-context?projection=eta-v1",
            )
            self.assertEqual(request.headers["authorization"], "Bearer dashboard-service-token")
            self.assertEqual(request.extensions["timeout"]["read"], 3.0)

    def test_applies_quality_rules_after_parsing_the_dashboard_plan(self):
        stationary = make_arrivals_payload()
        stationary["tracking"]["current_speed_kmh"] = 0
        stale = make_arrivals_payload()
        stale["observed_at"] = "2026-10-21T15:04:29Z"
        off_route = make_arrivals_payload()
        off_route["tracking"]["on_route"] = False
        confirmed = make_confirmed_arrival_payload()
        cases = (
            (stationary, "scheduled_reference", "no_usable_speed", None, None),
            (stale, "scheduled_reference", "stale_observation", None, None),
            (off_route, "scheduled_reference", "off_route", None, None),
            (confirmed, "arrived", "confirmed_arrival", 0, "2026-10-21T15:05:00Z"),
        )

        with self.dashboard_transport(lambda request: httpx2.Response(200, json=self.plan)):
            for payload, method, reason, seconds, arrival_at in cases:
                with self.subTest(reason=reason):
                    response = self.client.post(self.url, json=payload, headers=self.headers)

                    self.assertEqual(response.status_code, 200, response.text)
                    arrival = response.json()["data"]["attributes"]["arrivals"][0]
                    self.assertEqual(arrival["method"], method)
                    self.assertEqual(arrival["quality_reason"], reason)
                    self.assertEqual(arrival["eta_seconds"], seconds)
                    self.assertEqual(arrival["arrival_at"], arrival_at)
                    self.assertEqual(arrival["planned_arrival_at"], "2026-10-21T15:00:00Z")

    def test_reports_dashboard_failures_without_partial_arrivals(self):
        payload = make_arrivals_payload()
        cases = (
            ("not found", 404, "trip_context_not_found"),
            ("changed revision", 409, "route_revision_mismatch"),
            ("invalid plan", 502, "trip_context_invalid_response"),
            ("timeout", 503, "trip_context_unavailable"),
        )
        for outcome, status, code in cases:
            with self.subTest(outcome=outcome):
                dashboard_requests = []

                def handle_request(request):
                    dashboard_requests.append(request)
                    if outcome == "timeout":
                        raise httpx2.ReadTimeout("private upstream detail", request=request)
                    if outcome == "not found":
                        return httpx2.Response(404, text="private upstream detail")
                    if outcome == "invalid plan":
                        return httpx2.Response(200, json={"data": "private upstream detail"})
                    return httpx2.Response(200, json={**self.plan, "route_revision": "b" * 64})

                with self.dashboard_transport(handle_request):
                    response = self.client.post(self.url, json=payload, headers=self.headers)

                self.assertEqual(response.status_code, status, response.text)
                body = response.json()
                self.assertNotIn("data", body)
                self.assertEqual(body["errors"][0]["code"], code)
                self.assertNotIn("private upstream detail", response.text)
                self.assertEqual(len(dashboard_requests), 1)
