"""minitrain: a tiny NumPy training library for a binary classifier."""

from minitrain.config import ConfigError, TrainingConfig
from minitrain.data import Dataset, make_dataset
from minitrain.early_stopping import EarlyStopping, EarlyStoppingMonitor, StopReason
from minitrain.model import LogisticRegression, Params
from minitrain.trainer import EpochMetrics, TrainingResult, train

__all__ = [
    "ConfigError",
    "Dataset",
    "EarlyStopping",
    "EarlyStoppingMonitor",
    "EpochMetrics",
    "LogisticRegression",
    "Params",
    "StopReason",
    "TrainingConfig",
    "TrainingResult",
    "make_dataset",
    "train",
]
