"""Process entry point: load settings and the store, then serve.

Exit codes: 0 after a clean shutdown, 1 when the store is corrupt (it has been
quarantined; the next start begins empty), 2 for invalid configuration.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

import uvicorn
from fastapi import FastAPI

from experiment_runs.app import create_app
from experiment_runs.config import Settings, load_settings
from experiment_runs.errors import StoreCorruptError, ValidationError
from experiment_runs.logger import EventLogger
from experiment_runs.repository import RunRepository
from experiment_runs.service import RunService


def build(env: Mapping[str, str], logger: EventLogger) -> tuple[FastAPI, Settings]:
    """Load settings and the store and return a ready app.

    Raises ``ValidationError`` or ``StoreCorruptError``; never starts a server.
    """
    settings = load_settings(env)
    repository = RunRepository(settings.store_path, logger)
    loaded = repository.load()
    service = RunService(repository, loaded.runs)
    logger.log(
        "server.started",
        host=settings.host,
        port=settings.port,
        store_path=str(settings.store_path),
        store_existed=loaded.existed,
        run_count=len(loaded.runs),
    )
    return create_app(service, logger), settings


def main(env: Mapping[str, str] | None = None) -> int:
    logger = EventLogger()
    try:
        app, settings = build(os.environ if env is None else env, logger)
    except ValidationError as exc:
        logger.log(
            "server.start_failed",
            reason="invalid_config",
            details=[f"{d.field}: {d.message}" for d in exc.details],
        )
        return 2
    except StoreCorruptError as exc:
        logger.log(
            "server.start_failed",
            reason="store_corrupt",
            quarantined_path=str(exc.quarantined_path),
        )
        return 1

    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
    logger.log("server.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
