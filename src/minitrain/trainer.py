"""Mini-batch gradient-descent training loop.

Without early stopping the loop trains for ``config.max_epochs`` epochs and
leaves the model as it is after the last epoch, exactly as before. Pass
``early_stopping=EarlyStopping()`` to stop once validation loss stops
improving and get back the best model seen (see ``spec.md``).
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field

import numpy as np

from minitrain.config import TrainingConfig
from minitrain.data import Dataset
from minitrain.early_stopping import EarlyStopping, EarlyStoppingMonitor, StopReason
from minitrain.logging_utils import get_logger, log_event
from minitrain.model import LogisticRegression, Params


@dataclass(frozen=True)
class EpochMetrics:
    """Metrics recorded at the end of one epoch (epochs are numbered from 1)."""

    epoch: int
    train_loss: float
    val_loss: float
    val_accuracy: float


@dataclass(frozen=True)
class TrainingResult:
    """What a training run produced.

    ``best_epoch`` and ``best_val_loss`` describe the epoch with the lowest
    finite validation loss (earliest on ties), or ``None`` if there was none.
    ``restored_best`` says whether the model now holds that epoch's weights.
    """

    run_id: str
    epochs_run: int
    history: list[EpochMetrics] = field(default_factory=list)
    stop_reason: StopReason = "max_epochs"
    best_epoch: int | None = None
    best_val_loss: float | None = None
    restored_best: bool = False

    @property
    def final_val_loss(self) -> float:
        return self.history[-1].val_loss


def train(
    model: LogisticRegression,
    dataset: Dataset,
    config: TrainingConfig,
    *,
    early_stopping: EarlyStopping | None = None,
    run_id: str | None = None,
    logger: logging.Logger | None = None,
) -> TrainingResult:
    """Train ``model`` in place on ``dataset`` and return the run's history.

    Training is deterministic: the same model, dataset, config, and
    early-stopping settings always give the same history.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    logger = logger or get_logger()
    rng = np.random.default_rng(config.seed)
    n_train = len(dataset.y_train)
    history: list[EpochMetrics] = []
    monitor = EarlyStoppingMonitor(early_stopping) if early_stopping else None
    best_params: Params | None = None
    stop_reason: StopReason = "max_epochs"

    log_event(
        logger,
        "training_started",
        run_id=run_id,
        max_epochs=config.max_epochs,
        learning_rate=config.learning_rate,
        batch_size=config.batch_size,
        n_train=n_train,
        n_val=len(dataset.y_val),
        early_stopping=early_stopping is not None,
    )

    for epoch in range(1, config.max_epochs + 1):
        order = rng.permutation(n_train)
        for start in range(0, n_train, config.batch_size):
            batch = order[start : start + config.batch_size]
            model.step(
                dataset.x_train[batch], dataset.y_train[batch], config.learning_rate
            )

        metrics = EpochMetrics(
            epoch=epoch,
            train_loss=model.loss(dataset.x_train, dataset.y_train),
            val_loss=model.loss(dataset.x_val, dataset.y_val),
            val_accuracy=model.accuracy(dataset.x_val, dataset.y_val),
        )
        history.append(metrics)
        log_event(
            logger,
            "epoch_end",
            level=logging.DEBUG,
            run_id=run_id,
            epoch=epoch,
            train_loss=round(metrics.train_loss, 6),
            val_loss=round(metrics.val_loss, 6),
            val_accuracy=round(metrics.val_accuracy, 6),
        )

        if monitor is None or early_stopping is None:
            continue
        decision = monitor.update(epoch, metrics.val_loss)
        if decision.is_best and early_stopping.restore_best:
            best_params = model.get_params()
        if decision.stop and decision.reason is not None:
            stop_reason = decision.reason
            log_event(
                logger,
                "early_stopping_triggered",
                run_id=run_id,
                epoch=epoch,
                reason=stop_reason,
                best_epoch=monitor.best_epoch,
                best_val_loss=_rounded(monitor.best_value),
            )
            break

    restored = False
    if best_params is not None and monitor is not None:
        model.set_params(best_params)
        restored = True
        log_event(
            logger,
            "best_weights_restored",
            run_id=run_id,
            best_epoch=monitor.best_epoch,
            best_val_loss=_rounded(monitor.best_value),
        )

    best = _best_epoch(history)
    result = TrainingResult(
        run_id=run_id,
        epochs_run=len(history),
        history=history,
        stop_reason=stop_reason,
        best_epoch=best.epoch if best else None,
        best_val_loss=best.val_loss if best else None,
        restored_best=restored,
    )
    log_event(
        logger,
        "training_finished",
        run_id=run_id,
        epochs_run=result.epochs_run,
        stop_reason=result.stop_reason,
        final_val_loss=_rounded(result.final_val_loss),
        best_epoch=result.best_epoch,
        restored_best=result.restored_best,
    )
    return result


def _best_epoch(history: list[EpochMetrics]) -> EpochMetrics | None:
    """The epoch with the lowest finite validation loss; earliest on ties."""
    finite = [m for m in history if math.isfinite(m.val_loss)]
    return min(finite, key=lambda m: m.val_loss) if finite else None


def _rounded(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return value
    return round(value, 6)
