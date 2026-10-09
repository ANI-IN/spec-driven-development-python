"""Startup and shutdown behavior (FR-013, FR-018) and the exit codes."""

from __future__ import annotations

import json
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
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


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="needs POSIX permissions"
)
def test_main_exits_4_on_an_unreadable_store_and_leaves_it_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = tmp_path / "locked" / "runs.json"
    store.parent.mkdir()
    store.write_text("{}")
    store.chmod(0o000)
    try:
        assert main({"STORE_PATH": str(store)}) == 4
    finally:
        store.chmod(0o644)
    failed = stdout_events(capsys)[-1]
    assert failed["event"] == "server.start_failed"
    assert failed["reason"] == "store_unreadable"
    assert store.read_text() == "{}"
    assert [p.name for p in store.parent.iterdir()] == ["runs.json"]


# Real processes ----------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


class Server:
    """A real server process whose stdout events are read on a thread."""

    def __init__(self, store: Path, port: int) -> None:
        env = {**os.environ, "PORT": str(port), "STORE_PATH": str(store)}
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "experiment_runs"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.events: queue.Queue[Event | None] = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.events.put(json.loads(line))
        self.events.put(None)

    def wait_for(self, name: str, timeout: float = 15) -> Event | None:
        """The first event called ``name``, or None if the output ended first."""
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                event = self.events.get(timeout=remaining)
            except queue.Empty:
                break
            if event is None:
                return None
            if event["event"] == name:
                return event
        raise AssertionError(f"{name} was not logged within {timeout}s")

    def remaining_events(self) -> list[str]:
        self._reader.join(timeout=15)
        names: list[str] = []
        while not self.events.empty():
            event = self.events.get()
            if event is not None:
                names.append(str(event["event"]))
        return names

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=15)
        self._reader.join(timeout=15)
        assert self.proc.stdout is not None
        self.proc.stdout.close()


def started_server(store: Path) -> Server:
    """Start a server on a free port, retrying if another process took it."""
    for _ in range(3):
        server = Server(store, free_port())
        if server.wait_for("server.started") is not None:
            return server
        server.close()
    raise AssertionError("server never started")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals only")
@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_signals_shut_down_cleanly(tmp_path: Path, signum: signal.Signals) -> None:
    server = started_server(tmp_path / "r.json")
    try:
        server.proc.send_signal(signum)
        assert server.proc.wait(timeout=15) == 0
        assert server.remaining_events()[-1:] == ["server.stopped"]
    finally:
        server.close()


def test_port_in_use_exits_3_without_claiming_to_have_started(
    tmp_path: Path,
) -> None:
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        server = Server(tmp_path / "r.json", blocker.getsockname()[1])
        try:
            assert server.proc.wait(timeout=30) == 3
            events = server.remaining_events()
        finally:
            server.close()
    assert "server.started" not in events
    assert events[-1] == "server.start_failed"
