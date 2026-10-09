"""Mini-batch gradient-descent training loop.

The loop always trains for ``config.max_epochs`` epochs and returns the model
as it is after the last epoch, whatever happened to the validation loss on the
way. See ``lab/prd-early-stopping.md`` for why that is a problem.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

import numpy as np

from minitrain.config import TrainingConfig
from minitrain.data import Dataset
from minitrain.logging_utils import get_logger, log_event
from minitrain.model import LogisticRegression


@dataclass(frozen=True)
class EpochMetrics:
    """Metrics recorded at the end of one epoch (epochs are numbered from 1)."""

    epoch: int
    train_loss: float
    val_loss: float
    val_accuracy: float


@dataclass(frozen=True)
class TrainingResult:
    """What a training run produced."""

    run_id: str
    epochs_run: int
    history: list[EpochMetrics] = field(default_factory=list)

    @property
    def final_val_loss(self) -> float:
        return self.history[-1].val_loss


def train(
    model: LogisticRegression,
    dataset: Dataset,
    config: TrainingConfig,
    *,
    run_id: str | None = None,
    logger: logging.Logger | None = None,
) -> TrainingResult:
    """Train ``model`` in place on ``dataset`` and return the run's history.

    Training is deterministic: the same model, dataset, and config always give
    the same history.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    logger = logger or get_logger()
    rng = np.random.default_rng(config.seed)
    n_train = len(dataset.y_train)
    history: list[EpochMetrics] = []

    log_event(
        logger,
        "training_started",
        run_id=run_id,
        max_epochs=config.max_epochs,
        learning_rate=config.learning_rate,
        batch_size=config.batch_size,
        n_train=n_train,
        n_val=len(dataset.y_val),
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

    result = TrainingResult(run_id=run_id, epochs_run=len(history), history=history)
    log_event(
        logger,
        "training_finished",
        run_id=run_id,
        epochs_run=result.epochs_run,
        final_val_loss=round(result.final_val_loss, 6),
    )
    return result
