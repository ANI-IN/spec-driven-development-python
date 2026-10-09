from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from minitrain.data import Dataset, make_dataset
from minitrain.logging_utils import JsonFormatter


class ListHandler(logging.Handler):
    """Collects formatted JSON log lines so tests can assert on them."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.setFormatter(JsonFormatter())
        self.lines: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(self.format(record)))

    def events(self, name: str) -> list[dict[str, Any]]:
        return [line for line in self.lines if line["event"] == name]


@pytest.fixture
def log_capture() -> Iterator[tuple[logging.Logger, ListHandler]]:
    logger = logging.getLogger(f"minitrain.test.{uuid.uuid4().hex}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = ListHandler()
    logger.addHandler(handler)
    yield logger, handler
    logger.removeHandler(handler)


@pytest.fixture
def quiet_logger() -> logging.Logger:
    logger = logging.getLogger("minitrain.test.quiet")
    logger.propagate = False
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


@pytest.fixture(scope="session")
def dataset() -> Dataset:
    return make_dataset()
