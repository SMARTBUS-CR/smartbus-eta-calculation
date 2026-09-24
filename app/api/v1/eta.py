import uuid
from fastapi import APIRouter, status, Request
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
)
async def calculate_eta(request: Request, payload: EtaRequest) -> EtaResponse:
    """Receives flat bus telemetry data and returns JSON:API formatted ETA."""
    
    lang = request.headers.get("Accept-Language", "en")

    # Delegate calculation to the orchestration service
    result = calculate_eta_service(
        remaining_distance_m=payload.remaining_distance_m,
        current_speed_kmh=payload.current_speed_kmh,
        route_id=payload.route_id,
        stop_id=payload.stop_id,
        lang=lang
    )

    return EtaResponse(
        data=EtaDataResponse(
            id=str(uuid.uuid4()),
            attributes=EtaAttributesResponse(
                eta_seconds=result["eta_seconds"],
                eta_format=result["eta_format"],
                confidence=result["confidence"],
                calculated_at=result["calculated_at"],
            ),
        )
    )