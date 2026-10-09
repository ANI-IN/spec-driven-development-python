"""Assemble the FastAPI app. No server start here, so tests can build it freely."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.routing import Route

from experiment_runs.error_handlers import register_error_handlers
from experiment_runs.logger import EventLogger
from experiment_runs.routes import router
from experiment_runs.service import RunService


def create_app(service: RunService, logger: EventLogger) -> FastAPI:
    app = FastAPI(
        title="Experiment Runs API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.run_service = service
    app.include_router(router)
    register_error_handlers(app, logger)

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Unexpected errors are answered by the outermost server-error
            # middleware, so log the outcome here before re-raising.
            _log_outcome(request, logger, started, 500, type(exc).__name__)
            raise
        error_class = getattr(request.state, "error_class", None)
        if error_class is None and response.status_code >= 400:
            error_class = f"http_{response.status_code}"
        _log_outcome(request, logger, started, response.status_code, error_class)
        return response

    return app


def _log_outcome(
    request: Request,
    logger: EventLogger,
    started: float,
    status: int,
    error_class: str | None,
) -> None:
    """FR-016: one line per request, with the operation and its outcome."""
    route = request.scope.get("route")
    # On 405 Starlette leaves a partially matched route in scope; ignore it.
    matched = isinstance(route, Route) and status != 405
    fields: dict[str, object] = {
        "operation": route.name if matched and isinstance(route, Route) else "unknown",
        "method": request.method,
        "path": request.url.path,
        "status": status,
        "outcome": error_class or "success",
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    run_id = request.path_params.get("run_id")
    if run_id is not None:
        fields["run_id"] = run_id
    logger.log("request.error" if error_class else "request.ok", **fields)
