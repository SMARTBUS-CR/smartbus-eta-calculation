from pydantic import ValidationError
from app.schemas.eta_schema import EtaRequest

print("--- PRUEBAS DE VALIDACIÓN DE ERRORES ---")

# 1. Prueba: Distancia negativa o cero (debe fallar por gt=0)
bad_distance_payload = {
    "data": {
        "type": "eta_calculation",
        "attributes": {
            "route_id": "0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "stop_id": "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
            "remaining_distance_m": -500,  # ❌ Error: Distancia negativa
            "current_speed_kmh": 25.0
        }
    }
}

try:
    EtaRequest(**bad_distance_payload)
    print("❌ ERROR DE PRUEBA: El esquema aceptó una distancia negativa.")
except ValidationError as e:
    print("✅ PASÓ LA PRUEBA: Pydantic rechazó la distancia negativa correctamente.")

# 2. Prueba: Velocidad negativa (debe fallar por ge=0)
bad_speed_payload = {
    "data": {
        "type": "eta_calculation",
        "attributes": {
            "route_id": "0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "stop_id": "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
            "remaining_distance_m": 1200,
            "current_speed_kmh": -10.0  # ❌ Error: Velocidad negativa
        }
    }
}

try:
    EtaRequest(**bad_speed_payload)
    print("❌ ERROR DE PRUEBA: El esquema aceptó una velocidad negativa.")
except ValidationError as e:
    print("✅ PASÓ LA PRUEBA: Pydantic rechazó la velocidad negativa correctamente.")

# 3. Prueba: Faltan datos obligatorios (Falta route_id)
missing_field_payload = {
    "data": {
        "type": "eta_calculation",
        "attributes": {
            # "route_id" omitido a propósito ❌
            "stop_id": "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
            "remaining_distance_m": 1200,
            "current_speed_kmh": 20.0
        }
    }
}

try:
    EtaRequest(**missing_field_payload)
    print("❌ ERROR DE PRUEBA: El esquema aceptó la falta de route_id.")
except ValidationError as e:
    print("✅ PASÓ LA PRUEBA: Pydantic detectó que faltaba route_id obligatoriamente.")

# 4. Prueba: Tipo de dato incorrecto (String en vez de número en distancia)
bad_type_payload = {
    "data": {
        "type": "eta_calculation",
        "attributes": {
            "route_id": "0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "stop_id": "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22",
            "remaining_distance_m": "mil metros",  # ❌ Error: Debería ser un float
            "current_speed_kmh": 20.0
        }
    }
}

try:
    EtaRequest(**bad_type_payload)
    print("❌ ERROR DE PRUEBA: El esquema aceptó un texto en la distancia.")
except ValidationError as e:
    print("✅ PASÓ LA PRUEBA: Pydantic rechazó el tipo de dato no numérico.")