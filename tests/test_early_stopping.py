"""Acceptance tests for spec.md (early stopping with best-model restore).

Each test name starts with the acceptance criterion it proves.
"""

from __future__ import annotations

import logging
import math
from typing import cast

import numpy as np
import pytest

from minitrain.config import ConfigError, TrainingConfig
from minitrain.data import Dataset, FloatArray
from minitrain.early_stopping import EarlyStopping, EarlyStoppingMonitor
from minitrain.model import LogisticRegression
from minitrain.trainer import TrainingResult, train
from tests.conftest import ListHandler


def run_monitor(values: list[float], settings: EarlyStopping) -> tuple[int, str]:
    """Feed values until the monitor says stop; return (epoch, reason)."""
    monitor = EarlyStoppingMonitor(settings)
    for epoch, value in enumerate(values, start=1):
        decision = monitor.update(epoch, value)
        if decision.stop:
            assert decision.reason is not None
            return epoch, decision.reason
    return len(values), "max_epochs"


class ScriptedValLoss(LogisticRegression):
    """A real model whose *validation* loss follows a script, epoch by epoch.

    ``train()`` computes the training loss and then the validation loss once
    per epoch, so every second ``loss`` call is a validation call.
    """

    def __init__(self, n_features: int, val_losses: list[float]) -> None:
        super().__init__(n_features)
        self.val_losses = val_losses
        self.calls = 0

    def loss(self, x: FloatArray, y: FloatArray) -> float:
        self.calls += 1
        if self.calls % 2 == 0:
            return self.val_losses[self.calls // 2 - 1]
        return super().loss(x, y)


def scripted_run(
    dataset: Dataset,
    logger: logging.Logger,
    val_losses: list[float],
    settings: EarlyStopping,
) -> tuple[ScriptedValLoss, TrainingResult]:
    model = ScriptedValLoss(dataset.n_features, val_losses)
    config = TrainingConfig(max_epochs=len(val_losses))
    return model, train(model, dataset, config, early_stopping=settings, logger=logger)


# AC1: stops early on the bundled dataset --------------------------------------


def test_ac1_default_settings_stop_well_before_max_epochs(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    model = LogisticRegression(dataset.n_features)
    result = train(
        model,
        dataset,
        TrainingConfig(),
        early_stopping=EarlyStopping(),
        logger=quiet_logger,
    )
    assert result.stop_reason == "patience_exhausted"
    assert result.epochs_run <= 60


# AC2: the returned model is the best one --------------------------------------


def test_ac2_restored_model_has_the_lowest_validation_loss(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    model = LogisticRegression(dataset.n_features)
    result = train(
        model,
        dataset,
        TrainingConfig(),
        early_stopping=EarlyStopping(),
        logger=quiet_logger,
    )
    lowest = min(result.history, key=lambda m: m.val_loss)
    assert result.restored_best is True
    assert result.best_epoch == lowest.epoch == 21
    assert result.best_val_loss == lowest.val_loss
    assert model.loss(dataset.x_val, dataset.y_val) == lowest.val_loss


def test_ac2_ties_resolve_to_the_earliest_epoch_in_the_monitor() -> None:
    monitor = EarlyStoppingMonitor(EarlyStopping(patience=5))
    for epoch, value in enumerate([0.5, 0.4, 0.4, 0.45], start=1):
        monitor.update(epoch, value)
    assert monitor.best_epoch == 2


def test_ac2_ties_resolve_to_the_earliest_epoch_in_the_result(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    _, result = scripted_run(
        dataset, quiet_logger, [0.5, 0.4, 0.4, 0.45, 0.46], EarlyStopping(patience=3)
    )
    assert result.best_epoch == 2


# AC3 and AC4: patience counts from the last significant improvement -----------


def test_ac3_stops_exactly_patience_epochs_after_last_significant_improvement() -> None:
    values = [1.0, 0.9, 0.8, 0.85, 0.86, 0.87]
    assert run_monitor(values, EarlyStopping(patience=3, min_delta=0.0)) == (
        6,
        "patience_exhausted",
    )


def test_ac4_improvements_within_min_delta_do_not_reset_patience() -> None:
    # 0.795 and 0.791 beat 0.80 by less than 0.01, so patience keeps counting,
    # but the best epoch still moves to the lowest value.
    monitor = EarlyStoppingMonitor(EarlyStopping(patience=3, min_delta=0.01))
    decisions = [
        monitor.update(epoch, value)
        for epoch, value in enumerate([0.80, 0.795, 0.791, 0.799], start=1)
    ]
    assert [d.stop for d in decisions] == [False, False, False, True]
    assert monitor.best_epoch == 3


def test_ac4_significance_is_measured_from_the_last_significant_improvement() -> None:
    # 0.789 is less than 0.01 below the best (0.795) but more than 0.01 below
    # the last significant improvement (0.80), so it resets the counter.
    values = [0.80, 0.795, 0.789, 0.79, 0.79]
    assert run_monitor(values, EarlyStopping(patience=2, min_delta=0.01)) == (
        5,
        "patience_exhausted",
    )


def test_ac4_an_improvement_of_exactly_min_delta_is_not_significant() -> None:
    assert run_monitor([1.0, 0.5, 0.4], EarlyStopping(patience=1, min_delta=0.5)) == (
        2,
        "patience_exhausted",
    )


def test_ac4_an_improvement_larger_than_min_delta_resets_patience() -> None:
    values = [0.80, 0.81, 0.82, 0.70, 0.71, 0.72, 0.73]
    assert run_monitor(values, EarlyStopping(patience=3, min_delta=0.01)) == (
        7,
        "patience_exhausted",
    )


# AC5: warm-up epochs never count toward patience ------------------------------


def test_ac5_cannot_stop_for_patience_during_warm_up() -> None:
    values = [1.0] + [1.1] * 9
    settings = EarlyStopping(patience=2, min_delta=0.0, start_from_epoch=5)
    # epochs 2..5 are warm-up; 6 and 7 count, so it stops at 7.
    assert run_monitor(values, settings) == (7, "patience_exhausted")


def test_ac5_a_warm_up_epoch_can_be_the_best_epoch() -> None:
    monitor = EarlyStoppingMonitor(EarlyStopping(patience=2, start_from_epoch=3))
    for epoch, value in enumerate([0.9, 0.5, 0.8, 0.8, 0.8], start=1):
        monitor.update(epoch, value)
    assert monitor.best_epoch == 2


# AC6: non-finite validation loss stops at once ------------------------------


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_ac6_non_finite_value_stops_immediately(bad: float) -> None:
    assert run_monitor([0.9, 0.8, bad, 0.7], EarlyStopping(patience=10)) == (
        3,
        "non_finite_metric",
    )


def test_ac6_warm_up_never_delays_the_non_finite_check() -> None:
    settings = EarlyStopping(patience=10, start_from_epoch=5)
    assert run_monitor([0.9, math.nan, 0.8], settings) == (2, "non_finite_metric")


def test_ac6_training_restores_the_last_finite_best_after_nan(
    dataset: Dataset, log_capture: tuple[logging.Logger, ListHandler]
) -> None:
    logger, handler = log_capture
    losses = [0.9, 0.8, 0.7, 0.75, 0.6, math.nan, 0.5]
    _, result = scripted_run(dataset, logger, losses, EarlyStopping())
    assert result.stop_reason == "non_finite_metric"
    assert result.epochs_run == 6
    assert result.best_epoch == 5
    assert result.restored_best is True
    [triggered] = handler.events("early_stopping_triggered")
    assert triggered["reason"] == "non_finite_metric"
    assert triggered["epoch"] == 6


def test_ac6_nan_at_epoch_one_leaves_no_best(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    _, result = scripted_run(dataset, quiet_logger, [math.nan, 0.5], EarlyStopping())
    assert result.stop_reason == "non_finite_metric"
    assert result.epochs_run == 1
    assert result.best_epoch is None
    assert result.best_val_loss is None
    assert result.restored_best is False


def test_ac6_with_restore_off_the_model_keeps_the_last_weights(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    model = ScriptedValLoss(dataset.n_features, [0.9, 0.5, math.nan])
    before_last_epoch = LogisticRegression(dataset.n_features)
    result = train(
        model,
        dataset,
        TrainingConfig(max_epochs=3),
        early_stopping=EarlyStopping(restore_best=False),
        logger=quiet_logger,
    )
    reference = train(
        before_last_epoch, dataset, TrainingConfig(max_epochs=3), logger=quiet_logger
    )
    assert result.restored_best is False
    assert result.epochs_run == reference.epochs_run == 3
    np.testing.assert_array_equal(model.weights, before_last_epoch.weights)


# AC7: restore can be turned off ----------------------------------------------


def test_ac7_without_restore_the_model_keeps_last_epoch_weights(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    model = LogisticRegression(dataset.n_features)
    result = train(
        model,
        dataset,
        TrainingConfig(),
        early_stopping=EarlyStopping(restore_best=False),
        logger=quiet_logger,
    )
    assert result.restored_best is False
    assert model.loss(dataset.x_val, dataset.y_val) == result.history[-1].val_loss


# AC8: invalid settings are rejected ------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"patience": 0},
        {"patience": -1},
        {"patience": 2.5},
        {"patience": True},
        {"min_delta": -0.001},
        {"min_delta": math.nan},
        {"min_delta": math.inf},
        {"min_delta": True},
        {"start_from_epoch": -1},
        {"start_from_epoch": 1.5},
        {"restore_best": "no"},
    ],
)
def test_ac8_invalid_settings_raise_config_error(kwargs: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        EarlyStopping(**kwargs)  # type: ignore[arg-type]  # deliberately bad input


def test_ac8_numpy_scalars_are_accepted_and_stored_as_python_values() -> None:
    settings = EarlyStopping(
        patience=cast(int, np.int64(5)),
        min_delta=cast(float, np.float32(0.25)),
        start_from_epoch=cast(int, np.int32(2)),
        restore_best=cast(bool, np.True_),
    )
    assert settings == EarlyStopping(5, 0.25, 2, True)
    assert type(settings.patience) is int
    assert type(settings.min_delta) is float
    assert type(settings.restore_best) is bool


# AC9: callers that do not opt in see no change -------------------------------


def test_ac9_positional_call_matches_the_numbers_before_this_change(
    dataset: Dataset,
) -> None:
    model = LogisticRegression(dataset.n_features)
    result = train(model, dataset, TrainingConfig())
    # Golden values from the version before early stopping existed.
    assert result.history[20].val_loss == pytest.approx(0.478891, abs=1e-6)
    assert result.history[-1].val_loss == pytest.approx(0.877704, abs=1e-6)
    assert float(np.sum(model.weights)) == pytest.approx(-5.811811, abs=1e-6)
    assert result.epochs_run == 300
    assert result.stop_reason == "max_epochs"
    assert result.restored_best is False


def test_ac9_best_epoch_is_reported_even_without_early_stopping(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    result = train(
        LogisticRegression(dataset.n_features),
        dataset,
        TrainingConfig(),
        logger=quiet_logger,
    )
    assert result.best_epoch == 21
    assert result.best_val_loss == pytest.approx(0.478891, abs=1e-6)


# AC10: reaching max_epochs ----------------------------------------------------


def test_ac10_patience_larger_than_max_epochs_runs_to_the_end_and_restores(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    model = LogisticRegression(dataset.n_features)
    result = train(
        model,
        dataset,
        TrainingConfig(max_epochs=40),
        early_stopping=EarlyStopping(patience=1000),
        logger=quiet_logger,
    )
    assert result.epochs_run == 40
    assert result.stop_reason == "max_epochs"
    assert result.restored_best is True
    assert model.loss(dataset.x_val, dataset.y_val) == result.best_val_loss


def test_ac10_patience_running_out_on_the_last_epoch_is_patience_exhausted(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    _, result = scripted_run(
        dataset, quiet_logger, [0.5, 0.6, 0.7], EarlyStopping(patience=2)
    )
    assert result.epochs_run == 3
    assert result.stop_reason == "patience_exhausted"


# AC11: observable in the structured logs ---------------------------------------


def test_ac11_stop_and_restore_are_logged_once_with_run_id(
    dataset: Dataset, log_capture: tuple[logging.Logger, ListHandler]
) -> None:
    logger, handler = log_capture
    model = LogisticRegression(dataset.n_features)
    result = train(
        model,
        dataset,
        TrainingConfig(),
        early_stopping=EarlyStopping(),
        run_id="r42",
        logger=logger,
    )
    [started] = handler.events("training_started")
    assert started["early_stopping"] is True

    [triggered] = handler.events("early_stopping_triggered")
    assert triggered["run_id"] == "r42"
    assert triggered["epoch"] == result.epochs_run
    assert triggered["reason"] == "patience_exhausted"
    assert triggered["best_epoch"] == result.best_epoch
    assert triggered["best_val_loss"] == pytest.approx(result.best_val_loss, abs=1e-6)

    [restored] = handler.events("best_weights_restored")
    assert restored["best_epoch"] == result.best_epoch

    [finished] = handler.events("training_finished")
    assert finished["stop_reason"] == "patience_exhausted"
    assert finished["best_epoch"] == result.best_epoch
    assert finished["restored_best"] is True


def test_ac11_nothing_extra_is_logged_without_early_stopping(
    dataset: Dataset, log_capture: tuple[logging.Logger, ListHandler]
) -> None:
    logger, handler = log_capture
    train(
        LogisticRegression(dataset.n_features),
        dataset,
        TrainingConfig(max_epochs=5),
        logger=logger,
    )
    assert handler.events("early_stopping_triggered") == []
    assert handler.events("best_weights_restored") == []
    assert handler.events("training_started")[0]["early_stopping"] is False


# AC12: deterministic ----------------------------------------------------------


def test_ac12_same_inputs_same_result(
    dataset: Dataset, quiet_logger: logging.Logger
) -> None:
    first = LogisticRegression(dataset.n_features)
    second = LogisticRegression(dataset.n_features)
    a = train(
        first,
        dataset,
        TrainingConfig(),
        early_stopping=EarlyStopping(),
        logger=quiet_logger,
    )
    b = train(
        second,
        dataset,
        TrainingConfig(),
        early_stopping=EarlyStopping(),
        logger=quiet_logger,
    )
    assert (a.epochs_run, a.best_epoch, a.history) == (
        b.epochs_run,
        b.best_epoch,
        b.history,
    )
    np.testing.assert_array_equal(first.weights, second.weights)
