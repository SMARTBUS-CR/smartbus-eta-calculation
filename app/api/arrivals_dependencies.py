"""Authentication and configuration shared by arrivals and readiness."""

from typing import Annotated

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.arrivals_errors import ArrivalsApiError
from app.config import ArrivalQualityPolicy, TripContextSettings

service_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="EtaServiceBearer",
    description="Sanctum Bearer token forwarded to the operational Dashboard.",
)


def _is_valid_bearer_token(token: str) -> bool:
    """Return whether a token can be safely sent as an HTTP header value."""
    return bool(token) and token.isascii() and all("!" <= character <= "~" for character in token)


def extract_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(service_bearer)],
) -> str:
    """Extract the active user's non-empty Sanctum Bearer token."""
    if credentials is None or not _is_valid_bearer_token(credentials.credentials):
        raise ArrivalsApiError(401, "unauthorized_service")
    return credentials.credentials


def load_arrivals_settings() -> tuple[TripContextSettings, ArrivalQualityPolicy]:
    """Validate local configuration before opening the Dashboard connection."""
    try:
        return TripContextSettings.from_environment(), ArrivalQualityPolicy.from_environment()
    except ValueError as error:
        raise ArrivalsApiError(503, "eta_not_ready") from error
