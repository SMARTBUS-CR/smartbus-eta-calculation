from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.v1.eta import router as eta_router

# Initialize FastAPI application
app = FastAPI(title="Smartbus ETA Calculation API")
app.include_router(eta_router, prefix="/api/v1/eta", tags=["ETA"])

# ==========================================
# 422 UNPROCESSABLE ENTITY HANDLER
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles Pydantic validation errors and translates them based on Accept-Language."""
    
    # Check language
    lang = request.headers.get("Accept-Language", "en").lower()
    is_spanish = "es" in lang

    formatted_errors = {}
    
    for error in exc.errors():
        field_name = str(error["loc"][-1]) if error["loc"] else "unknown"
        error_type = error["type"]
        
        # Basic translation logic
        if is_spanish:
            if error_type == "missing":
                error_message = "Campo requerido"
            elif error_type == "greater_than":
                error_message = "El valor debe ser mayor a 0"
            elif error_type == "greater_than_equal":
                error_message = "El valor debe ser mayor o igual a 0"
            else:
                error_message = "Error de validación"
        else:
            if error_type == "missing":
                error_message = "Field required"
            elif error_type == "greater_than":
                error_message = "Input should be greater than 0"
            elif error_type == "greater_than_equal":
                error_message = "Input should be greater than or equal to 0"
            else:
                error_message = "Validation error"

        if field_name not in formatted_errors:
            formatted_errors[field_name] = []
            
        formatted_errors[field_name].append(error_message)
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "message": "Error de validación" if is_spanish else "Validation error",
            "errors": formatted_errors
        }
    )

# ==========================================
# 503 SERVICE UNAVAILABLE HANDLER
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handles unexpected server errors, formats identically to 422, and translates."""
    
    # Check language
    lang = request.headers.get("Accept-Language", "en").lower()
    is_spanish = "es" in lang

    # Translate messages
    message = "Servicio no disponible" if is_spanish else "Service Unavailable"
    detail = (
        "Ocurrió un error inesperado al procesar el cálculo del ETA." 
        if is_spanish 
        else "An unexpected error occurred while processing the ETA calculation."
    )

    # Devolvemos la misma estructura: un "message" principal y un diccionario de "errors"
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "message": message,
            "errors": {
                "server": [detail]
            }
        }
    )