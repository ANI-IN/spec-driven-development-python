"""Structured logger: exactly one JSON object per line on stdout (FR-016..FR-018)."""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from typing import TextIO


def _utc_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventLogger:
    """Writes ``{"timestamp": ..., "event": ..., **fields}`` lines.

    ``stream`` defaults to whatever ``sys.stdout`` is at write time, so test
    capture works without extra wiring.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream
        self._lock = threading.Lock()

    def log(self, event: str, **fields: object) -> None:
        record: dict[str, object] = {"timestamp": _utc_timestamp(), "event": event}
        record.update(fields)
        line = json.dumps(record, default=str)
        stream = self._stream or sys.stdout
        with self._lock:
            stream.write(line + "\n")
            stream.flush()
