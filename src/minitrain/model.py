"""Logistic-regression classifier trained with gradient descent."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from minitrain.data import FloatArray

_EPS = 1e-12


@dataclass(frozen=True)
class Params:
    """A snapshot of the model's learnable parameters."""

    weights: FloatArray
    bias: float


class LogisticRegression:
    """Binary classifier: ``p(y=1 | x) = sigmoid(x @ weights + bias)``."""

    def __init__(self, n_features: int) -> None:
        if n_features < 1:
            raise ValueError("n_features must be >= 1")
        self.weights: FloatArray = np.zeros(n_features)
        self.bias: float = 0.0

    def predict_proba(self, x: FloatArray) -> FloatArray:
        logits = x @ self.weights + self.bias
        # Clip so np.exp cannot overflow; probabilities stay well defined.
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -500.0, 500.0)))

    def predict(self, x: FloatArray) -> FloatArray:
        return (self.predict_proba(x) >= 0.5).astype(np.float64)

    def loss(self, x: FloatArray, y: FloatArray) -> float:
        """Mean binary cross-entropy (log loss)."""
        p = np.clip(self.predict_proba(x), _EPS, 1.0 - _EPS)
        return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))

    def accuracy(self, x: FloatArray, y: FloatArray) -> float:
        return float(np.mean(self.predict(x) == y))

    def gradients(self, x: FloatArray, y: FloatArray) -> tuple[FloatArray, float]:
        """Gradient of :meth:`loss` with respect to weights and bias."""
        error = self.predict_proba(x) - y
        grad_w = x.T @ error / len(y)
        grad_b = float(np.mean(error))
        return grad_w, grad_b

    def step(self, x: FloatArray, y: FloatArray, learning_rate: float) -> None:
        """Apply one gradient-descent update on a batch."""
        grad_w, grad_b = self.gradients(x, y)
        self.weights = self.weights - learning_rate * grad_w
        self.bias = self.bias - learning_rate * grad_b

    def get_params(self) -> Params:
        """Return a copy of the parameters, safe to keep after further training."""
        return Params(weights=self.weights.copy(), bias=self.bias)

    def set_params(self, params: Params) -> None:
        """Replace the parameters with a copy of ``params``."""
        if params.weights.shape != self.weights.shape:
            raise ValueError(
                f"expected weights of shape {self.weights.shape}, "
                f"got {params.weights.shape}"
            )
        self.weights = params.weights.copy()
        self.bias = params.bias
