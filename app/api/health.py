"""Health endpoints for the ETA service."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.arrivals_dependencies import load_arrivals_settings
from app.api.arrivals_errors import ArrivalErrors, JsonApiResponse

router = APIRouter(prefix="/health", tags=["Health"])


class LivenessResponse(BaseModel):
    status: Literal["alive"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    calculation: Literal["available"]
    ml: Literal["disabled"]


# The arrivals API registers this shared error model in OpenAPI.
_ERROR_CONTENT = {
    JsonApiResponse.media_type: {
        "schema": {"$ref": f"#/components/schemas/{ArrivalErrors.__name__}"}
    }
}


@router.get("/live", summary="Check ETA process liveness")
async def liveness() -> LivenessResponse:
    """Report that the HTTP process is responding."""
    return LivenessResponse(status="alive")


@router.get(
    "/ready",
    summary="Check local ETA calculation readiness",
    responses={
        503: {"description": "Invalid ETA service configuration.", "content": _ERROR_CONTENT},
    },
)
async def readiness() -> ReadinessResponse:
    """Check local batch settings without requesting a Dashboard plan."""
    load_arrivals_settings()
    return ReadinessResponse(status="ready", calculation="available", ml="disabled")
