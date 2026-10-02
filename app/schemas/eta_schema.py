"""Pydantic request and response contracts for the ETA endpoint."""

from pydantic import BaseModel, Field


class EtaRequest(BaseModel):
    """Validated input required to calculate a bus ETA."""

    remaining_distance_m: float = Field(
        ...,
        ge=0,
        allow_inf_nan=False,
        description="Remaining distance in meters",
        json_schema_extra={"example": 3200.0},
    )
    current_speed_kmh: float = Field(
        ...,
        gt=0,
        allow_inf_nan=False,
        description="Current speed in kilometers per hour",
        json_schema_extra={"example": 32.5},
    )
    route_id: str = Field(
        ..., description="Route identifier", json_schema_extra={"example": "R-101"}
    )
    stop_id: str = Field(
        ..., description="Stop identifier", json_schema_extra={"example": "S-505"}
    )


class EtaAttributesResponse(BaseModel):
    """ETA calculation result delivered in the JSON:API data object."""

    remaining_distance_m: float = Field(..., json_schema_extra={"example": 3200.0})
    current_speed_kmh: float = Field(..., json_schema_extra={"example": 32.5})
    speed_m_s: float = Field(..., json_schema_extra={"example": 9.03})
    eta_seconds: int = Field(..., json_schema_extra={"example": 354})
    eta_format: str = Field(..., json_schema_extra={"example": "5 min 54 s"})
    confidence: float = Field(..., json_schema_extra={"example": 0.82})
    calculated_at: str = Field(
        ..., json_schema_extra={"example": "2026-09-29T15:32:43Z"}
    )
    route_id: str = Field(..., json_schema_extra={"example": "R-101"})
    stop_id: str = Field(..., json_schema_extra={"example": "S-505"})


class EtaDataResponse(BaseModel):
    """JSON:API data wrapper for an ETA resource."""

    type: str = Field("eta", description="Resource type delivered")
    attributes: EtaAttributesResponse


class EtaResponse(BaseModel):
    """JSON:API response wrapper for an ETA calculation."""

    data: EtaDataResponse
