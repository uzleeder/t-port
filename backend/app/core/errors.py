"""Structured application errors and their HTTP mapping.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "details": [...]}}
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class ProvidersUnavailable(AppError):
    status_code = 503
    code = "providers_unavailable"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


def error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, exc.details), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ()) if p not in ("query", "body")),
                "message": err.get("msg", "Invalid value"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(error_body("validation_error", "Request validation failed.", details), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(error_body(code, str(exc.detail)), exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        import logging

        logging.getLogger("tport").exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(error_body("internal_error", "An unexpected error occurred."), 500)
