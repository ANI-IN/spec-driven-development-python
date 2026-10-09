"""FR-011 and SC-002: a crash at any point leaves old bytes or new bytes."""

from __future__ import annotations

import json
import os
import random
import re
import stat
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


REAL_CLOSE = os.close


def install_crash(patch: pytest.MonkeyPatch, point: str) -> None:
    """Make the step ``point`` of an atomic write fail like a crash.

    ``close`` closes the descriptor first, so the test does not leak it.
    """

    def crash(*args: object, **kwargs: object) -> None:
        raise SimulatedCrash(point)

    def close_then_crash(fd: int) -> None:
        REAL_CLOSE(fd)
        raise SimulatedCrash(point)

    if point == "flush":
        patch.setattr(atomic_write, "flush_to_disk", crash)
    elif point == "close":
        patch.setattr(os, "close", close_then_crash)
    else:
        patch.setattr(os, point, crash)


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


def test_temp_file_is_flushed_before_the_rename_and_dir_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real_flush, real_replace = atomic_write.flush_to_disk, os.replace
    real_dir_sync = atomic_write.fsync_directory

    def spy_flush(fd: int) -> None:
        calls.append("flush-file")
        real_flush(fd)

    def spy_replace(src: str | Path, dst: str | Path) -> None:
        calls.append("replace")
        real_replace(src, dst)

    def spy_dir_sync(directory: Path) -> None:
        calls.append("fsync-dir")
        real_dir_sync(directory)

    (tmp_path / "store.json").write_bytes(b"old")  # directory already exists
    monkeypatch.setattr(atomic_write, "flush_to_disk", spy_flush)
    monkeypatch.setattr(os, "replace", spy_replace)
    monkeypatch.setattr(atomic_write, "fsync_directory", spy_dir_sync)
    assert atomic_write_bytes(tmp_path / "store.json", b"data") is True
    assert calls == ["flush-file", "replace", "fsync-dir"]


def test_flush_uses_full_fsync_on_macos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform != "darwin":
        pytest.skip("F_FULLFSYNC exists only on macOS")
    import fcntl

    seen: list[int] = []
    real_fcntl = fcntl.fcntl

    def spy(fd: int, cmd: int, *args: int) -> object:
        seen.append(cmd)
        return real_fcntl(fd, cmd, *args)

    monkeypatch.setattr(fcntl, "fcntl", spy)
    atomic_write_bytes(tmp_path / "store.json", b"x")
    assert fcntl.F_FULLFSYNC in seen


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_an_existing_store_keeps_its_permissions(tmp_path: Path) -> None:
    target = tmp_path / "store.json"
    atomic_write_bytes(target, b"old")
    target.chmod(0o600)
    atomic_write_bytes(target, b"new")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_a_failed_directory_fsync_after_the_rename_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(directory: Path) -> None:
        raise OSError("fsync not supported")

    target = tmp_path / "store.json"
    target.write_bytes(b"old")
    monkeypatch.setattr(atomic_write, "fsync_directory", fail)
    assert atomic_write_bytes(target, b"new") is False
    assert target.read_bytes() == b"new"


def test_a_new_directory_is_made_durable_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[Path] = []
    real = atomic_write.fsync_directory

    def spy(directory: Path) -> None:
        synced.append(directory)
        real(directory)

    monkeypatch.setattr(atomic_write, "fsync_directory", spy)
    atomic_write_bytes(tmp_path / "a" / "b" / "store.json", b"{}")
    # Each new directory's parent first (top-down), then the rename.
    assert synced == [tmp_path, tmp_path / "a", tmp_path / "a" / "b"]


@pytest.mark.parametrize("crash_point", ["open", "write", "flush", "close", "replace"])
def test_crash_before_rename_leaves_target_unchanged_and_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crash_point: str
) -> None:
    target = tmp_path / "store.json"
    atomic_write_bytes(target, b"old")

    # Patch only around the call: os functions are replaced process-wide.
    with monkeypatch.context() as patch, pytest.raises(SimulatedCrash):
        install_crash(patch, crash_point)
        atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"old"
    assert leftovers(tmp_path) == []


def test_fifty_simulated_crashes_never_corrupt_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crash at a random syscall boundary 50 times; the old store survives."""
    target = tmp_path / "store.json"
    atomic_write_bytes(target, json.dumps({"version": 0}).encode())
    rng = random.Random(1234)
    points = ["open", "write", "flush", "close", "replace"]

    for i in range(1, 51):
        before = target.read_bytes()
        point = rng.choice(points)
        new = json.dumps({"version": i, "pad": "x" * rng.randint(0, 5000)})

        with monkeypatch.context() as patch, pytest.raises(SimulatedCrash):
            install_crash(patch, point)
            atomic_write_bytes(target, new.encode())
        assert target.read_bytes() == before
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
    for _ in range(25):
        proc = subprocess.Popen(
            [sys.executable, "-c", writer], stdout=subprocess.PIPE, text=True
        )
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "ready"
        try:
            proc.wait(timeout=rng.uniform(0.01, 0.15))
        except subprocess.TimeoutExpired:
            proc.kill()  # SIGKILL on POSIX
        proc.wait()
        proc.stdout.close()
        document = json.loads(target.read_bytes())
        assert set(document) == {"n", "pad"}
