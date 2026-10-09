"""Domain entities and their on-disk record format.

This module knows nothing about HTTP or files: it defines what a run is and
how it converts to and from a plain JSON-compatible ``dict``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from experiment_runs.errors import InvalidRecordError

RunStatus = Literal["running", "finished"]
HyperparameterValue = str | int | float | bool


def format_timestamp(moment: datetime) -> str:
    """UTC, millisecond precision, ``Z`` suffix: ``2026-10-10T08:30:00.000Z``."""
    utc = moment.astimezone(timezone.utc)
    return utc.isoformat(timespec="milliseconds").replace("+00:00", "Z")


TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


def parse_timestamp(text: str) -> datetime:
    """Inverse of :func:`format_timestamp`.

    Accepts exactly the stored shape (date, time, fraction, and a zone), on
    every supported Python version.
    """
    try:
        moment = datetime.strptime(text, TIMESTAMP_FORMAT)
        return moment.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise InvalidRecordError(f"not a stored timestamp: {text!r}") from exc


@dataclass(frozen=True)
class Run:
    """One training run of one model."""

    id: str
    name: str
    model_type: str
    started_at: datetime
    hyperparameters: dict[str, HyperparameterValue] = field(default_factory=dict)
    time_budget_minutes: int | None = None
    status: RunStatus = "running"
    finished_at: datetime | None = None
    metrics: dict[str, float] | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "model_type": self.model_type,
            "hyperparameters": dict(self.hyperparameters),
            "time_budget_minutes": self.time_budget_minutes,
            "status": self.status,
            "started_at": format_timestamp(self.started_at),
            "finished_at": (
                format_timestamp(self.finished_at) if self.finished_at else None
            ),
            "metrics": dict(self.metrics) if self.metrics is not None else None,
        }

    @classmethod
    def from_record(cls, record: object) -> Run:
        """Rebuild a run from :meth:`to_record` output.

        Raises :class:`InvalidRecordError` for any record that
        :meth:`to_record` could not have produced (data-model invariants 2-5).
        """
        if not isinstance(record, dict):
            raise InvalidRecordError("run record must be an object")
        try:
            return cls._from_dict(record)
        except KeyError as exc:
            raise InvalidRecordError(f"run record is missing {exc}") from exc

    @classmethod
    def _from_dict(cls, record: dict[str, object]) -> Run:
        status = record["status"]
        if status != "running" and status != "finished":
            raise InvalidRecordError(f"unknown status: {status!r}")

        hyperparameters = record["hyperparameters"]
        if not isinstance(hyperparameters, dict):
            raise InvalidRecordError("hyperparameters must be an object")
        params: dict[str, HyperparameterValue] = {}
        for key, value in hyperparameters.items():
            if not isinstance(value, str | int | float | bool):
                raise InvalidRecordError("hyperparameters must map names to scalars")
            if isinstance(value, float) and not math.isfinite(value):
                raise InvalidRecordError("hyperparameter values must be finite")
            params[str(key)] = value

        budget = record["time_budget_minutes"]
        if budget is not None and (
            isinstance(budget, bool) or not isinstance(budget, int)
        ):
            raise InvalidRecordError("time_budget_minutes must be an integer or null")

        raw_metrics = record["metrics"]
        metrics: dict[str, float] | None = None
        if raw_metrics is not None:
            if not isinstance(raw_metrics, dict):
                raise InvalidRecordError("metrics must be an object or null")
            metrics = {str(k): _finite_float(v) for k, v in raw_metrics.items()}

        finished_raw = record["finished_at"]
        finished_at = (
            None if finished_raw is None else parse_timestamp(_text(finished_raw))
        )
        if status == "finished" and (finished_at is None or metrics is None):
            raise InvalidRecordError("a finished run needs finished_at and metrics")
        if status == "running" and (finished_at is not None or metrics is not None):
            raise InvalidRecordError("a running run has no finished_at or metrics")

        return cls(
            id=_text(record["id"]),
            name=_text(record["name"]),
            model_type=_text(record["model_type"]),
            hyperparameters=params,
            time_budget_minutes=budget,
            status=status,
            started_at=parse_timestamp(_text(record["started_at"])),
            finished_at=finished_at,
            metrics=metrics,
        )


@dataclass(frozen=True)
class RunView:
    """A run plus the fields derived at read time."""

    run: Run
    stalled: bool


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidRecordError("expected a non-empty string")
    return value


def _finite_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidRecordError("metric values must be numbers")
    try:
        number = float(value)
    except OverflowError as exc:
        raise InvalidRecordError("metric values must be finite") from exc
    if not math.isfinite(number):
        raise InvalidRecordError("metric values must be finite")
    return number
