"""Structured logging: one JSON object per line.

Every training event carries a ``run_id`` so all lines from one run can be
grouped, plus whatever fields the caller adds (``epoch``, ``val_loss``, ...).
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, TextIO

LOGGER_NAME = "minitrain"


class JsonFormatter(logging.Formatter):
    """Render a record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update({key: _json_safe(value) for key, value in fields.items()})
        return json.dumps(payload, sort_keys=False, default=str, allow_nan=False)


# Any: log fields can hold any JSON-like value.
def _json_safe(value: Any) -> Any:
    """Strict JSON has no NaN or Infinity, so write them as strings, at any depth."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value


if TYPE_CHECKING:
    _StreamHandler = logging.StreamHandler[TextIO]
else:  # StreamHandler is only subscriptable at runtime on Python 3.11+
    _StreamHandler = logging.StreamHandler


class _CurrentStderrHandler(_StreamHandler):
    """Writes to whatever ``sys.stderr`` is at emit time, not at creation."""

    @property
    def stream(self) -> TextIO:
        return sys.stderr

    @stream.setter
    def stream(self, value: TextIO) -> None:
        pass  # always follow sys.stderr


def get_logger() -> logging.Logger:
    """Return the package logger, writing JSON lines to stderr by default."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = _CurrentStderrHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Log ``event`` with structured ``fields``."""
    logger.log(level, event, extra={"fields": fields})
