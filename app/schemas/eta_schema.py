from pydantic import BaseModel, Field


# 1. REQUEST SCHEMAS

class EtaRequest(BaseModel):
    remaining_distance_m: float = Field(..., gt=0, description="Remaining distance in meters", example=3200)
    current_speed_kmh: float = Field(..., ge=0, description="Current speed in km/h", example=32.5)
    
# 2. RESPONSE SCHEMAS

class EtaAttributesResponse(BaseModel):
    eta_seconds: int = Field(..., example=600)
    eta_formatted: str = Field(..., example="10 min 55 s")
    confidence: float = Field(..., example=0.85)
    calculated_at: str = Field(..., example="2023-10-01T12:00:00Z")

class EtaDataResponse(BaseModel):
    type: str = Field("eta", description="Resource type delivered")
    id: str = Field(..., example="0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11")
    attributes: EtaAttributesResponse

class EtaResponse(BaseModel):
    data: EtaDataResponse