"""Startup and shutdown behavior (FR-013, FR-018)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi.testclient import TestClient

from experiment_runs.errors import StoreCorruptError
from experiment_runs.main import build, main
from tests.conftest import LogCapture


def stdout_events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_build_logs_startup_with_store_state(tmp_path: Path, logs: LogCapture) -> None:
    store = tmp_path / "runs.json"
    app, settings = build({"STORE_PATH": str(store), "PORT": "8123"}, logs.logger)
    started = logs.events("server.started")[0]
    assert started["store_existed"] is False
    assert started["run_count"] == 0
    assert started["port"] == 8123
    assert settings.store_path == store

    TestClient(app).post("/runs", json={"name": "r", "model_type": "m"})
    _, _ = build({"STORE_PATH": str(store)}, logs.logger)
    restarted = logs.events("server.started")[1]
    assert restarted["store_existed"] is True
    assert restarted["run_count"] == 1


def test_build_raises_on_a_corrupt_store(tmp_path: Path, logs: LogCapture) -> None:
    store = tmp_path / "runs.json"
    store.write_text("{oops")
    with pytest.raises(StoreCorruptError):
        build({"STORE_PATH": str(store)}, logs.logger)


def test_main_exits_1_on_corrupt_store_then_starts_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = tmp_path / "runs.json"
    store.write_text("{oops")
    served: list[object] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: served.append(app))

    assert main({"STORE_PATH": str(store)}) == 1
    failed = [e for e in stdout_events(capsys) if e["event"] == "server.start_failed"]
    assert failed[0]["reason"] == "store_corrupt"
    assert Path(failed[0]["quarantined_path"]).read_text() == "{oops"
    assert served == []

    assert main({"STORE_PATH": str(store)}) == 0
    events = [e["event"] for e in stdout_events(capsys)]
    assert "server.started" in events
    assert events[-1] == "server.stopped"
    assert len(served) == 1


def test_main_exits_2_on_bad_config(capsys: pytest.CaptureFixture[str]) -> None:
    assert main({"PORT": "not-a-port"}) == 2
    failed = stdout_events(capsys)[-1]
    assert failed["event"] == "server.start_failed"
    assert failed["reason"] == "invalid_config"


def test_main_passes_host_and_port_to_uvicorn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(kw))
    main({"STORE_PATH": str(tmp_path / "r.json"), "HOST": "0.0.0.0", "PORT": "9000"})
    assert seen["host"] == "0.0.0.0"
    assert seen["port"] == 9000
