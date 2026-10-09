"""Process entry point: load settings and the store, then serve.

Exit codes:

- ``0`` after a clean shutdown (Ctrl+C or SIGTERM),
- ``1`` when the store is corrupt (it has been quarantined; the next start
  begins empty),
- ``2`` for invalid configuration,
- ``3`` when the server cannot start, for example because the port is taken.
"""

from __future__ import annotations

import os
import signal
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI

from experiment_runs.app import create_app
from experiment_runs.config import Settings, load_settings
from experiment_runs.errors import StoreCorruptError, ValidationError
from experiment_runs.logger import EventLogger
from experiment_runs.repository import RunRepository
from experiment_runs.service import RunService

STARTUP_FAILED = 3


@dataclass(frozen=True)
class Startup:
    """A ready app plus the facts the ``server.started`` line reports."""

    app: FastAPI
    settings: Settings
    store_existed: bool
    run_count: int


def build(env: Mapping[str, str], logger: EventLogger) -> Startup:
    """Load settings and the store and return a ready app.

    Raises ``ValidationError`` or ``StoreCorruptError``; never starts a server.
    """
    settings = load_settings(env)
    repository = RunRepository(settings.store_path, logger)
    loaded = repository.load()
    service = RunService(repository, loaded.runs)
    return Startup(
        app=create_app(service, logger),
        settings=settings,
        store_existed=loaded.existed,
        run_count=len(loaded.runs),
    )


class _Server(uvicorn.Server):
    """Calls ``on_started`` only once the socket is actually listening."""

    def __init__(self, config: uvicorn.Config, on_started: Callable[[], None]) -> None:
        super().__init__(config)
        self._on_started = on_started

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        if self.started:
            self._on_started()


def serve(startup: Startup, logger: EventLogger) -> bool:
    """Run the server until it stops. Returns ``False`` if it never started."""
    settings = startup.settings

    def on_started() -> None:
        logger.log(
            "server.started",
            host=settings.host,
            port=settings.port,
            store_path=str(settings.store_path),
            store_existed=startup.store_existed,
            run_count=startup.run_count,
        )

    config = uvicorn.Config(
        startup.app, host=settings.host, port=settings.port, log_level="warning"
    )
    server = _Server(config, on_started)
    # Uvicorn re-raises the SIGTERM it handled once it has shut down; with the
    # default handler that kills the process before we can log the shutdown.
    previous = signal.signal(signal.SIGTERM, lambda signum, frame: None)
    try:
        server.run()
    except SystemExit:
        if server.started:
            raise
        return False
    finally:
        signal.signal(signal.SIGTERM, previous)
    return True


def main(env: Mapping[str, str] | None = None) -> int:
    logger = EventLogger()
    try:
        startup = build(os.environ if env is None else env, logger)
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

    if not serve(startup, logger):
        logger.log(
            "server.start_failed",
            reason="startup_failed",
            host=startup.settings.host,
            port=startup.settings.port,
        )
        return STARTUP_FAILED
    logger.log("server.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
