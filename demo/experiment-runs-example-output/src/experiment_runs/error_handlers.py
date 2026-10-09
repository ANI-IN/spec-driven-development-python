"""Map exceptions to HTTP responses in one place (research.md, Decision 2).

Branches on exception class only. Each handler records the error class on
``request.state`` so the request log line can report it.
"""

from __future__ import annotations

import traceback
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from experiment_runs.errors import (
    AppError,
    NotFoundError,
    RunAlreadyFinishedError,
    StoreCorruptError,
    StoreWriteError,
    ValidationError,
)
from experiment_runs.logger import EventLogger
from experiment_runs.schemas import ErrorDetail, ErrorResponse


def _response(
    status_code: int,
    error: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=error, message=message, details=details)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
        headers=dict(headers) if headers else None,
    )


# Mapping fields are reported down to the key (``metrics.auc``). Anything
# deeper is Pydantic naming the union branch it tried (``metrics.auc.int``),
# so it is cut off; a key that happens to be called ``int`` is kept.
_MAPPING_FIELDS = {"hyperparameters", "metrics"}


# Any: Pydantic's error dictionaries are untyped (values may be any JSON).
def _field_name(err: Mapping[str, Any]) -> str:
    """``("body", "metrics", "auc")`` becomes ``"metrics.auc"``.

    Malformed JSON has no field, so it is reported as ``body``.
    """
    if err.get("type") == "json_invalid":
        return "body"
    parts = [str(part) for part in err.get("loc", ())]
    if parts and parts[0] == "body":
        parts = parts[1:]
    depth = 2 if parts and parts[0] in _MAPPING_FIELDS else 1
    return ".".join(parts[:depth]) or "body"


def error_response(exc: AppError) -> JSONResponse:
    if isinstance(exc, ValidationError):
        details = [ErrorDetail(field=d.field, message=d.message) for d in exc.details]
        return _response(400, "validation_error", exc.message, details)
    if isinstance(exc, NotFoundError):
        return _response(404, "not_found", exc.message)
    if isinstance(exc, RunAlreadyFinishedError):
        return _response(409, "already_finished", exc.message)
    if isinstance(exc, StoreCorruptError):
        return _response(500, "internal_error", "store is corrupt")
    if isinstance(exc, StoreWriteError):
        return _response(500, "internal_error", "write failed")
    return _response(500, "internal_error", "unexpected error")


def register_error_handlers(app: FastAPI, logger: EventLogger) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request.state.error_class = type(exc).__name__
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request.state.error_class = "ValidationError"
        details: list[ErrorDetail] = []
        for err in exc.errors():
            field = _field_name(err)
            # A union reports one error per branch; keep the first per field.
            if all(d.field != field for d in details):
                details.append(ErrorDetail(field=field, message=str(err["msg"])))
        return _response(400, "validation_error", "invalid request body", details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Framework errors (unknown path, wrong method, unparsable body)."""
        codes = {404: "not_found", 405: "method_not_allowed"}
        error = codes.get(exc.status_code, "bad_request")
        request.state.error_class = type(exc).__name__
        return _response(exc.status_code, error, str(exc.detail), headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        request.state.error_class = type(exc).__name__
        logger.log(
            "request.unexpected_error",
            error_class=type(exc).__name__,
            error=str(exc),
            stack=traceback.format_exception(type(exc), exc, exc.__traceback__),
        )
        return _response(500, "internal_error", "unexpected error")
