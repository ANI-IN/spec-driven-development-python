"""Early stopping with best-model restore (see spec.md at the repo root).

``EarlyStopping`` holds the settings. ``EarlyStoppingMonitor`` is the
per-run state machine that the training loop feeds one validation loss per
epoch. It knows nothing about models or logging, so every rule in the spec can
be tested with plain numbers.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from typing import Literal

import numpy as np

from minitrain.config import ConfigError

StopReason = Literal["max_epochs", "patience_exhausted", "non_finite_metric"]


@dataclass(frozen=True)
class EarlyStopping:
    """Settings for early stopping on validation loss (lower is better).

    patience:          epochs without a significant improvement before stopping.
    min_delta:         a value counts as a significant improvement only if it
                       is more than ``min_delta`` (absolute) below the value at
                       the last significant improvement.
    start_from_epoch:  epochs 1..start_from_epoch never advance the patience
                       counter, so a run cannot stop *for patience* while
                       warming up. A non-finite value still stops it at once,
                       and warm-up epochs can still be the best epoch.
    restore_best:      at the end of training, load the weights from the
                       epoch with the lowest finite validation loss.
    """

    patience: int = 10
    min_delta: float = 1e-3
    start_from_epoch: int = 0
    restore_best: bool = True

    def __post_init__(self) -> None:
        if not _is_int(self.patience) or self.patience < 1:
            raise ConfigError(
                f"patience must be an integer >= 1, got {self.patience!r}"
            )
        if (
            _is_bool(self.min_delta)
            or not isinstance(self.min_delta, numbers.Real)
            or not math.isfinite(self.min_delta)
            or self.min_delta < 0
        ):
            raise ConfigError(
                f"min_delta must be a finite number >= 0, got {self.min_delta!r}"
            )
        if not _is_int(self.start_from_epoch) or self.start_from_epoch < 0:
            raise ConfigError(
                "start_from_epoch must be an integer >= 0, "
                f"got {self.start_from_epoch!r}"
            )
        if not _is_bool(self.restore_best):
            raise ConfigError(f"restore_best must be a bool, got {self.restore_best!r}")
        # Store plain Python values, whatever numeric types the caller used.
        object.__setattr__(self, "patience", int(self.patience))
        object.__setattr__(self, "min_delta", float(self.min_delta))
        object.__setattr__(self, "start_from_epoch", int(self.start_from_epoch))
        object.__setattr__(self, "restore_best", bool(self.restore_best))


def _is_bool(value: object) -> bool:
    return isinstance(value, bool | np.bool_)


def _is_int(value: object) -> bool:
    """Python and NumPy integers, but not booleans."""
    return isinstance(value, numbers.Integral) and not _is_bool(value)


@dataclass(frozen=True)
class Decision:
    """What the monitor concluded after one epoch."""

    is_best: bool
    stop: bool
    reason: StopReason | None = None


class EarlyStoppingMonitor:
    """Tracks the best epoch and the patience counter for one run."""

    def __init__(self, settings: EarlyStopping) -> None:
        self.settings = settings
        self.best_epoch: int | None = None
        self.best_value: float | None = None
        self._reference: float | None = None  # last *significant* improvement
        self.epochs_without_improvement = 0

    def update(self, epoch: int, value: float) -> Decision:
        if not math.isfinite(value):
            return Decision(is_best=False, stop=True, reason="non_finite_metric")

        is_best = self.best_value is None or value < self.best_value
        if is_best:
            self.best_epoch, self.best_value = epoch, value

        significant = (
            self._reference is None or value < self._reference - self.settings.min_delta
        )
        if significant:
            self._reference = value
            self.epochs_without_improvement = 0
        elif epoch > self.settings.start_from_epoch:
            self.epochs_without_improvement += 1

        if self.epochs_without_improvement >= self.settings.patience:
            return Decision(is_best=is_best, stop=True, reason="patience_exhausted")
        return Decision(is_best=is_best, stop=False)
