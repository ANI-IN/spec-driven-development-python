"""FR-011 and SC-002: a crash at any point leaves old bytes or new bytes."""

from __future__ import annotations

import json
import os
import random
import re
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from experiment_runs import atomic_write
from experiment_runs.atomic_write import atomic_write_bytes, temp_path_for


class SimulatedCrash(Exception):
    pass


def leftovers(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if ".tmp." in p.name]


def test_writes_new_content(tmp_path: Path) -> None:
    target = tmp_path / "store.json"
    atomic_write_bytes(target, b"hello")
    assert target.read_bytes() == b"hello"
    atomic_write_bytes(target, b"world")
    assert target.read_bytes() == b"world"
    assert leftovers(tmp_path) == []


def test_creates_missing_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "store.json"
    atomic_write_bytes(target, b"{}")
    assert target.read_bytes() == b"{}"


def test_temp_name_has_pid_and_random_suffix(tmp_path: Path) -> None:
    name = temp_path_for(tmp_path / "store.json").name
    assert re.fullmatch(rf"store\.json\.tmp\.{os.getpid()}\.[0-9a-f]{{16}}", name)
    assert temp_path_for(tmp_path / "store.json") != temp_path_for(
        tmp_path / "store.json"
    )


def test_fsyncs_the_file_and_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[int] = []
    real_fsync = os.fsync
    dir_syncs: list[Path] = []
    real_dir_sync = atomic_write.fsync_directory

    def spy_fsync(fd: int) -> None:
        synced.append(fd)
        real_fsync(fd)

    def spy_dir_sync(directory: Path) -> None:
        dir_syncs.append(directory)
        real_dir_sync(directory)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(atomic_write, "fsync_directory", spy_dir_sync)
    atomic_write_bytes(tmp_path / "store.json", b"data")
    assert len(synced) >= 1
    assert dir_syncs == [tmp_path]


@pytest.mark.parametrize("crash_point", ["write", "fsync", "replace"])
def test_crash_before_rename_leaves_target_unchanged_and_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crash_point: str
) -> None:
    target = tmp_path / "store.json"
    atomic_write_bytes(target, b"old")

    def crash(*args: object, **kwargs: object) -> None:
        raise SimulatedCrash(crash_point)

    # Patch only around the call: this replaces the function on the os module.
    with monkeypatch.context() as patch, pytest.raises(SimulatedCrash):
        patch.setattr(os, crash_point, crash)
        atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"old"
    assert leftovers(tmp_path) == []


def test_fifty_simulated_crashes_never_corrupt_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crash at a random syscall boundary 50 times; the store always parses."""
    target = tmp_path / "store.json"
    atomic_write_bytes(target, json.dumps({"version": 0}).encode())
    rng = random.Random(1234)
    points = ["write", "fsync", "replace", None]

    for i in range(1, 51):
        before = target.read_bytes()
        point = rng.choice(points)
        with monkeypatch.context() as patch:
            if point is not None:

                def crash(*args: object, **kwargs: object) -> None:
                    raise SimulatedCrash

                patch.setattr(os, point, crash)
            new = json.dumps({"version": i, "pad": "x" * rng.randint(0, 5000)})
            try:
                atomic_write_bytes(target, new.encode())
            except SimulatedCrash:
                assert target.read_bytes() == before
            else:
                assert target.read_bytes() == new.encode()
        json.loads(target.read_bytes())
        assert leftovers(tmp_path) == []


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL is POSIX only")
def test_real_sigkill_mid_write_never_leaves_a_partial_store(tmp_path: Path) -> None:
    """Kill a writer process at random moments; every read must parse."""
    target = tmp_path / "store.json"
    atomic_write_bytes(target, json.dumps({"n": 0, "pad": ""}).encode())
    writer = textwrap.dedent(
        f"""
        import json, sys
        from pathlib import Path
        from experiment_runs.atomic_write import atomic_write_bytes
        target = Path({str(target)!r})
        n = 0
        print("ready", flush=True)
        while True:
            n += 1
            data = json.dumps({{"n": n, "pad": "x" * 200_000}}).encode()
            atomic_write_bytes(target, data)
        """
    )
    rng = random.Random(99)
    for _ in range(10):
        proc = subprocess.Popen(
            [sys.executable, "-c", writer], stdout=subprocess.PIPE, text=True
        )
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "ready"
        try:
            proc.wait(timeout=rng.uniform(0.01, 0.15))
        except subprocess.TimeoutExpired:
            proc.send_signal(signal.SIGKILL)
        proc.wait()
        proc.stdout.close()
        document = json.loads(target.read_bytes())
        assert set(document) == {"n", "pad"}
