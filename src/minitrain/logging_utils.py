"""Structured logging: one JSON object per line.

Every training event carries a ``run_id`` so all lines from one run can be
grouped, plus whatever fields the caller adds (``epoch``, ``val_loss``, ...).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

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
            payload.update(fields)
        return json.dumps(payload, sort_keys=False, default=str)


def get_logger() -> logging.Logger:
    """Return the package logger, writing JSON lines to stderr by default."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
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
