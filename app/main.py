from collections import defaultdict
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic_i18n import DictLoader, PydanticI18n

from app.api.arrivals_errors import ArrivalsApiError, JsonApiResponse, validation_response
from app.api.health import router as health_router
from app.api.v1.arrivals import router as arrivals_router
from app.api.v1.arrivals import trip_arrivals
from app.api.v1.eta import router as eta_router
from app.i18n import __, _translations, get_locale
from app.schemas.batch_arrivals_schema import ARRIVALS_REQUEST_EXAMPLE, ARRIVALS_RESPONSE_EXAMPLE
from app.services.eta_service import EtaCalculationError

pydantic_translations = {"en_US": _translations.get("en", {}), "es_ES": _translations.get("es", {})}
translation_loader = DictLoader(pydantic_translations)
validation_translator = PydanticI18n(translation_loader)

API_DESCRIPTION = (
    "API for SmartBus **ETA Calculation Service**. This service is responsible for "
    "predicting estimated arrival times for bus routes and stops using machine learning inference "
    "and deterministic fallback methods. <br><br> "
    "All the endpoints described in this documentation follow the "
    "[JSON:API](https://jsonapi.org/) specification for request and response formats."
)

app = FastAPI(
    title="SmartBus ETA Calculation API",
    version="2.0.0",
    description=API_DESCRIPTION,
)
app.include_router(eta_router, prefix="/api/v1/eta", tags=["ETA"])
app.include_router(arrivals_router, prefix="/api/v1/eta", tags=["ETA"])
app.include_router(health_router)

_default_openapi = app.openapi


def openapi_with_arrivals_examples() -> dict[str, Any]:
    schema = _default_openapi()
    schema["security"] = [{"http": []}]
    paths = schema.get("paths", {})
    for public_path, method in [
        ("/health/live", "get"),
        ("/health/ready", "get"),
        ("/api/v1/eta/calculate", "post"),
    ]:
        if public_path in paths and method in paths[public_path]:
            paths[public_path][method]["security"] = []

    operation = schema["paths"]["/api/v1/eta/trips/{trip_id}/arrivals"]["post"]
    request = operation["requestBody"]["content"]["application/json"]
    response = operation["responses"]["200"]["content"][JsonApiResponse.media_type]

    # FastAPI omits nulls during schema generation; these examples require them.
    request["examples"] = {"moving_bus": {"value": ARRIVALS_REQUEST_EXAMPLE}}
    response["example"] = ARRIVALS_RESPONSE_EXAMPLE
    return schema


app.openapi = openapi_with_arrivals_examples


@app.get("/", include_in_schema=False)
async def root_docs_redirect() -> RedirectResponse:
    """Redirect the root URL directly to the interactive Scalar API documentation."""
    return RedirectResponse(url="/docs/api", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/docs/api.json", include_in_schema=False)
async def openapi_json_spec() -> JSONResponse:
    """Serve the OpenAPI specification as a JSON document."""
    return JSONResponse(content=app.openapi())


@app.get("/docs/api", include_in_schema=False, response_class=HTMLResponse)
async def scalar_docs() -> HTMLResponse:
    """Render modern Scalar API documentation referencing the OpenAPI document."""
    html_content = """<!doctype html>
<html>
  <head>
    <title>SmartBus ETA Calculation API - Documentation</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body {
        margin: 0;
        padding: 0;
      }
      .scalar-top-nav {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 12px;
        padding: 8px 20px;
        background-color: #120e1f;
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 13px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      }
      .scalar-top-nav a {
        color: #c4b5fd;
        text-decoration: none;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 500;
        transition: background-color 0.15s ease, color 0.15s ease;
      }
      .scalar-top-nav a:hover {
        background-color: rgba(196, 181, 253, 0.15);
        color: #ffffff;
      }
      .scalar-top-nav .nav-label {
        margin-right: auto;
        color: #9ca3af;
        font-weight: 600;
        letter-spacing: 0.02em;
      }
      .scalar-top-nav .nav-separator {
        color: #4b5563;
        user-select: none;
      }
    </style>
  </head>
  <body>
    <nav class="scalar-top-nav">
      <span class="nav-label">SmartBus ETA Documentation</span>
      <a href="/docs" target="_self" title="Interactive Swagger UI Explorer">Swagger UI</a>
      <span class="nav-separator">|</span>
      <a href="/redoc" target="_self" title="ReDoc API Reference">ReDoc</a>
      <span class="nav-separator">|</span>
      <a href="/docs/api.json" target="_blank" title="Raw OpenAPI Specification">OpenAPI JSON</a>
    </nav>
    <script
      id="api-reference"
      data-url="/docs/api.json"
      data-configuration='{"theme":"purple","darkMode":true}'>
    </script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.exception_handler(ArrivalsApiError)
async def arrivals_exception_handler(request: Request, exc: ArrivalsApiError):
    return exc.response(request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.scope.get("endpoint") is trip_arrivals:
        return validation_response(request, exc)

    lang_code = get_locale(request)
    pydantic_locale = "es_ES" if lang_code == "es" else "en_US"

    translated_errors = validation_translator.translate(exc.errors(), locale=pydantic_locale)
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
