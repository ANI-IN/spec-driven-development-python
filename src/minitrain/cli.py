"""Command-line entry point: ``minitrain`` or ``python -m minitrain``.

Trains the classifier on the bundled dataset and prints a short report that
compares the best validation loss seen during training with the loss of the
model you actually get back. ``--early-stopping`` turns on early stopping with
best-model restore; ``--patience``, ``--min-delta``, and ``--start-from-epoch``
tune it and are only accepted together with it.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from minitrain.config import ConfigError, TrainingConfig
from minitrain.data import make_dataset
from minitrain.early_stopping import EarlyStopping
from minitrain.logging_utils import get_logger
from minitrain.model import LogisticRegression
from minitrain.trainer import TrainingResult, train


def build_parser() -> argparse.ArgumentParser:
    defaults = TrainingConfig()
    parser = argparse.ArgumentParser(
        prog="minitrain", description="Train the demo classifier."
    )
    parser.add_argument("--learning-rate", type=float, default=defaults.learning_rate)
    parser.add_argument("--max-epochs", type=int, default=defaults.max_epochs)
    parser.add_argument("--batch-size", type=int, default=defaults.batch_size)
    parser.add_argument("--seed", type=int, default=defaults.seed)
    stopping = EarlyStopping()
    parser.add_argument(
        "--early-stopping",
        action="store_true",
        help="stop when validation loss stops improving and restore the best model",
    )
    parser.add_argument("--patience", type=int, help=f"default {stopping.patience}")
    parser.add_argument("--min-delta", type=float, help=f"default {stopping.min_delta}")
    parser.add_argument(
        "--start-from-epoch", type=int, help=f"default {stopping.start_from_epoch}"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="log one JSON line per epoch"
    )
    return parser


def early_stopping_from(args: argparse.Namespace) -> EarlyStopping | None:
    """Build the settings from CLI flags; tuning flags need --early-stopping."""
    tuning = {
        "patience": args.patience,
        "min_delta": args.min_delta,
        "start_from_epoch": args.start_from_epoch,
    }
    given = {name: value for name, value in tuning.items() if value is not None}
    if not args.early_stopping:
        if given:
            flags = ", ".join("--" + name.replace("_", "-") for name in given)
            raise ConfigError(f"{flags}: these settings require --early-stopping")
        return None
    return EarlyStopping(**given)


def format_report(result: TrainingResult) -> str:
    last = result.history[-1]
    lines = [
        f"run_id            {result.run_id}",
        f"epochs run        {result.epochs_run}",
        f"stop reason       {result.stop_reason}",
    ]
    if result.best_epoch is not None:
        best = result.history[result.best_epoch - 1]
        lines.append(
            f"best val_loss     {best.val_loss:.4f} at epoch {best.epoch} "
            f"(val_accuracy {best.val_accuracy:.3f})"
        )
    lines += [
        f"final val_loss    {last.val_loss:.4f} at epoch {last.epoch} "
        f"(val_accuracy {last.val_accuracy:.3f})",
        f"final train_loss  {last.train_loss:.4f}",
        "returned model    "
        + (
            f"best epoch ({result.best_epoch})"
            if result.restored_best
            else f"last epoch ({last.epoch})"
        ),
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = TrainingConfig(
            learning_rate=args.learning_rate,
            max_epochs=args.max_epochs,
            batch_size=args.batch_size,
            seed=args.seed,
        )
        early_stopping = early_stopping_from(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    logger = get_logger()
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    dataset = make_dataset()
    model = LogisticRegression(dataset.n_features)
    result = train(model, dataset, config, early_stopping=early_stopping, logger=logger)
    print(format_report(result))
    return 0
