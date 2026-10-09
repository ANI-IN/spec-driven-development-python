"""Typed error hierarchy (constitution principle III).

Every error the application raises on purpose derives from ``AppError``.
Callers branch on the class, never on the message text.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FieldError:
    """One invalid input field: where it is and what is wrong with it."""

    field: str
    message: str


class AppError(Exception):
    """Base class for every deliberate application error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(AppError):
    """Input broke a rule. ``details`` lists every offending field."""

    def __init__(self, message: str, details: list[FieldError] | None = None) -> None:
        super().__init__(message)
        self.details: list[FieldError] = details or []


class NotFoundError(AppError):
    """No run has the requested identifier."""


class RunAlreadyFinishedError(AppError):
    """The run already has final metrics; they cannot be replaced."""


class InvalidRecordError(AppError):
    """A stored record breaks the data model; the store counts as corrupt."""


class StoreCorruptError(AppError):
    """The store file could not be read or parsed and was quarantined."""

    def __init__(self, message: str, quarantined_path: Path) -> None:
        super().__init__(message)
        self.quarantined_path = quarantined_path


class StoreUnreadableError(AppError):
    """The store exists but cannot be read (permissions, or not a file).

    Unlike corruption, nothing is renamed: fixing access is enough.
    """

    def __init__(self, message: str, store_path: Path) -> None:
        super().__init__(message)
        self.store_path = store_path


class StoreWriteError(AppError):
    """Persisting the store failed. The previous contents are intact."""
