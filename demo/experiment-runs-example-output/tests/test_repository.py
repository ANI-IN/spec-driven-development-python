"""User Story 2: persistence survives restarts and refuses corrupt stores."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from experiment_runs import atomic_write
from experiment_runs import repository as repository_module
from experiment_runs.errors import (
    StoreCorruptError,
    StoreUnreadableError,
    StoreWriteError,
)
from experiment_runs.models import Run
from experiment_runs.repository import RunRepository
from tests.conftest import LogCapture

STARTED = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def make_run(run_id: str = "r1") -> Run:
    return Run(id=run_id, name="baseline", model_type="mlp", started_at=STARTED)


def test_missing_store_loads_empty(repository: RunRepository, logs: LogCapture) -> None:
    result = repository.load()
    assert result.runs == []
    assert result.existed is False
    assert logs.events("store.initialized")[0]["existed"] is False


def test_saved_runs_load_back(
    repository: RunRepository, store_path: Path, logs: LogCapture
) -> None:
    runs = [make_run("a"), make_run("b")]
    repository.save_all(runs)
    reloaded = RunRepository(store_path, logs.logger).load()
    assert reloaded.runs == runs
    assert reloaded.existed is True
    loaded = logs.events("store.loaded")[0]
    assert loaded["count"] == 2


def test_store_file_has_a_schema_version(
    repository: RunRepository, store_path: Path
) -> None:
    repository.save_all([make_run()])
    document = json.loads(store_path.read_text())
    assert document["schema_version"] == 1
    assert len(document["runs"]) == 1


@pytest.mark.parametrize(
    "content",
    [
        b"{not json",
        b"",
        b"\xff\xfe\x00",
        b"[]",
        b'{"schema_version": 2, "runs": []}',
        b'{"schema_version": 1, "runs": {}}',
        b'{"schema_version": 1, "runs": [{"id": "x"}]}',
        b"[" * 100_000 + b"]" * 100_000,
    ],
)
def test_corrupt_store_is_quarantined_and_raises(
    store_path: Path, logs: LogCapture, content: bytes
) -> None:
    store_path.parent.mkdir(parents=True)
    store_path.write_bytes(content)
    with pytest.raises(StoreCorruptError) as caught:
        RunRepository(store_path, logs.logger).load()

    quarantined = caught.value.quarantined_path
    assert not store_path.exists()
    assert quarantined.read_bytes() == content
    assert quarantined.name.startswith("runs.json.corrupt.")
    event = logs.events("store.quarantined")[0]
    assert event["quarantined_path"] == str(quarantined)


def test_duplicate_ids_count_as_corruption(store_path: Path, logs: LogCapture) -> None:
    store_path.parent.mkdir(parents=True)
    record = make_run("same").to_record()
    store_path.write_text(json.dumps({"schema_version": 1, "runs": [record, record]}))
    with pytest.raises(StoreCorruptError):
        RunRepository(store_path, logs.logger).load()


def test_quarantine_never_overwrites_an_earlier_one(
    store_path: Path, logs: LogCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> FrozenDatetime:
            return cls(2026, 10, 1, 9, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(repository_module, "datetime", FrozenDatetime)
    store_path.parent.mkdir(parents=True)
    paths = []
    for content in (b"first", b"second"):
        store_path.write_bytes(content)
        with pytest.raises(StoreCorruptError) as caught:
            RunRepository(store_path, logs.logger).load()
        paths.append(caught.value.quarantined_path)
    assert paths[0] != paths[1]
    assert paths[0].read_bytes() == b"first"
    assert paths[1].read_bytes() == b"second"


def test_after_quarantine_the_next_start_is_empty(
    store_path: Path, logs: LogCapture
) -> None:
    store_path.parent.mkdir(parents=True)
    store_path.write_text("garbage")
    with pytest.raises(StoreCorruptError):
        RunRepository(store_path, logs.logger).load()
    assert RunRepository(store_path, logs.logger).load().runs == []


def test_save_uses_the_atomic_write_helper(
    repository: RunRepository, monkeypatch: pytest.MonkeyPatch, logs: LogCapture
) -> None:
    calls: list[Path] = []
    real = atomic_write.atomic_write_bytes

    def spy(target: Path, data: bytes) -> None:
        calls.append(target)
        real(target, data)

    monkeypatch.setattr(repository_module, "atomic_write_bytes", spy)
    repository.save_all([make_run()])
    assert calls == [repository.store_path]
    assert logs.events("store.write")[-1]["outcome"] == "success"


def test_write_failure_raises_store_write_error_and_logs(
    repository: RunRepository, monkeypatch: pytest.MonkeyPatch, logs: LogCapture
) -> None:
    def fail(target: Path, data: bytes) -> None:
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(repository_module, "atomic_write_bytes", fail)
    with pytest.raises(StoreWriteError):
        repository.save_all([make_run()])
    event = logs.events("store.write")[-1]
    assert event["outcome"] == "PermissionError"
    assert "read-only" in event["error"]


def test_concurrent_saves_never_interleave(
    repository: RunRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    active = 0
    overlaps = 0
    guard = threading.Lock()
    real = atomic_write.atomic_write_bytes

    def slow_write(target: Path, data: bytes) -> None:
        nonlocal active, overlaps
        with guard:
            active += 1
            overlaps += active > 1
        time.sleep(0.01)
        real(target, data)
        with guard:
            active -= 1

    monkeypatch.setattr(repository_module, "atomic_write_bytes", slow_write)
    threads = [
        threading.Thread(target=repository.save_all, args=([make_run(str(i))],))
        for i in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert overlaps == 0


def test_a_write_that_is_not_confirmed_durable_is_logged(
    repository: RunRepository, monkeypatch: pytest.MonkeyPatch, logs: LogCapture
) -> None:
    monkeypatch.setattr(repository_module, "atomic_write_bytes", lambda t, d: False)
    repository.save_all([make_run()])
    assert logs.events("store.write_not_durable")[0]["count"] == 1
    assert logs.events("store.write")[-1]["outcome"] == "success"


@pytest.mark.parametrize(
    "content",
    [
        # More digits than Python will parse as an int: json raises ValueError.
        b'{"schema_version": 1, "runs": [], "x": ' + b"9" * 5000 + b"}",
    ],
)
def test_unparsable_numbers_are_quarantined(
    store_path: Path, logs: LogCapture, content: bytes
) -> None:
    store_path.parent.mkdir(parents=True)
    store_path.write_bytes(content)
    with pytest.raises(StoreCorruptError):
        RunRepository(store_path, logs.logger).load()
    assert not store_path.exists()


@pytest.mark.parametrize(
    "started_at", ["9999-12-31T23:59:59.000-05:00", "0001-01-01T00:00:00.000+05:00"]
)
def test_out_of_range_timestamps_are_quarantined(
    store_path: Path, logs: LogCapture, started_at: str
) -> None:
    record = make_run().to_record()
    record["started_at"] = started_at
    store_path.parent.mkdir(parents=True)
    store_path.write_text(json.dumps({"schema_version": 1, "runs": [record]}))
    with pytest.raises(StoreCorruptError):
        RunRepository(store_path, logs.logger).load()


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="needs POSIX permissions"
)
def test_a_store_that_cannot_be_read_or_moved_is_reported(
    store_path: Path, logs: LogCapture
) -> None:
    store_path.parent.mkdir(parents=True)
    store_path.write_text("{}")
    store_path.chmod(0o000)
    store_path.parent.chmod(0o555)
    try:
        with pytest.raises(StoreUnreadableError):
            RunRepository(store_path, logs.logger).load()
        assert logs.events("store.unreadable")
    finally:
        store_path.parent.chmod(0o755)
        store_path.chmod(0o644)


def test_a_directory_is_not_a_store(tmp_path: Path, logs: LogCapture) -> None:
    (tmp_path / "runs.json").mkdir()
    with pytest.raises(StoreUnreadableError):
        RunRepository(tmp_path / "runs.json", logs.logger).load()
    assert (tmp_path / "runs.json").is_dir()  # never renamed
