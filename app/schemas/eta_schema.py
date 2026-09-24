from pydantic import BaseModel, Field

# 1. REQUEST SCHEMAS
class EtaRequest(BaseModel):
    remaining_distance_m: float = Field(
        ..., 
        ge=0, 
        allow_inf_nan=False,
        description="Remaining distance in meters", 
        json_schema_extra={"example": 3200.0}
    )
    current_speed_kmh: float = Field(
        ..., 
        gt=0, 
        allow_inf_nan=False,
        description="Current speed in km/h", 
        json_schema_extra={"example": 32.5}
    )
    route_id: str = Field(..., description="Route identifier", json_schema_extra={"example": "R-101"})
    stop_id: str = Field(..., description="Stop identifier", json_schema_extra={"example": "S-505"})
    
# 2. RESPONSE SCHEMAS
class EtaAttributesResponse(BaseModel):
    eta_seconds: int = Field(..., json_schema_extra={"example": 600})
    eta_format: str = Field(..., json_schema_extra={"example": "10 min 0 s"})
    confidence: float = Field(..., json_schema_extra={"example": 0.82})
    calculated_at: str = Field(..., json_schema_extra={"example": "2026-09-24T15:32:43Z"})

class EtaDataResponse(BaseModel):
    type: str = Field("eta", description="Resource type delivered")
    id: str = Field(..., json_schema_extra={"example": "0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"})
    attributes: EtaAttributesResponse

class EtaResponse(BaseModel):
    data: EtaDataResponse