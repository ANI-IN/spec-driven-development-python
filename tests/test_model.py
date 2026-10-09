import numpy as np
import pytest

from minitrain.data import Dataset
from minitrain.model import LogisticRegression, Params


def test_new_model_predicts_one_half(dataset: Dataset) -> None:
    model = LogisticRegression(dataset.n_features)
    np.testing.assert_allclose(model.predict_proba(dataset.x_val), 0.5)
    assert model.loss(dataset.x_val, dataset.y_val) == pytest.approx(np.log(2))


def test_gradients_match_finite_differences(dataset: Dataset) -> None:
    rng = np.random.default_rng(0)
    model = LogisticRegression(dataset.n_features)
    model.weights = rng.normal(scale=0.1, size=dataset.n_features)
    model.bias = 0.2
    x, y = dataset.x_train, dataset.y_train
    grad_w, grad_b = model.gradients(x, y)

    eps = 1e-6
    for i in (0, 5, dataset.n_features - 1):
        original = model.weights[i]
        model.weights[i] = original + eps
        up = model.loss(x, y)
        model.weights[i] = original - eps
        down = model.loss(x, y)
        model.weights[i] = original
        assert grad_w[i] == pytest.approx((up - down) / (2 * eps), rel=1e-4, abs=1e-8)

    model.bias = 0.2 + eps
    up = model.loss(x, y)
    model.bias = 0.2 - eps
    down = model.loss(x, y)
    assert grad_b == pytest.approx((up - down) / (2 * eps), rel=1e-4, abs=1e-8)


def test_a_step_lowers_training_loss(dataset: Dataset) -> None:
    model = LogisticRegression(dataset.n_features)
    before = model.loss(dataset.x_train, dataset.y_train)
    model.step(dataset.x_train, dataset.y_train, learning_rate=0.1)
    assert model.loss(dataset.x_train, dataset.y_train) < before


def test_get_params_returns_an_independent_copy(dataset: Dataset) -> None:
    model = LogisticRegression(dataset.n_features)
    snapshot = model.get_params()
    model.step(dataset.x_train, dataset.y_train, learning_rate=0.1)
    assert np.all(snapshot.weights == 0.0)
    assert snapshot.bias == 0.0


def test_set_params_restores_a_snapshot(dataset: Dataset) -> None:
    model = LogisticRegression(dataset.n_features)
    model.step(dataset.x_train, dataset.y_train, learning_rate=0.1)
    snapshot = model.get_params()
    loss_at_snapshot = model.loss(dataset.x_val, dataset.y_val)
    for _ in range(20):
        model.step(dataset.x_train, dataset.y_train, learning_rate=0.1)
    model.set_params(snapshot)
    assert model.loss(dataset.x_val, dataset.y_val) == loss_at_snapshot


def test_set_params_rejects_the_wrong_shape() -> None:
    model = LogisticRegression(3)
    with pytest.raises(ValueError):
        model.set_params(Params(weights=np.zeros(4), bias=0.0))


def test_loss_stays_finite_for_extreme_weights(dataset: Dataset) -> None:
    model = LogisticRegression(dataset.n_features)
    model.weights = np.full(dataset.n_features, 1e6)
    assert np.isfinite(model.loss(dataset.x_val, dataset.y_val))
