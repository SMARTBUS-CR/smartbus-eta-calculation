"""Health endpoints for the ETA service."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/health", tags=["Health"])


class LivenessResponse(BaseModel):
    status: Literal["alive"]


@router.get("/live", summary="Check ETA process liveness")
async def liveness() -> LivenessResponse:
    """Report that the HTTP process is responding."""
    return LivenessResponse(status="alive")
