"""Authentication and configuration shared by arrivals and readiness."""

import os
from secrets import compare_digest
from typing import Annotated

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.arrivals_errors import ArrivalsApiError
from app.config import ArrivalQualityPolicy, TripContextSettings


service_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="EtaServiceBearer",
    description="Service credential configured as ETA_SERVICE_KEY.",
)


def authenticate_eta_service(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(service_bearer)],
) -> None:
    key = os.environ.get("ETA_SERVICE_KEY")
    if key is None or not key.strip():
        raise ArrivalsApiError(503, "eta_not_ready")
    if credentials is None or not compare_digest(credentials.credentials.encode(), key.encode()):
        raise ArrivalsApiError(401, "unauthorized_service")


def load_arrivals_settings() -> tuple[TripContextSettings, ArrivalQualityPolicy]:
    """Validate local configuration before opening the Dashboard connection."""
    try:
        return TripContextSettings.from_environment(), ArrivalQualityPolicy.from_environment()
    except ValueError as error:
        raise ArrivalsApiError(503, "eta_not_ready") from error
