"""Domain rules: User Stories 1, 3 and 4 at the service level."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from experiment_runs.errors import (
    NotFoundError,
    RunAlreadyFinishedError,
    StoreWriteError,
    ValidationError,
)
from experiment_runs.repository import RunRepository
from experiment_runs.service import RunService, is_stalled
from tests.conftest import START, FakeClock, LogCapture

UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)


def names(service: RunService) -> list[str]:
    return [view.run.name for view in service.list_runs()]


# User Story 1: log and list runs ---------------------------------------------


def test_create_returns_a_running_run(service: RunService) -> None:
    view = service.create(
        name="baseline",
        model_type="xgboost",
        hyperparameters={"max_depth": 6, "eta": 0.3},
        time_budget_minutes=30,
    )
    run = view.run
    assert UUID4.fullmatch(run.id)
    assert run.status == "running"
    assert run.started_at == START
    assert run.finished_at is None
    assert run.metrics is None
    assert run.hyperparameters == {"max_depth": 6, "eta": 0.3}
    assert view.stalled is False


def test_names_are_trimmed(service: RunService) -> None:
    run = service.create(name="  baseline  ", model_type=" mlp ").run
    assert (run.name, run.model_type) == ("baseline", "mlp")


def test_identifiers_are_unique(service: RunService) -> None:
    created = {service.create(name=f"r{i}", model_type="m").run.id for i in range(20)}
    assert len(created) == 20


def test_list_returns_every_run(service: RunService) -> None:
    for name in ("a", "b", "c"):
        service.create(name=name, model_type="m")
    assert sorted(names(service)) == ["a", "b", "c"]


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"name": "   "}, "name"),
        ({"name": ""}, "name"),
        ({"name": "x" * 201}, "name"),
        ({"model_type": "\t"}, "model_type"),
        ({"hyperparameters": {"lr": math.nan}}, "hyperparameters.lr"),
        ({"hyperparameters": {"lr": math.inf}}, "hyperparameters.lr"),
        ({"hyperparameters": {" ": 1}}, "hyperparameters"),
        ({"hyperparameters": {f"k{i}": i for i in range(51)}}, "hyperparameters"),
        ({"time_budget_minutes": 0}, "time_budget_minutes"),
        ({"time_budget_minutes": 10_081}, "time_budget_minutes"),
    ],
)
def test_invalid_input_is_rejected_and_nothing_is_stored(
    service: RunService, store_path: Path, kwargs: dict[str, object], field: str
) -> None:
    args: dict[str, object] = {"name": "ok", "model_type": "m", **kwargs}
    with pytest.raises(ValidationError) as caught:
        service.create(**args)  # type: ignore[arg-type]
    assert field in [d.field for d in caught.value.details]
    assert service.list_runs() == []
    assert not store_path.exists()


def test_every_invalid_field_is_reported_at_once(service: RunService) -> None:
    with pytest.raises(ValidationError) as caught:
        service.create(name=" ", model_type="", time_budget_minutes=0)
    fields = {d.field for d in caught.value.details}
    assert fields == {"name", "model_type", "time_budget_minutes"}


# User Story 3: finish and delete ---------------------------------------------


def test_finish_records_metrics_and_time(service: RunService, clock: FakeClock) -> None:
    run_id = service.create(name="r", model_type="m").run.id
    clock.advance(minutes=12)
    run = service.finish(run_id, {"val_auc": 0.91, "val_loss": 0.3}).run
    assert run.status == "finished"
    assert run.finished_at == clock.now
    assert run.metrics == {"val_auc": 0.91, "val_loss": 0.3}


def test_finishing_twice_is_a_conflict_and_keeps_the_first_metrics(
    service: RunService,
) -> None:
    run_id = service.create(name="r", model_type="m").run.id
    service.finish(run_id, {"val_auc": 0.91})
    with pytest.raises(RunAlreadyFinishedError):
        service.finish(run_id, {"val_auc": 0.99})
    assert service.list_runs()[0].run.metrics == {"val_auc": 0.91}


@pytest.mark.parametrize(
    "metrics",
    [
        {},
        {"auc": math.nan},
        {"auc": -math.inf},
        {"": 1.0},
        {f"m{i}": 1.0 for i in range(51)},
    ],
)
def test_invalid_metrics_are_rejected(
    service: RunService, metrics: dict[str, float]
) -> None:
    run_id = service.create(name="r", model_type="m").run.id
    with pytest.raises(ValidationError):
        service.finish(run_id, metrics)
    assert service.list_runs()[0].run.status == "running"


def test_delete_removes_the_run(service: RunService) -> None:
    keep = service.create(name="keep", model_type="m").run.id
    drop = service.create(name="drop", model_type="m").run.id
    service.delete(drop)
    assert [v.run.id for v in service.list_runs()] == [keep]


@pytest.mark.parametrize("bad_id", ["missing", "00000000-0000-4000-8000-000000000000"])
def test_unknown_ids_are_not_found_and_change_nothing(
    service: RunService, bad_id: str
) -> None:
    service.create(name="r", model_type="m")
    before = service.list_runs()
    with pytest.raises(NotFoundError):
        service.finish(bad_id, {"auc": 0.5})
    with pytest.raises(NotFoundError):
        service.delete(bad_id)
    assert service.list_runs() == before


def test_a_failed_write_changes_nothing(
    repository: RunRepository, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = RunService(repository, clock=clock)
    run_id = service.create(name="r", model_type="m").run.id

    def fail(runs: object) -> None:
        raise StoreWriteError("disk full")

    monkeypatch.setattr(repository, "save_all", fail)
    with pytest.raises(StoreWriteError):
        service.create(name="other", model_type="m")
    with pytest.raises(StoreWriteError):
        service.finish(run_id, {"auc": 0.5})
    with pytest.raises(StoreWriteError):
        service.delete(run_id)
    views = service.list_runs()
    assert [(v.run.id, v.run.status) for v in views] == [(run_id, "running")]


def test_acknowledged_changes_survive_a_restart(
    service: RunService, store_path: Path, logs: LogCapture, clock: FakeClock
) -> None:
    a = service.create(name="a", model_type="m").run.id
    b = service.create(name="b", model_type="m").run.id
    service.finish(a, {"auc": 0.8})
    service.delete(b)

    reloaded = RunRepository(store_path, logs.logger).load().runs
    restarted = RunService(
        RunRepository(store_path, logs.logger), reloaded, clock=clock
    )
    assert [(v.run.id, v.run.status) for v in restarted.list_runs()] == [
        (a, "finished")
    ]


# User Story 4: stalled runs at a glance --------------------------------------


def test_stalled_only_after_the_budget_is_exceeded(
    service: RunService, clock: FakeClock
) -> None:
    run = service.create(name="r", model_type="m", time_budget_minutes=60).run
    clock.advance(minutes=60)
    assert is_stalled(run, clock.now) is False  # exactly at the budget
    clock.advance(seconds=1)
    assert is_stalled(run, clock.now) is True
    assert service.list_runs()[0].stalled is True


def test_runs_without_a_budget_never_stall(
    service: RunService, clock: FakeClock
) -> None:
    service.create(name="r", model_type="m")
    clock.advance(days=30)
    assert service.list_runs()[0].stalled is False


def test_finished_runs_never_stall(service: RunService, clock: FakeClock) -> None:
    run_id = service.create(name="r", model_type="m", time_budget_minutes=1).run.id
    clock.advance(minutes=5)
    service.finish(run_id, {"auc": 0.7})
    assert service.list_runs()[0].stalled is False


def test_list_order_stalled_then_running_then_finished(
    service: RunService, clock: FakeClock
) -> None:
    # 09:00 f-old (finishes 09:20), 09:01 s-long (budget 10), 09:02 running-a,
    # 09:03 s-short (budget 5), 09:04 f-new (finishes 09:30), 09:05 running-b
    created: dict[str, str] = {}
    plan = [
        ("f-old", None),
        ("s-long", 10),
        ("running-a", None),
        ("s-short", 5),
        ("f-new", None),
        ("running-b", 240),
    ]
    for name, budget in plan:
        created[name] = service.create(
            name=name, model_type="m", time_budget_minutes=budget
        ).run.id
        clock.advance(minutes=1)
    clock.now = START.replace(minute=20)
    service.finish(created["f-old"], {"auc": 0.7})
    clock.now = START.replace(minute=30)
    service.finish(created["f-new"], {"auc": 0.8})

    views = service.list_runs()
    assert [v.run.name for v in views] == [
        "s-long",
        "s-short",
        "running-a",
        "running-b",
        "f-new",
        "f-old",
    ]
    assert [v.stalled for v in views] == [True, True, False, False, False, False]


def test_list_reads_the_clock_once(service: RunService, clock: FakeClock) -> None:
    for i in range(5):
        service.create(name=f"r{i}", model_type="m", time_budget_minutes=1)
    before = clock.calls
    service.list_runs()
    assert clock.calls == before + 1
