"""One error shape for the whole API:  {"detail": "<human readable>", "code": "<MACHINE_CODE>"}

Clients branch on `code` (stable); humans read `detail` (can be reworded).
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("clinic.errors")


class AppError(Exception):
    status_code = 500

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    """State conflict: the request is valid but clashes with current data (slot taken, ...)."""

    status_code = 409


class UnprocessableError(AppError):
    """The request is well-formed but violates a business rule (past, outside hours, ...)."""

    status_code = 422


def _body(code: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"detail": detail, "code": code, **extra}


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(_body(exc.code, exc.detail), status_code=exc.status_code)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {"field": ".".join(map(str, e["loc"][1:])) or str(e["loc"][0]), "message": e["msg"]}
        for e in exc.errors()
    ]
    detail = "; ".join(f"{e['field']}: {e['message']}" for e in errors)
    return JSONResponse(_body("VALIDATION_ERROR", detail, errors=errors), status_code=422)


_HTTP_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(_body("INTERNAL_ERROR", "Internal server error"), status_code=500)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled)
