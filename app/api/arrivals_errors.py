"""JSON:API responses for the arrivals API."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.i18n import _translations, get_locale


class JsonApiResponse(JSONResponse):
    media_type = "application/vnd.api+json"


class ErrorSource(BaseModel):
    pointer: str | None = None
    parameter: str | None = None


class ArrivalError(BaseModel):
    status: str
    code: str
    title: str
    detail: str
    source: ErrorSource | None = None


class ArrivalErrors(BaseModel):
    errors: list[ArrivalError]


_TITLE_KEYS = {
    401: "errors.arrivals.unauthorized_title",
    403: "errors.arrivals.forbidden_title",
    404: "errors.arrivals.not_found_title",
    409: "errors.arrivals.conflict_title",
    422: "errors.validation_title",
    500: "errors.internal_server_title",
    502: "errors.arrivals.bad_gateway_title",
    503: "errors.arrivals.unavailable_title",
}

_VALIDATION_KEYS = {
    "missing": "errors.arrivals.required_field",
    "extra_forbidden": "errors.arrivals.unexpected_field",
    "json_invalid": "errors.arrivals.invalid_json",
}


def json_pointer(path: tuple[str | int, ...]) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)


class ArrivalsApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        *,
        detail: str | None = None,
        pointer: str | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.detail = detail or f"errors.arrivals.{code}"
        self.pointer = pointer

    def response(self, request: Request) -> JsonApiResponse:
        source = ErrorSource(pointer=self.pointer) if self.pointer is not None else None
        error = _error(self.status, self.code, self.detail, source, locale=get_locale(request))
        headers = {"WWW-Authenticate": "Bearer"} if self.status == 401 else None
        return JsonApiResponse(
            status_code=self.status,
            content=ArrivalErrors(errors=[error]).model_dump(exclude_none=True),
            headers=headers,
        )


def validation_response(request: Request, exception: RequestValidationError) -> JsonApiResponse:
    errors = []
    locale = get_locale(request)
    for error in exception.errors():
        location = error["loc"]
        if location[:1] == ("path",):
            source = ErrorSource(parameter=str(location[1]))
        elif error["type"] == "json_invalid":
            source = ErrorSource(pointer="")
        else:
            source = ErrorSource(pointer=json_pointer(location[1:]))
        detail = _VALIDATION_KEYS.get(error["type"], "errors.arrivals.invalid_field")
        errors.append(_error(422, "invalid_input", detail, source, locale=locale))

    return JsonApiResponse(
        status_code=422, content=ArrivalErrors(errors=errors).model_dump(exclude_none=True)
    )


def arrival_error_example(status: int, code: str) -> dict[str, object]:
    """Build an English OpenAPI example using the runtime error contract."""
    detail = {
        "invalid_input": "errors.arrivals.invalid_field",
        "internal_error": "errors.unexpected",
    }.get(code, f"errors.arrivals.{code}")
    source = (
        ErrorSource(pointer="/targets/0/remaining_distance_m") if code == "invalid_input" else None
    )
    error = _error(status, code, detail, source, locale="en")
    return ArrivalErrors(errors=[error]).model_dump(exclude_none=True)


def _error(
    status: int, code: str, detail: str, source: ErrorSource | None, *, locale: str
) -> ArrivalError:
    translations = _translations.get(locale, {})
    title = _TITLE_KEYS[status]
    return ArrivalError(
        status=str(status),
        code=code,
        title=translations.get(title, title),
        detail=translations.get(detail, detail),
        source=source,
    )
