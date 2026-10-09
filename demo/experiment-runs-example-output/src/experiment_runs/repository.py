"""Storage only: load and save the run store (constitution principle IV).

The store is one JSON file, ``{"schema_version": 1, "runs": [...]}``. Every
write goes through :func:`atomic_write_bytes`. No HTTP and no business rules.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from experiment_runs.atomic_write import atomic_write_bytes
from experiment_runs.errors import (
    InvalidRecordError,
    StoreCorruptError,
    StoreWriteError,
)
from experiment_runs.logger import EventLogger
from experiment_runs.models import Run

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LoadResult:
    runs: list[Run]
    existed: bool


class RunRepository:
    def __init__(self, store_path: Path, logger: EventLogger) -> None:
        self.store_path = store_path
        self._logger = logger
        self._write_lock = threading.Lock()

    def load(self) -> LoadResult:
        """Read every run, or quarantine the file and raise if it is unusable."""
        if not self.store_path.exists():
            self._logger.log(
                "store.initialized", existed=False, store_path=str(self.store_path)
            )
            return LoadResult(runs=[], existed=False)

        try:
            document = json.loads(self.store_path.read_bytes())
            runs = _parse_document(document)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            RecursionError,
            InvalidRecordError,
        ) as exc:
            quarantined = self._quarantine()
            self._logger.log(
                "store.quarantined",
                store_path=str(self.store_path),
                quarantined_path=str(quarantined),
                error_class=type(exc).__name__,
                error=str(exc),
            )
            raise StoreCorruptError(
                f"store is unreadable; moved to {quarantined}", quarantined
            ) from exc

        self._logger.log(
            "store.loaded",
            existed=True,
            count=len(runs),
            store_path=str(self.store_path),
        )
        return LoadResult(runs=runs, existed=True)

    def save_all(self, runs: Sequence[Run]) -> None:
        """Atomically replace the store with ``runs``. Writes never interleave."""
        payload = {
            "schema_version": SCHEMA_VERSION,
            "runs": [run.to_record() for run in runs],
        }
        data = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
        with self._write_lock:
            try:
                durable = atomic_write_bytes(self.store_path, data)
            except OSError as exc:
                self._logger.log(
                    "store.write",
                    outcome=type(exc).__name__,
                    count=len(runs),
                    error=str(exc),
                )
                raise StoreWriteError(f"could not write store: {exc}") from exc
        if not durable:
            self._logger.log(
                "store.write_not_durable",
                count=len(runs),
                reason="directory fsync failed after rename",
            )
        self._logger.log("store.write", outcome="success", count=len(runs))

    def _quarantine(self) -> Path:
        """Rename the bad file aside. Never overwrites an earlier quarantine."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        base = self.store_path.with_name(f"{self.store_path.name}.corrupt.{stamp}")
        candidate, suffix = base, 1
        while candidate.exists():
            candidate = base.with_name(f"{base.name}-{suffix}")
            suffix += 1
        os.rename(self.store_path, candidate)
        return candidate


def _parse_document(document: object) -> list[Run]:
    if not isinstance(document, dict):
        raise InvalidRecordError("store must be a JSON object")
    version = document.get("schema_version")
    if version != SCHEMA_VERSION:
        raise InvalidRecordError(f"unsupported schema_version: {version!r}")
    records = document.get("runs")
    if not isinstance(records, list):
        raise InvalidRecordError("store 'runs' must be a list")
    runs = [Run.from_record(record) for record in records]
    if len({run.id for run in runs}) != len(runs):
        raise InvalidRecordError("store contains duplicate run ids")
    return runs
