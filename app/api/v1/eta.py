import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, status, Request
from app.schemas.eta_schema import (
    EtaAttributesResponse,
    EtaDataResponse,
    EtaRequest,
    EtaResponse,
)

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

    # ===========================================================================================================
    # Future integration with a real ETA calculation service would go here. For now, we return hardcoded values.
    # ===========================================================================================================
    
    eta_seconds = 600
    minutes = eta_seconds // 60
    
    # Quick inline fix for formatting
    unit_label = "min" if "es" in lang.lower() else "min"
    eta_formatted = f"{minutes} {unit_label} 0 s"

    return EtaResponse(
        data=EtaDataResponse(
            id=str(uuid.uuid4()),
            attributes=EtaAttributesResponse(
                eta_seconds=eta_seconds,
                eta_formatted=eta_formatted,
                confidence=0.85,
                calculated_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
    )