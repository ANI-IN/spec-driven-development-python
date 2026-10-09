"""Startup and shutdown behavior (FR-013, FR-018) and the exit codes."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from experiment_runs import main as main_module
from experiment_runs.errors import StoreCorruptError
from experiment_runs.logger import EventLogger
from experiment_runs.main import Startup, build, main
from tests.conftest import LogCapture

Event = dict[str, object]


def stdout_events(capsys: pytest.CaptureFixture[str]) -> list[Event]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def fake_serve(started: bool, served: list[Startup]) -> object:
    def serve(startup: Startup, logger: EventLogger) -> bool:
        served.append(startup)
        return started

    return serve


def test_build_reports_store_state(tmp_path: Path, logs: LogCapture) -> None:
    store = tmp_path / "runs.json"
    first = build({"STORE_PATH": str(store), "PORT": "8123"}, logs.logger)
    assert (first.store_existed, first.run_count) == (False, 0)
    assert first.settings.port == 8123
    assert first.settings.store_path == store

    TestClient(first.app).post("/runs", json={"name": "r", "model_type": "m"})
    second = build({"STORE_PATH": str(store)}, logs.logger)
    assert (second.store_existed, second.run_count) == (True, 1)


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
    served: list[Startup] = []
    monkeypatch.setattr(main_module, "serve", fake_serve(True, served))

    assert main({"STORE_PATH": str(store)}) == 1
    failed = [e for e in stdout_events(capsys) if e["event"] == "server.start_failed"]
    assert failed[0]["reason"] == "store_corrupt"
    assert Path(str(failed[0]["quarantined_path"])).read_text() == "{oops"
    assert served == []

    assert main({"STORE_PATH": str(store)}) == 0
    assert stdout_events(capsys)[-1]["event"] == "server.stopped"
    assert served[0].run_count == 0


def test_main_exits_2_on_bad_config(capsys: pytest.CaptureFixture[str]) -> None:
    assert main({"PORT": "not-a-port"}) == 2
    failed = stdout_events(capsys)[-1]
    assert failed["event"] == "server.start_failed"
    assert failed["reason"] == "invalid_config"


def test_main_exits_3_when_the_server_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(main_module, "serve", fake_serve(False, []))
    assert main({"STORE_PATH": str(tmp_path / "r.json")}) == 3
    events = stdout_events(capsys)
    assert events[-1]["event"] == "server.start_failed"
    assert events[-1]["reason"] == "startup_failed"
    assert "server.stopped" not in [e["event"] for e in events]


# Real processes ----------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def start_server(tmp_path: Path, port: int) -> subprocess.Popen[str]:
    env = {**os.environ, "PORT": str(port), "STORE_PATH": str(tmp_path / "r.json")}
    return subprocess.Popen(
        [sys.executable, "-m", "experiment_runs"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_for_event(proc: subprocess.Popen[str], name: str) -> Event:
    assert proc.stdout is not None
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        event: Event = json.loads(line)
        if event["event"] == name:
            return event
    raise AssertionError(f"{name} was never logged")


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM is POSIX only")
def test_sigterm_shuts_down_cleanly(tmp_path: Path) -> None:
    proc = start_server(tmp_path, free_port())
    try:
        started = wait_for_event(proc, "server.started")
        assert started["store_existed"] is False
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=15) == 0
        assert proc.stdout is not None
        remaining = [json.loads(line)["event"] for line in proc.stdout]
        assert remaining[-1] == "server.stopped"
    finally:
        proc.kill()
        proc.wait()


def test_port_in_use_exits_3_without_claiming_to_have_started(
    tmp_path: Path,
) -> None:
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        proc = start_server(tmp_path, blocker.getsockname()[1])
        try:
            out, _ = proc.communicate(timeout=30)
        finally:
            proc.kill()
    events = [json.loads(line)["event"] for line in out.splitlines()]
    assert proc.returncode == 3
    assert "server.started" not in events
    assert events[-1] == "server.start_failed"
