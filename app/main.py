from collections import defaultdict
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.v1.eta import router as eta_router

# Initialize FastAPI application
app = FastAPI(title="Smartbus ETA Calculation API")
app.include_router(eta_router, prefix="/api/v1/eta", tags=["ETA"])

# 1. Lookup table to eliminate nested conditionals
TRANSLATIONS = {
    "es": {
        "missing": "Campo requerido",
        "greater_than": "El valor debe ser mayor a 0",
        "greater_than_equal": "El valor debe ser mayor o igual a 0",
        "default_field_error": "Error de validación",
        "validation_title": "Error de validación",
        "server_error_title": "Error interno del servidor",
        "server_error_detail": "Ocurrió un error inesperado al procesar el cálculo del ETA.",
    },
    "en": {
        "missing": "Field required",
        "greater_than": "Input should be greater than 0",
        "greater_than_equal": "Input should be greater than or equal to 0",
        "default_field_error": "Validation error",
        "validation_title": "Validation error",
        "server_error_title": "Internal Server Error",
        "server_error_detail": "An unexpected error occurred while processing the ETA calculation.",
    },
}

def get_language(request: Request) -> str:
    lang = request.headers.get("Accept-Language", "en").lower()
    return "es" if "es" in lang else "en"

# ==========================================
# 422 UNPROCESSABLE ENTITY HANDLER
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    lang = get_language(request)
    texts = TRANSLATIONS[lang]
    formatted_errors = defaultdict(list)

    for error in exc.errors():
        field_name = str(error["loc"][-1]) if error.get("loc") else "unknown"
        error_type = error.get("type", "")
        error_message = texts.get(error_type, texts["default_field_error"])
        formatted_errors[field_name].append(error_message)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": texts["validation_title"], "errors": dict(formatted_errors)},
    )

# ==========================================
# 500 INTERNAL SERVER ERROR HANDLER
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    lang = get_language(request)
    texts = TRANSLATIONS[lang]

    # Corrected status code from 503 to 500
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": texts["server_error_title"],
            "errors": {"server": [texts["server_error_detail"]]},
        },
    )