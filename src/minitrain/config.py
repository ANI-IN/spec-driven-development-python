"""Training configuration."""

from __future__ import annotations

from dataclasses import dataclass


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
        if not self.learning_rate > 0:
            raise ConfigError(f"learning_rate must be > 0, got {self.learning_rate}")
        if self.max_epochs < 1:
            raise ConfigError(f"max_epochs must be >= 1, got {self.max_epochs}")
        if self.batch_size < 1:
            raise ConfigError(f"batch_size must be >= 1, got {self.batch_size}")
