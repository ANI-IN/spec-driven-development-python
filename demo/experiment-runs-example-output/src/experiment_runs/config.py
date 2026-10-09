"""Read settings from environment variables. No side effects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from experiment_runs.errors import FieldError, ValidationError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_STORE_PATH = Path("data/runs.json")


@dataclass(frozen=True)
class Settings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    store_path: Path = DEFAULT_STORE_PATH


def load_settings(env: Mapping[str, str]) -> Settings:
    """``HOST``, ``PORT`` and ``STORE_PATH``; empty values mean "use the default"."""
    host = env.get("HOST") or DEFAULT_HOST
    raw_port = env.get("PORT") or str(DEFAULT_PORT)
    if (
        not (raw_port.isascii() and raw_port.isdigit())
        or len(raw_port) > 5
        or not 1 <= int(raw_port) <= 65_535
    ):
        raise ValidationError(
            "invalid configuration",
            [FieldError("PORT", f"must be an integer 1-65535, got {raw_port!r}")],
        )
    store_path = Path(env.get("STORE_PATH") or DEFAULT_STORE_PATH)
    if store_path.is_dir():
        raise ValidationError(
            "invalid configuration",
            [
                FieldError(
                    "STORE_PATH", f"must be a file path, got a directory {store_path}"
                )
            ],
        )
    return Settings(host=host, port=int(raw_port), store_path=store_path)
