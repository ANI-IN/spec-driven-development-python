import math
from typing import cast

import numpy as np
import pytest

from minitrain.config import ConfigError, TrainingConfig


def test_defaults_are_valid() -> None:
    config = TrainingConfig()
    assert config.learning_rate > 0
    assert config.max_epochs >= 1
    assert config.batch_size >= 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"learning_rate": 0.0},
        {"learning_rate": -0.1},
        {"max_epochs": 0},
        {"batch_size": 0},
    ],
)
def test_out_of_range_values_are_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ConfigError):
        TrainingConfig(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"learning_rate": math.inf},
        {"learning_rate": math.nan},
        {"learning_rate": "0.1"},
        {"max_epochs": 2.5},
        {"max_epochs": True},
        {"batch_size": 2.5},
        {"seed": -1},
        {"seed": 1.5},
    ],
)
def test_wrong_types_and_non_finite_values_are_rejected(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ConfigError):
        TrainingConfig(**kwargs)  # type: ignore[arg-type]  # deliberately bad input


def test_numpy_integers_are_accepted() -> None:
    # cast: NumPy 1.x stubs do not treat np.int64 as int; at runtime it is one.
    config = TrainingConfig(
        max_epochs=cast(int, np.int64(5)), seed=cast(int, np.int64(3))
    )
    assert config.max_epochs == 5
    assert type(config.max_epochs) is int
