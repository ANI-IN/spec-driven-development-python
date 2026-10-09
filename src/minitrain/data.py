"""Synthetic dataset for a binary classifier.

The data is deliberately small and wide: few training rows, many features, and
only a handful of those features carry signal. A model trained on it without
any regularization memorizes the training rows, which is exactly the situation
early stopping exists for.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Dataset:
    """Train and validation splits. Labels are 0.0 or 1.0."""

    x_train: FloatArray
    y_train: FloatArray
    x_val: FloatArray
    y_val: FloatArray

    @property
    def n_features(self) -> int:
        return int(self.x_train.shape[1])


def make_dataset(
    n_samples: int = 240,
    n_features: int = 40,
    n_informative: int = 10,
    val_fraction: float = 0.5,
    label_noise: float = 0.05,
    seed: int = 0,
) -> Dataset:
    """Generate a reproducible train/validation split.

    The same arguments always produce identical arrays.
    """
    if not 0 < n_informative <= n_features:
        raise ValueError("n_informative must be between 1 and n_features")
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be strictly between 0 and 1")
    if not 0 <= label_noise < 0.5:
        raise ValueError("label_noise must be in [0, 0.5)")

    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n_samples, n_features))
    true_weights = np.zeros(n_features)
    true_weights[:n_informative] = rng.normal(loc=0.0, scale=2.0, size=n_informative)
    logits = x @ true_weights
    y = (logits > 0).astype(np.float64)

    flip = rng.random(n_samples) < label_noise
    y[flip] = 1.0 - y[flip]

    order = rng.permutation(n_samples)
    n_val = int(round(n_samples * val_fraction))
    if not 0 < n_val < n_samples:
        raise ValueError(
            f"n_samples={n_samples} and val_fraction={val_fraction} leave a split empty"
        )
    val_idx, train_idx = order[:n_val], order[n_val:]
    return Dataset(
        x_train=x[train_idx],
        y_train=y[train_idx],
        x_val=x[val_idx],
        y_val=y[val_idx],
    )
