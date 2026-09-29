from collections import defaultdict
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_i18n import PydanticI18n, DictLoader

from app.api.v1.eta import router as eta_router
from app.services.eta_service import EtaCalculationError
from app.i18n import __, get_locale, _translations

pydantic_dict = {
    "en_US": _translations.get("en", {}),
    "es_ES": _translations.get("es", {})
}
loader = DictLoader(pydantic_dict)
tr = PydanticI18n(loader)

app = FastAPI(title="Smartbus ETA Calculation API")
app.include_router(eta_router, prefix="/api/v1/eta", tags=["ETA"])

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    lang_code = get_locale(request)
    pydantic_locale = "es_ES" if lang_code == "es" else "en_US"
    
    translated_errors = tr.translate(exc.errors(), locale=pydantic_locale)
    formatted_errors = defaultdict(list)

    for error in translated_errors:
        field_name = str(error["loc"][-1]) if error.get("loc") else "unknown"
        formatted_errors[field_name].append(error["msg"])

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "message": __("errors.validation_title", request),
            "errors": dict(formatted_errors)
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
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": __("errors.internal_server_title", request),
            "errors": {"server": [__("errors.unexpected", request)]},
        },
    )