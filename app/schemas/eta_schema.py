from pydantic import BaseModel, Field

# 1. REQUEST SCHEMAS
class EtaRequest(BaseModel):
    remaining_distance_m: float = Field(
        ..., 
        gt=0, 
        description="Remaining distance in meters", 
        json_schema_extra={"example": 3200.0}
    )
    current_speed_kmh: float = Field(
        ..., 
        ge=0, 
        description="Current speed in km/h", 
        json_schema_extra={"example": 32.5}
    )
    
# 2. RESPONSE SCHEMAS
class EtaAttributesResponse(BaseModel):
    eta_seconds: int = Field(..., json_schema_extra={"example": 600})
    eta_formatted: str = Field(..., json_schema_extra={"example": "10 min 55 s"})
    confidence: float = Field(..., json_schema_extra={"example": 0.85})
    calculated_at: str = Field(..., json_schema_extra={"example": "2026-09-13T22:00:00Z"})

class EtaDataResponse(BaseModel):
    type: str = Field("eta", description="Resource type delivered")
    id: str = Field(..., json_schema_extra={"example": "0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"})
    attributes: EtaAttributesResponse

class EtaResponse(BaseModel):
    data: EtaDataResponse