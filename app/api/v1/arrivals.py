"""Internal API for correlated batch arrival estimates."""

import os
from datetime import datetime, timezone
from secrets import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.arrivals_errors import ArrivalErrors, ArrivalsApiError, JsonApiResponse, json_pointer
from app.config import TripContextSettings
from app.schemas.batch_arrivals_schema import (
    ARRIVALS_REQUEST_EXAMPLE,
    ARRIVALS_RESPONSE_EXAMPLE,
    BatchArrivalsData,
    BatchArrivalsRequest,
    BatchArrivalsResponse,
)
from app.services.batch_arrivals import BatchInputError, TripNotEstimable, calculate_batch_arrivals
from app.services.trip_context_provider import (
    TripContextInvalidResponse,
    TripContextNotFound,
    TripContextRevisionMismatch,
    TripContextUnavailable,
    open_trip_context_provider,
)


router = APIRouter()
service_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="EtaServiceBearer",
    description="Service credential configured as ETA_SERVICE_KEY.",
)


def authenticate_arrivals(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(service_bearer)],
) -> None:
    key = os.environ.get("ETA_SERVICE_KEY")
    if key is None or not key.strip():
        raise ArrivalsApiError(503, "eta_not_ready")
    if credentials is None or not compare_digest(credentials.credentials.encode(), key.encode()):
        raise ArrivalsApiError(401, "unauthorized_service")


ERROR_RESPONSES = {
    code: {"model": ArrivalErrors, "description": description}
    for code, description in {
        401: "Missing or invalid ETA service credential.",
        404: "Trip context not found.",
        409: "Trip is not estimable or its route revision has changed.",
        422: "Invalid request or tracking progress.",
        500: "Unexpected server failure.",
        502: "Dashboard returned an invalid response.",
        503: "ETA is not configured or Dashboard is unavailable.",
    }.items()
}
ERROR_RESPONSES[401]["headers"] = {
    "WWW-Authenticate": {"schema": {"type": "string"}, "example": "Bearer"}
}


@router.post(
    "/trips/{trip_id}/arrivals",
    response_model=BatchArrivalsResponse,
    response_class=JsonApiResponse,
    dependencies=[Depends(authenticate_arrivals)],
    summary="Calculate ordered arrival estimates for a Trip",
    responses={
        200: {"content": {JsonApiResponse.media_type: {"example": ARRIVALS_RESPONSE_EXAMPLE}}},
        **ERROR_RESPONSES,
    },
)
def trip_arrivals(
    trip_id: UUID,
    payload: Annotated[
        BatchArrivalsRequest,
        Body(openapi_examples={"moving_bus": {"value": ARRIVALS_REQUEST_EXAMPLE}}),
    ],
) -> BatchArrivalsResponse:
    """Resolve one operational plan and calculate against a single source observation."""
    try:
        settings = TripContextSettings.from_environment()
    except ValueError as error:
        raise ArrivalsApiError(503, "eta_not_ready") from error

    try:
        with open_trip_context_provider(settings) as provider:
            context = provider.get_context(trip_id, expected_revision=payload.route_revision)
    except TripContextNotFound as error:
        raise ArrivalsApiError(404, "trip_context_not_found") from error
    except TripContextRevisionMismatch as error:
        raise ArrivalsApiError(409, "route_revision_mismatch") from error
    except TripContextInvalidResponse as error:
        raise ArrivalsApiError(502, "trip_context_invalid_response") from error
    except TripContextUnavailable as error:
        raise ArrivalsApiError(503, "trip_context_unavailable") from error

    try:
        attributes = calculate_batch_arrivals(
            payload, context, calculated_at=datetime.now(timezone.utc)
        )
    except BatchInputError as error:
        raise ArrivalsApiError(
            422, "invalid_input", detail=error.detail, pointer=json_pointer(error.path)
        ) from error
    except TripNotEstimable as error:
        raise ArrivalsApiError(409, "trip_not_estimable") from error

    return BatchArrivalsResponse(
        data=BatchArrivalsData(type="trip-arrival-estimates", id=trip_id, attributes=attributes)
    )
