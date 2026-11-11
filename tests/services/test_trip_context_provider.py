"""Tests for retrieving operational Trip context over HTTP."""

from uuid import UUID
import unittest

import httpx2

from app.config import TripContextSettings
from app.schemas.trip_context_schema import TripContext
from app.services.trip_context_provider import HttpTripContextProvider
from app.services.trip_context_provider import TripContextInvalidResponse
from app.services.trip_context_provider import TripContextNotFound
from app.services.trip_context_provider import TripContextRevisionMismatch
from app.services.trip_context_provider import TripContextUnavailable
from app.services.trip_context_provider import open_trip_context_provider
from tests.support.trip_context import make_trip_context_payload


class HttpTripContextProviderTests(unittest.TestCase):
    """Verify the operational context provider boundary."""

    def test_fetches_and_parses_the_requested_trip_context(self):
        payload = make_trip_context_payload()
        trip_id = UUID(payload["trip_id"])
        requests = []

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)
            return httpx2.Response(200, json=payload)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(client=client)

            context = provider.get_context(trip_id)

        self.assertIsInstance(context, TripContext)
        self.assertEqual(context.trip_id, trip_id)
        self.assertEqual(context.route_revision, payload["route_revision"])
        self.assertEqual(
            [item.occurrence_id for item in context.stop_occurrences],
            [
                UUID(item["occurrence_id"])
                for item in payload["stop_occurrences"]
            ],
        )
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].method, "GET")
        self.assertEqual(
            str(requests[0].url),
            f"https://dashboard.test/api/internal/v1/trips/{trip_id}/tracking-context"
            "?projection=eta-v1",
        )

    def test_rejects_context_for_a_different_trip(self):
        payload = make_trip_context_payload()
        requested_trip_id = UUID(payload["trip_id"])
        payload["trip_id"] = "99999999-9999-4999-8999-999999999999"
        requests = []

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)
            return httpx2.Response(200, json=payload)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(client=client)

            with self.assertRaises(TripContextInvalidResponse):
                provider.get_context(requested_trip_id)

        self.assertEqual(len(requests), 1)

    def test_rejects_invalid_context_from_the_provider(self):
        payload = make_trip_context_payload()
        payload["route_distance_m"] = -1.0

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, json=payload)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(client=client)

            with self.assertRaises(TripContextInvalidResponse):
                provider.get_context(UUID(payload["trip_id"]))

    def test_rejects_invalid_json_from_the_provider(self):
        trip_id = UUID("11111111-1111-4111-8111-111111111111")

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(
                200,
                text="<html>Unexpected response</html>",
                headers={"Content-Type": "text/html"},
            )

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(client=client)

            with self.assertRaises(TripContextInvalidResponse):
                provider.get_context(trip_id)

    def test_reports_when_the_requested_trip_is_not_found(self):
        trip_id = UUID("11111111-1111-4111-8111-111111111111")
        requests = []

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)
            return httpx2.Response(404, json={"message": "Not found."})

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(client=client)

            with self.assertRaises(TripContextNotFound):
                provider.get_context(trip_id)

        self.assertEqual(len(requests), 1)

    def test_rejects_unexpected_provider_http_statuses(self):
        for status_code in (301, 401, 403, 429, 500, 503):
            with self.subTest(status_code=status_code):
                trip_id = UUID("11111111-1111-4111-8111-111111111111")
                requests = []

                def handle_request(
                    request: httpx2.Request,
                ) -> httpx2.Response:
                    requests.append(request)
                    return httpx2.Response(
                        status_code,
                        text="Unexpected upstream response.",
                    )

                with httpx2.Client(
                    base_url="https://dashboard.test",
                    transport=httpx2.MockTransport(handle_request),
                    follow_redirects=False,
                ) as client:
                    provider = HttpTripContextProvider(client=client)

                    with self.assertRaises(TripContextInvalidResponse):
                        provider.get_context(trip_id)

                self.assertEqual(len(requests), 1)

    def test_reports_connection_failures_without_retrying(self):
        for error_type in (
            httpx2.ConnectError,
            httpx2.ConnectTimeout,
            httpx2.ReadTimeout,
        ):
            with self.subTest(error_type=error_type.__name__):
                trip_id = UUID("11111111-1111-4111-8111-111111111111")
                requests = []

                def handle_request(
                    request: httpx2.Request,
                ) -> httpx2.Response:
                    requests.append(request)
                    raise error_type(
                        "Upstream connection failed.",
                        request=request,
                    )

                with httpx2.Client(
                    base_url="https://dashboard.test",
                    transport=httpx2.MockTransport(handle_request),
                ) as client:
                    provider = HttpTripContextProvider(client=client)

                    with self.assertRaises(TripContextUnavailable):
                        provider.get_context(trip_id)

                self.assertEqual(len(requests), 1)

    def test_wraps_a_malformed_upstream_http_response(self):
        trip_id = UUID("11111111-1111-4111-8111-111111111111")

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            raise httpx2.RemoteProtocolError("Malformed upstream HTTP.", request=request)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(client=client)

            with self.assertRaises(TripContextInvalidResponse):
                provider.get_context(trip_id)

    def test_rejects_context_with_a_different_route_revision(self):
        payload = make_trip_context_payload()
        trip_id = UUID(payload["trip_id"])
        expected_revision = "b" * 64

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, json=payload)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(client=client)

            with self.assertRaises(TripContextRevisionMismatch):
                provider.get_context(
                    trip_id,
                    expected_revision=expected_revision,
                )

    def test_uses_a_three_second_timeout_by_default(self):
        payload = make_trip_context_payload()
        requests = []

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)
            return httpx2.Response(200, json=payload)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
            timeout=30.0,
        ) as client:
            provider = HttpTripContextProvider(client=client)

            provider.get_context(UUID(payload["trip_id"]))

        self.assertEqual(len(requests), 1)
        self.assertEqual(
            requests[0].extensions["timeout"],
            {
                "connect": 3.0,
                "read": 3.0,
                "write": 3.0,
                "pool": 3.0,
            },
        )

    def test_uses_the_configured_timeout(self):
        payload = make_trip_context_payload()
        requests = []

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)
            return httpx2.Response(200, json=payload)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(
                client=client,
                timeout_seconds=1.5,
            )

            provider.get_context(UUID(payload["trip_id"]))

        self.assertEqual(len(requests), 1)
        self.assertEqual(
            requests[0].extensions["timeout"],
            {
                "connect": 1.5,
                "read": 1.5,
                "write": 1.5,
                "pool": 1.5,
            },
        )

    def test_rejects_invalid_timeout_configuration(self):
        for timeout in (
            0.0,
            -1.0,
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(timeout=timeout):
                requests = []

                def handle_request(
                    request: httpx2.Request,
                ) -> httpx2.Response:
                    requests.append(request)
                    return httpx2.Response(200)

                with httpx2.Client(
                    base_url="https://dashboard.test",
                    transport=httpx2.MockTransport(handle_request),
                ) as client:
                    with self.assertRaises(ValueError):
                        HttpTripContextProvider(
                            client=client,
                            timeout_seconds=timeout,
                        )

                self.assertEqual(len(requests), 0)

    def test_rejects_redirects_without_following_them(self):
        payload = make_trip_context_payload()
        requests = []

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)

            if len(requests) == 1:
                return httpx2.Response(
                    302,
                    headers={
                        "Location": "https://another-service.test/context",
                    },
                )

            return httpx2.Response(200, json=payload)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
            follow_redirects=True,
        ) as client:
            provider = HttpTripContextProvider(client=client)

            with self.assertRaises(TripContextInvalidResponse):
                provider.get_context(UUID(payload["trip_id"]))

        self.assertEqual(len(requests), 1)

    def test_sends_the_configured_service_token(self):
        payload = make_trip_context_payload()
        requests = []
        token = "test-service-token"

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)
            return httpx2.Response(200, json=payload)

        with httpx2.Client(
            base_url="https://dashboard.test",
            transport=httpx2.MockTransport(handle_request),
        ) as client:
            provider = HttpTripContextProvider(
                client=client,
                token=token,
            )

            provider.get_context(UUID(payload["trip_id"]))

        self.assertEqual(len(requests), 1)
        self.assertEqual(
            requests[0].headers["Authorization"],
            f"Bearer {token}",
        )
        self.assertNotIn(token, str(requests[0].url))

    def test_rejects_blank_service_tokens(self):
        for token in ("", "   ", "\t", "\n"):
            with self.subTest(token=repr(token)):
                with httpx2.Client(
                    base_url="https://dashboard.test",
                ) as client:
                    with self.assertRaises(ValueError):
                        HttpTripContextProvider(
                            client=client,
                            token=token,
                        )

    def test_creates_a_provider_from_connection_settings(self):
        payload = make_trip_context_payload()
        requests = []

        def handle_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request)
            return httpx2.Response(200, json=payload)

        settings = TripContextSettings(
            base_url="https://dashboard.test",
            token="test-service-token",
            timeout_seconds=1.5,
        )

        with open_trip_context_provider(
            settings,
            transport=httpx2.MockTransport(handle_request),
        ) as provider:
            context = provider.get_context(
                UUID(payload["trip_id"]),
                expected_revision=payload["route_revision"],
            )

        self.assertEqual(context.trip_id, UUID(payload["trip_id"]))
        self.assertEqual(len(requests), 1)
        self.assertEqual(
            str(requests[0].url),
            f"https://dashboard.test/api/internal/v1/trips/"
            f"{payload['trip_id']}/tracking-context?projection=eta-v1",
        )
        self.assertEqual(
            requests[0].headers["Authorization"],
            "Bearer test-service-token",
        )
        self.assertEqual(
            requests[0].extensions["timeout"]["read"],
            1.5,
        )

    def test_closes_the_transport_when_context_execution_fails(self):
        class TrackingTransport(httpx2.MockTransport):
            closed = False

            def close(self) -> None:
                self.closed = True
                super().close()

        transport = TrackingTransport(
            lambda request: httpx2.Response(200)
        )
        settings = TripContextSettings(
            base_url="https://dashboard.test",
            token="test-service-token",
        )

        with self.assertRaisesRegex(RuntimeError, "Calculation failed"):
            with open_trip_context_provider(
                settings,
                transport=transport,
            ):
                raise RuntimeError("Calculation failed")

        self.assertTrue(transport.closed)
