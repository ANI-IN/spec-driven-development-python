import numpy as np
import pytest

from minitrain.data import Dataset, make_dataset


def test_shapes_follow_the_arguments() -> None:
    data = make_dataset(n_samples=100, n_features=12, n_informative=3, val_fraction=0.3)
    assert data.x_train.shape == (70, 12)
    assert data.x_val.shape == (30, 12)
    assert data.y_train.shape == (70,)
    assert data.y_val.shape == (30,)
    assert data.n_features == 12


def test_labels_are_binary(dataset: Dataset) -> None:
    labels = np.concatenate([dataset.y_train, dataset.y_val])
    assert set(np.unique(labels)) <= {0.0, 1.0}


def test_same_seed_gives_identical_data() -> None:
    a, b = make_dataset(seed=3), make_dataset(seed=3)
    np.testing.assert_array_equal(a.x_train, b.x_train)
    np.testing.assert_array_equal(a.y_val, b.y_val)


def test_different_seeds_give_different_data() -> None:
    a, b = make_dataset(seed=1), make_dataset(seed=2)
    assert not np.array_equal(a.x_train, b.x_train)


def test_train_and_validation_rows_do_not_overlap(dataset: Dataset) -> None:
    train_rows = {row.tobytes() for row in dataset.x_train}
    val_rows = {row.tobytes() for row in dataset.x_val}
    assert train_rows.isdisjoint(val_rows)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_informative": 0},
        {"n_informative": 50, "n_features": 10},
        {"val_fraction": 0.0},
        {"val_fraction": 1.0},
        {"label_noise": 0.5},
    ],
)
def test_invalid_arguments_are_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        make_dataset(**kwargs)  # type: ignore[arg-type]
