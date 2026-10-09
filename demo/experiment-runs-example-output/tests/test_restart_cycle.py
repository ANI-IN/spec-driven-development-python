"""SC-006: zero runs lost across 100 restart cycles of mixed writes."""

from __future__ import annotations

import random
from pathlib import Path

from experiment_runs.repository import RunRepository
from experiment_runs.service import RunService
from tests.conftest import FakeClock, LogCapture


def test_hundred_restart_cycles_lose_nothing(tmp_path: Path) -> None:
    store = tmp_path / "runs.json"
    logs = LogCapture()
    clock = FakeClock()
    rng = random.Random(7)
    expected: dict[str, tuple[str, str]] = {}

    for cycle in range(100):
        repository = RunRepository(store, logs.logger)
        service = RunService(repository, repository.load().runs, clock=clock)
        assert {
            v.run.id: (v.run.name, v.run.status) for v in service.list_runs()
        } == expected

        for _ in range(rng.randint(1, 4)):
            run = service.create(name=f"c{cycle}", model_type="m").run
            expected[run.id] = (run.name, "running")
        running = [k for k, (_, status) in expected.items() if status == "running"]
        if running and rng.random() < 0.6:
            run_id = rng.choice(running)
            service.finish(run_id, {"auc": rng.random()})
            expected[run_id] = (expected[run_id][0], "finished")
        if expected and rng.random() < 0.4:
            run_id = rng.choice(sorted(expected))
            service.delete(run_id)
            del expected[run_id]
        clock.advance(minutes=1)

    final = RunRepository(store, logs.logger).load().runs
    assert {r.id: (r.name, r.status) for r in final} == expected
