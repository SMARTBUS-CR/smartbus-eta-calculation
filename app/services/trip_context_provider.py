"""Retrieve operational Trip plans through a provider boundary."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Protocol
from uuid import UUID
from pydantic import ValidationError
from json import JSONDecodeError
from math import isfinite

import httpx2

from app.config import TripContextSettings
from app.schemas.trip_context_schema import TripContext


class TripContextInvalidResponse(RuntimeError):
    """The provider returned an invalid operational Trip context."""

class TripContextNotFound(RuntimeError):
    """The requested Trip context does not exist."""

class TripContextRevisionMismatch(RuntimeError):
    """The retrieved plan differs from the requested revision."""

class TripContextUnavailable(RuntimeError):
    """The operational Trip context provider cannot be reached."""


class TripContextProvider(Protocol):
    """Contract for retrieving a typed operational Trip plan."""

    def get_context(
        self,
        trip_id: UUID,
        *,
        expected_revision: str | None = None,
    ) -> TripContext:
        ...

class HttpTripContextProvider:
    """Retrieve Trip context from the operational Dashboard API."""

    def __init__(
        self,
        client: httpx2.Client,
        *,
        timeout_seconds: float = 3.0,
        token: str | None = None,
    ) -> None:
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError(
                "Trip context timeout must be positive and finite."
            )

        if token is not None and not token.strip():
            raise ValueError(
                "Trip context service token must not be blank."
            )

        self._client = client
        self._timeout_seconds = timeout_seconds
        self._token = token

    def get_context(
        self,
        trip_id: UUID,
        *,
        expected_revision: str | None = None,
    ) -> TripContext:
        """Retrieve the Trip context for the given Trip ID."""

        headers = {}

        if self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            response = self._client.get(
                f"/api/internal/v1/trips/{trip_id}/tracking-context",
                params={"projection": "eta-v1"},
                headers=headers,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            )
        except (httpx2.TimeoutException, httpx2.NetworkError) as exception:
            raise TripContextUnavailable(
                "The Trip context provider is temporarily unavailable."
            ) from exception

        if response.status_code == 404:
            raise TripContextNotFound(
                "The requested Trip context was not found."
            )

        try:
            response.raise_for_status()
        except httpx2.HTTPStatusError as exception:
            raise TripContextInvalidResponse(
                "The provider returned an unexpected HTTP status."
            ) from exception

        try:
            context = TripContext.model_validate(response.json())
        except (JSONDecodeError, ValidationError) as exception:
            raise TripContextInvalidResponse(
                "The provider returned an invalid Trip context."
            ) from exception

        if context.trip_id != trip_id:
            raise TripContextInvalidResponse(
                "Trip context does not match the requested Trip."
            )

        if (
            expected_revision is not None
            and context.route_revision != expected_revision
        ):
            raise TripContextRevisionMismatch(
                "Trip context does not match the requested route revision."
            )

        return context

@contextmanager
def open_trip_context_provider(
    settings: TripContextSettings,
    *,
    transport: httpx2.BaseTransport | None = None,
) -> Generator[HttpTripContextProvider, None, None]:
    """Open a configured provider and close its HTTP client on exit."""

    with httpx2.Client(
        base_url=settings.base_url,
        transport=transport,
        follow_redirects=False,
    ) as client:
        yield HttpTripContextProvider(
            client=client,
            token=settings.token,
            timeout_seconds=settings.timeout_seconds,
        )
