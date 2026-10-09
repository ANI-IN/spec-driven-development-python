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
