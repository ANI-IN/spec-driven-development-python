from __future__ import annotations

import io
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from experiment_runs.app import create_app
from experiment_runs.logger import EventLogger
from experiment_runs.repository import RunRepository
from experiment_runs.service import RunService

START = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """A controllable ``now()`` for deterministic stall and ordering tests."""

    def __init__(self, start: datetime = START) -> None:
        self.now = start
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.now

    def advance(self, **delta: float) -> None:
        self.now = self.now + timedelta(**delta)


class LogCapture:
    """An ``EventLogger`` writing to memory, with helpers to read lines back."""

    def __init__(self) -> None:
        self.stream = io.StringIO()
        self.logger = EventLogger(self.stream)

    def lines(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.stream.getvalue().splitlines()]

    def events(self, name: str) -> list[dict[str, Any]]:
        return [line for line in self.lines() if line["event"] == name]


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def logs() -> LogCapture:
    return LogCapture()


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "runs.json"


@pytest.fixture
def repository(store_path: Path, logs: LogCapture) -> RunRepository:
    return RunRepository(store_path, logs.logger)


@pytest.fixture
def service(repository: RunRepository, clock: FakeClock) -> RunService:
    return RunService(repository, clock=clock)


@pytest.fixture
def client(service: RunService, logs: LogCapture) -> TestClient:
    return TestClient(create_app(service, logs.logger))


@pytest.fixture
def create_payload() -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": "baseline",
            "model_type": "logistic_regression",
            "hyperparameters": {"learning_rate": 0.05, "epochs": 20},
        }
        payload.update(overrides)
        return payload

    return build
