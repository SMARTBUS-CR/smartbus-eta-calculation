from pydantic import BaseModel, Field
from typing import Optional

#schema for a request
class EtaAtributes(BaseModel):
    # Define the attributes for the Eta request
    route_id: str = Field(..., example="0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11")
    stop_id: str = Field(..., example="b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22")
    remaining_distance_m: float = Field(..., gt=0, description="Distancia restante en metros", example=3200)
    current_speed_kmh: float = Field(..., gt=0, description="Velocidad actual en km/h", example=32.5)

class EtaDataRequest(BaseModel):
    #objeto data dentro del estandar JSON API
    type: str = Field("eta_calculo", description="Tipo de recurso de la peticion")
    attributes: EtaAtributes

#schema for a response