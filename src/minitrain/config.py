"""Training configuration."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import numpy as np


class ConfigError(ValueError):
    """Raised when a configuration value is out of range."""


@dataclass(frozen=True)
class TrainingConfig:
    """Hyperparameters for one training run.

    The defaults are tuned so that the bundled dataset overfits: validation
    loss bottoms out early and then climbs for the rest of the run.
    """

    learning_rate: float = 0.05
    max_epochs: int = 300
    batch_size: int = 16
    seed: int = 7

    def __post_init__(self) -> None:
        rate = self.learning_rate
        if isinstance(rate, bool) or not isinstance(rate, numbers.Real):
            raise ConfigError(f"learning_rate must be a number, got {rate!r}")
        if not math.isfinite(rate) or rate <= 0:
            raise ConfigError(f"learning_rate must be finite and > 0, got {rate}")
        object.__setattr__(self, "learning_rate", float(rate))
        for name, minimum in (("max_epochs", 1), ("batch_size", 1), ("seed", 0)):
            value = getattr(self, name)
            if not _is_integer(value):
                raise ConfigError(f"{name} must be an integer, got {value!r}")
            if value < minimum:
                raise ConfigError(f"{name} must be >= {minimum}, got {value}")
            object.__setattr__(self, name, int(value))


def _is_integer(value: object) -> bool:
    """Python and NumPy integers, but not booleans."""
    return isinstance(value, numbers.Integral) and not isinstance(
        value, bool | np.bool_
    )
