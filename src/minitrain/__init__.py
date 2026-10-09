"""minitrain: a tiny NumPy training library for a binary classifier."""

from minitrain.config import ConfigError, TrainingConfig
from minitrain.data import Dataset, make_dataset
from minitrain.model import LogisticRegression, Params
from minitrain.trainer import EpochMetrics, TrainingResult, train

__all__ = [
    "ConfigError",
    "Dataset",
    "EpochMetrics",
    "LogisticRegression",
    "Params",
    "TrainingConfig",
    "TrainingResult",
    "make_dataset",
    "train",
]
