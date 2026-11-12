from collections import defaultdict
from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_i18n import PydanticI18n, DictLoader

from app.api.arrivals_errors import ArrivalsApiError, JsonApiResponse, validation_response
from app.api.health import router as health_router
from app.api.v1.arrivals import router as arrivals_router, trip_arrivals

from app.api.v1.eta import router as eta_router
from app.schemas.batch_arrivals_schema import ARRIVALS_REQUEST_EXAMPLE, ARRIVALS_RESPONSE_EXAMPLE
from app.services.eta_service import EtaCalculationError
from app.i18n import __, get_locale, _translations

pydantic_translations = {
    "en_US": _translations.get("en", {}),
    "es_ES": _translations.get("es", {})
}
translation_loader = DictLoader(pydantic_translations)
validation_translator = PydanticI18n(translation_loader)

app = FastAPI(title="Smartbus ETA Calculation API")
app.include_router(eta_router, prefix="/api/v1/eta", tags=["ETA"])
app.include_router(arrivals_router, prefix="/api/v1/eta", tags=["ETA"])
app.include_router(health_router)

_default_openapi = app.openapi


def openapi_with_arrivals_examples() -> dict[str, Any]:
    schema = _default_openapi()
    operation = schema["paths"]["/api/v1/eta/trips/{trip_id}/arrivals"]["post"]
    request = operation["requestBody"]["content"]["application/json"]
    response = operation["responses"]["200"]["content"][JsonApiResponse.media_type]

    # FastAPI omits nulls during schema generation; these examples require them.
    request["examples"] = {"moving_bus": {"value": ARRIVALS_REQUEST_EXAMPLE}}
    response["example"] = ARRIVALS_RESPONSE_EXAMPLE
    return schema


app.openapi = openapi_with_arrivals_examples

@app.exception_handler(ArrivalsApiError)
async def arrivals_exception_handler(request: Request, exc: ArrivalsApiError):
    return exc.response(request)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.scope.get("endpoint") is trip_arrivals:
        return validation_response(request, exc)

    lang_code = get_locale(request)
    pydantic_locale = "es_ES" if lang_code == "es" else "en_US"
    
    translated_errors = validation_translator.translate(
        exc.errors(), locale=pydantic_locale
    )
    formatted_errors = defaultdict(list)

    for error in translated_errors:
        field_name = str(error["loc"][-1]) if error.get("loc") else "unknown"
        formatted_errors[field_name].append(error["msg"])

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "message": __("errors.validation_title", request),
            "errors": dict(formatted_errors),
        },
    )

@app.exception_handler(EtaCalculationError)
async def eta_calculation_error_handler(request: Request, exc: EtaCalculationError):
    error_key = str(exc) if str(exc) else "errors.unexpected"
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "message": __("errors.eta_calculation_title", request),
            "errors": {"service": [__(error_key, request)]},
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if request.scope.get("endpoint") is trip_arrivals:
        return ArrivalsApiError(500, "internal_error", detail="errors.unexpected").response(request)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": __("errors.internal_server_title", request),
            "errors": {"server": [__("errors.unexpected", request)]},
        },
    )
