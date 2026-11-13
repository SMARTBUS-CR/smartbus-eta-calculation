"""HTTP endpoint for ETA calculations."""

from fastapi import APIRouter, status

from app.schemas.eta_schema import (
    EtaAttributesResponse,
    EtaDataResponse,
    EtaRequest,
    EtaResponse,
)
from app.services.eta_service import calculate_eta as calculate_eta_service

router = APIRouter()


@router.post(
    "/calculate",
    response_model=EtaResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate Bus Estimated Time of Arrival (ETA)",
    openapi_extra={"security": []},
)
def calculate_eta(payload: EtaRequest) -> EtaResponse:
    """Calculate ETA and return the result in the API response contract."""
    result = calculate_eta_service(
        remaining_distance_m=payload.remaining_distance_m,
        current_speed_kmh=payload.current_speed_kmh,
        route_id=payload.route_id,
        stop_id=payload.stop_id,
    )

    return EtaResponse(
        data=EtaDataResponse(
            attributes=EtaAttributesResponse(**result),
        ),
    )
