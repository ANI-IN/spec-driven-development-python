"""SC-004: every operation under 100 ms (p95) with 1,000 runs in the store.

Skip on slow shared CI hardware with ``CI_SKIP_PERF=1``.
"""

from __future__ import annotations

import os
import statistics
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from experiment_runs.models import Run
from experiment_runs.repository import RunRepository
from experiment_runs.service import RunService
from tests.conftest import LogCapture

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(
        os.environ.get("CI_SKIP_PERF", "") not in ("", "0"), reason="CI_SKIP_PERF set"
    ),
]

BUDGET_MS = 100.0
ITERATIONS = 50


def p95_ms(operation: Callable[[int], object]) -> float:
    timings = []
    for i in range(ITERATIONS):
        started = time.perf_counter()
        operation(i)
        timings.append((time.perf_counter() - started) * 1000)
    return statistics.quantiles(timings, n=20)[-1]


def test_operations_stay_under_budget_at_1000_runs(tmp_path: Path) -> None:
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    seeded = [
        Run(
            id=f"seed-{i:04d}",
            name=f"run {i}",
            model_type="mlp",
            hyperparameters={"lr": 0.001 * (i % 10 + 1), "layers": i % 5 + 1},
            time_budget_minutes=60 if i % 3 else None,
            started_at=start + timedelta(minutes=i),
        )
        for i in range(1000)
    ]
    repository = RunRepository(tmp_path / "runs.json", LogCapture().logger)
    repository.save_all(seeded)
    service = RunService(repository, seeded)

    created: list[str] = []
    results = {
        "create": p95_ms(
            lambda i: created.append(
                service.create(name=f"n{i}", model_type="m").run.id
            )
        ),
        "list": p95_ms(lambda i: service.list_runs()),
        "finish": p95_ms(lambda i: service.finish(created[i], {"auc": 0.5})),
        "delete": p95_ms(lambda i: service.delete(created[i])),
    }
    slow = {name: round(ms, 1) for name, ms in results.items() if ms >= BUDGET_MS}
    assert not slow, f"p95 over {BUDGET_MS} ms: {slow}"
