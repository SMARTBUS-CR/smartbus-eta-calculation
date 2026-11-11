"""Internal API for correlated batch arrival estimates."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.arrivals_dependencies import authenticate_eta_service, load_arrivals_settings
from app.api.arrivals_errors import (
    ArrivalErrors,
    ArrivalsApiError,
    JsonApiResponse,
    arrival_error_example,
    json_pointer,
)
from app.schemas.batch_arrivals_schema import (
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


ERROR_RESPONSES = {
    status: {
        "model": ArrivalErrors,
        "description": description,
        "content": {
            JsonApiResponse.media_type: {
                "examples": {code: {"value": arrival_error_example(status, code)} for code in codes},
            }
        },
    }
    for status, (description, codes) in {
        401: ("Missing or invalid ETA service credential.", ("unauthorized_service",)),
        404: ("Trip context not found.", ("trip_context_not_found",)),
        409: (
            "Trip is not estimable or its route revision has changed.",
            ("route_revision_mismatch", "trip_not_estimable"),
        ),
        422: ("Invalid request or tracking progress.", ("invalid_input",)),
        500: ("Unexpected server failure.", ("internal_error",)),
        502: ("Dashboard returned an invalid response.", ("trip_context_invalid_response",)),
        503: (
            "ETA is not configured or Dashboard is unavailable.",
            ("eta_not_ready", "trip_context_unavailable"),
        ),
    }.items()
}
ERROR_RESPONSES[401]["headers"] = {
    "WWW-Authenticate": {"schema": {"type": "string"}, "example": "Bearer"}
}


@router.post(
    "/trips/{trip_id}/arrivals",
    response_model=BatchArrivalsResponse,
    response_class=JsonApiResponse,
    dependencies=[Depends(authenticate_eta_service)],
    summary="Calculate ordered arrival estimates for a Trip",
    responses=ERROR_RESPONSES,
)
def trip_arrivals(
    trip_id: UUID,
    payload: BatchArrivalsRequest,
) -> BatchArrivalsResponse:
    """Resolve one operational plan and apply the arrival quality policy.

    Usable observations may report confirmed arrivals or estimates from current
    or recent effective speed. Degraded observations return a planned reference
    when available, with null live fields.
    """
    settings, quality_policy = load_arrivals_settings()

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
            payload,
            context,
            calculated_at=datetime.now(timezone.utc),
            quality_policy=quality_policy,
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
