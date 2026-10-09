"""Domain logic for runs: validation, stall detection, ordering.

No HTTP types are imported here (constitution principle IV). State changes are
applied in memory only after the repository has durably saved them, so an
acknowledged change is always on disk and a failed write changes nothing.
"""

from __future__ import annotations

import math
import threading
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from experiment_runs.errors import (
    FieldError,
    NotFoundError,
    RunAlreadyFinishedError,
    ValidationError,
)
from experiment_runs.models import HyperparameterValue, Run, RunView
from experiment_runs.repository import RunRepository

NAME_MAX_LENGTH = 200
MODEL_TYPE_MAX_LENGTH = 100
KEY_MAX_LENGTH = 100
MAX_HYPERPARAMETERS = 50
MAX_METRICS = 50
TIME_BUDGET_MAX_MINUTES = 10_080  # one week

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_stalled(run: Run, now: datetime) -> bool:
    """FR-009: running, has a budget, and has been running longer than it."""
    if run.status != "running" or run.time_budget_minutes is None:
        return False
    return now - run.started_at > timedelta(minutes=run.time_budget_minutes)


def order_runs(runs: Iterable[Run], now: datetime) -> list[RunView]:
    """FR-004a ordering, evaluated against a single ``now``.

    1. Stalled runs, longest-running first (``started_at`` ascending).
    2. Other running runs, ``started_at`` ascending.
    3. Finished runs, most recently finished first.
    Ties break on ``id`` so the order is fully deterministic.
    """
    views = [RunView(run=run, stalled=is_stalled(run, now)) for run in runs]
    stalled = sorted(
        (v for v in views if v.stalled), key=lambda v: (v.run.started_at, v.run.id)
    )
    running = sorted(
        (v for v in views if v.run.status == "running" and not v.stalled),
        key=lambda v: (v.run.started_at, v.run.id),
    )
    finished = sorted(
        (v for v in views if v.run.status == "finished"),
        key=lambda v: (v.run.finished_at or v.run.started_at, v.run.id),
        reverse=True,
    )
    return stalled + running + finished


class RunService:
    def __init__(
        self,
        repository: RunRepository,
        runs: Iterable[Run] = (),
        *,
        clock: Clock = utc_now,
        new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._repository = repository
        self._runs: dict[str, Run] = {run.id: run for run in runs}
        self._clock = clock
        self._new_id = new_id
        self._lock = threading.Lock()

    def create(
        self,
        *,
        name: str,
        model_type: str,
        hyperparameters: Mapping[str, HyperparameterValue] | None = None,
        time_budget_minutes: int | None = None,
    ) -> RunView:
        errors: list[FieldError] = []
        clean_name = _required_text("name", name, NAME_MAX_LENGTH, errors)
        clean_model = _required_text(
            "model_type", model_type, MODEL_TYPE_MAX_LENGTH, errors
        )
        clean_params = _hyperparameters(hyperparameters or {}, errors)
        _check_budget(time_budget_minutes, errors)
        if errors:
            raise ValidationError("invalid run", errors)

        now = self._clock()
        run = Run(
            id=self._new_id(),
            name=clean_name,
            model_type=clean_model,
            hyperparameters=clean_params,
            time_budget_minutes=time_budget_minutes,
            started_at=now,
        )
        with self._lock:
            self._commit({**self._runs, run.id: run})
        return RunView(run=run, stalled=is_stalled(run, now))

    def list_runs(self) -> list[RunView]:
        with self._lock:
            runs = list(self._runs.values())
        return order_runs(runs, self._clock())

    def finish(self, run_id: str, metrics: Mapping[str, float]) -> RunView:
        clean_metrics = _metrics(metrics)
        with self._lock:
            run = self._get(run_id)
            if run.status == "finished":
                raise RunAlreadyFinishedError(f"run {run_id} is already finished")
            now = self._clock()
            finished = replace(
                run, status="finished", finished_at=now, metrics=clean_metrics
            )
            self._commit({**self._runs, run_id: finished})
        return RunView(run=finished, stalled=False)

    def delete(self, run_id: str) -> None:
        with self._lock:
            self._get(run_id)
            remaining = {k: v for k, v in self._runs.items() if k != run_id}
            self._commit(remaining)

    def _get(self, run_id: str) -> Run:
        run = self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"no run with id {run_id}")
        return run

    def _commit(self, runs: dict[str, Run]) -> None:
        """Persist first; only a successful write changes what callers see."""
        self._repository.save_all(list(runs.values()))
        self._runs = runs


def _required_text(
    field: str, value: str, max_length: int, errors: list[FieldError]
) -> str:
    clean = value.strip()
    if not clean:
        errors.append(FieldError(field, "must not be empty or whitespace"))
    elif len(clean) > max_length:
        errors.append(FieldError(field, f"must be at most {max_length} characters"))
    return clean


def _check_key(field: str, key: str, errors: list[FieldError]) -> bool:
    if not key.strip() or len(key) > KEY_MAX_LENGTH:
        errors.append(
            FieldError(field, f"keys must be 1 to {KEY_MAX_LENGTH} non-blank chars")
        )
        return False
    return True


def _hyperparameters(
    values: Mapping[str, HyperparameterValue], errors: list[FieldError]
) -> dict[str, HyperparameterValue]:
    if len(values) > MAX_HYPERPARAMETERS:
        errors.append(
            FieldError("hyperparameters", f"at most {MAX_HYPERPARAMETERS} entries")
        )
    for key, value in values.items():
        field = f"hyperparameters.{key}"
        _check_key("hyperparameters", key, errors)
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(FieldError(field, "must be a finite number"))
    return dict(values)


def _check_budget(minutes: int | None, errors: list[FieldError]) -> None:
    if minutes is not None and not 1 <= minutes <= TIME_BUDGET_MAX_MINUTES:
        errors.append(
            FieldError(
                "time_budget_minutes",
                f"must be between 1 and {TIME_BUDGET_MAX_MINUTES}",
            )
        )


def _metrics(values: Mapping[str, float]) -> dict[str, float]:
    errors: list[FieldError] = []
    if not values:
        errors.append(FieldError("metrics", "must contain at least one metric"))
    if len(values) > MAX_METRICS:
        errors.append(FieldError("metrics", f"at most {MAX_METRICS} entries"))
    clean: dict[str, float] = {}
    for key, value in values.items():
        if not _check_key("metrics", key, errors):
            continue
        try:
            number = float(value)
        except OverflowError:  # an integer too large for a float
            number = math.inf
        if not math.isfinite(number):
            errors.append(FieldError(f"metrics.{key}", "must be a finite number"))
        clean[key] = number
    if errors:
        raise ValidationError("invalid metrics", errors)
    return clean
