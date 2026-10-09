"""The only way persisted state reaches disk (constitution principle V).

Write to a temp file in the same directory, fsync it, ``os.replace`` it over
the target, then fsync the directory so the rename itself is durable. A crash
at any point leaves the target holding either the old bytes or the new bytes.
"""

from __future__ import annotations

import contextlib
import os
import secrets
from pathlib import Path


def temp_path_for(target: Path) -> Path:
    """``<target>.tmp.<pid>.<16 hex chars>``, next to the target."""
    return target.with_name(f"{target.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")


def atomic_write_bytes(target: Path, data: bytes) -> None:
    """Replace ``target`` with ``data`` atomically and durably."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = temp_path_for(target)
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()
        raise
    fsync_directory(target.parent)


def fsync_directory(directory: Path) -> None:
    """Persist a rename in ``directory``. Windows cannot open directories."""
    if os.name == "nt":
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
