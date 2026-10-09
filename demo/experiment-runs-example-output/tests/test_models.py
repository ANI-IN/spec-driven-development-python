from datetime import datetime, timedelta, timezone

import pytest

from experiment_runs.errors import InvalidRecordError
from experiment_runs.models import Run, format_timestamp, parse_timestamp

STARTED = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def finished_run() -> Run:
    return Run(
        id="5b1f2a8e-1c2d-4e3f-8a9b-0c1d2e3f4a5b",
        name="baseline",
        model_type="xgboost",
        hyperparameters={
            "max_depth": 6,
            "eta": 0.3,
            "objective": "binary",
            "gpu": False,
        },
        time_budget_minutes=30,
        status="finished",
        started_at=STARTED,
        finished_at=STARTED + timedelta(minutes=12),
        metrics={"val_auc": 0.91, "val_loss": 0.33},
    )


def test_timestamps_round_trip_in_utc() -> None:
    text = format_timestamp(STARTED)
    assert text == "2026-10-01T09:00:00.000Z"
    assert parse_timestamp(text) == STARTED


def test_parse_timestamp_rejects_naive_times() -> None:
    with pytest.raises(InvalidRecordError):
        parse_timestamp("2026-10-01T09:00:00")
    with pytest.raises(InvalidRecordError):
        parse_timestamp("yesterday")


def test_record_round_trip() -> None:
    run = finished_run()
    assert Run.from_record(run.to_record()) == run


def test_running_run_round_trip() -> None:
    run = Run(id="a", name="n", model_type="m", started_at=STARTED)
    record = run.to_record()
    assert record["status"] == "running"
    assert record["finished_at"] is None
    assert record["metrics"] is None
    assert Run.from_record(record) == run


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("status", "paused"),
        ("name", ""),
        ("hyperparameters", {"a": [1, 2]}),
        ("hyperparameters", {"lr": float("nan")}),
        ("time_budget_minutes", "30"),
        ("time_budget_minutes", True),
        ("metrics", {"auc": "high"}),
        ("metrics", None),
        ("metrics", {"auc": 10**400}),
        ("started_at", "yesterday"),
    ],
)
def test_from_record_rejects_impossible_records(key: str, value: object) -> None:
    record = finished_run().to_record()
    record[key] = value
    with pytest.raises(InvalidRecordError):
        Run.from_record(record)


def running_run_record() -> dict[str, object]:
    return Run(id="a", name="n", model_type="m", started_at=STARTED).to_record()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("metrics", {"auc": 0.5}),
        ("finished_at", "2026-10-01T10:00:00.000Z"),
        ("finished_at", ""),
    ],
)
def test_running_records_cannot_carry_results(key: str, value: object) -> None:
    record = running_run_record()
    record[key] = value
    with pytest.raises(InvalidRecordError):
        Run.from_record(record)


def test_from_record_rejects_missing_fields() -> None:
    record = finished_run().to_record()
    del record["model_type"]
    with pytest.raises(InvalidRecordError):
        Run.from_record(record)


def test_from_record_rejects_non_objects() -> None:
    with pytest.raises(InvalidRecordError):
        Run.from_record(["not", "a", "dict"])
