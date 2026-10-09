import logging

import numpy as np
import pytest

from minitrain.config import TrainingConfig
from minitrain.data import Dataset
from minitrain.model import LogisticRegression
from minitrain.trainer import train
from tests.conftest import ListHandler


def test_trains_for_max_epochs(dataset: Dataset, quiet_logger: logging.Logger) -> None:
    model = LogisticRegression(dataset.n_features)
    result = train(model, dataset, TrainingConfig(max_epochs=25), logger=quiet_logger)
    assert result.epochs_run == 25
    assert [m.epoch for m in result.history] == list(range(1, 26))
    assert result.final_val_loss == result.history[-1].val_loss


def test_training_is_deterministic(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    config = TrainingConfig(max_epochs=30)
    first = LogisticRegression(dataset.n_features)
    second = LogisticRegression(dataset.n_features)
    a = train(first, dataset, config, logger=quiet_logger)
    b = train(second, dataset, config, logger=quiet_logger)
    assert a.history == b.history
    np.testing.assert_array_equal(first.weights, second.weights)


def test_training_loss_goes_down(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    model = LogisticRegression(dataset.n_features)
    result = train(model, dataset, TrainingConfig(max_epochs=50), logger=quiet_logger)
    assert result.history[-1].train_loss < result.history[0].train_loss


def test_run_id_is_used_when_given(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    model = LogisticRegression(dataset.n_features)
    result = train(
        model, dataset, TrainingConfig(max_epochs=1), run_id="abc", logger=quiet_logger
    )
    assert result.run_id == "abc"


def test_logs_one_structured_line_per_epoch(
    dataset: Dataset, log_capture: tuple[logging.Logger, ListHandler]
) -> None:
    logger, handler = log_capture
    model = LogisticRegression(dataset.n_features)
    train(model, dataset, TrainingConfig(max_epochs=5), run_id="r1", logger=logger)

    assert len(handler.events("training_started")) == 1
    epochs = handler.events("epoch_end")
    assert [line["epoch"] for line in epochs] == [1, 2, 3, 4, 5]
    assert all(line["run_id"] == "r1" for line in handler.lines)
    finished = handler.events("training_finished")
    assert len(finished) == 1
    assert finished[0]["epochs_run"] == 5


def test_default_run_matches_the_numbers_in_the_lesson(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    """README and the PRD quote these values; they must not drift."""
    model = LogisticRegression(dataset.n_features)
    result = train(model, dataset, TrainingConfig(), logger=quiet_logger)
    assert result.history[20].val_loss == pytest.approx(0.478891, abs=1e-6)
    assert result.history[-1].val_loss == pytest.approx(0.877704, abs=1e-6)
    assert float(np.sum(model.weights)) == pytest.approx(-5.811811, abs=1e-6)
    assert model.bias == pytest.approx(-0.225072, abs=1e-6)


def test_default_run_overfits(dataset: Dataset, quiet_logger: logging.Logger) -> None:
    """The lesson depends on this: the best epoch is early, the last is worse."""
    model = LogisticRegression(dataset.n_features)
    result = train(model, dataset, TrainingConfig(), logger=quiet_logger)
    best = min(result.history, key=lambda m: m.val_loss)
    assert best.epoch < 60
    assert result.final_val_loss > best.val_loss * 1.5
