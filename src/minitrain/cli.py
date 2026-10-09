"""Command-line entry point: ``minitrain`` or ``python -m minitrain``.

Trains the classifier on the bundled dataset and prints a short report that
compares the best validation loss seen during training with the loss of the
model you actually get back.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from collections.abc import Sequence

from minitrain.config import ConfigError, TrainingConfig
from minitrain.data import make_dataset
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
    parser.add_argument(
        "--verbose", action="store_true", help="log one JSON line per epoch"
    )
    return parser


def format_report(result: TrainingResult) -> str:
    finite = [m for m in result.history if math.isfinite(m.val_loss)]
    best = min(finite or result.history, key=lambda m: m.val_loss)
    last = result.history[-1]
    lines = [
        f"run_id            {result.run_id}",
        f"epochs run        {result.epochs_run}",
        f"best val_loss     {best.val_loss:.4f} at epoch {best.epoch} "
        f"(val_accuracy {best.val_accuracy:.3f})",
        f"final val_loss    {last.val_loss:.4f} at epoch {last.epoch} "
        f"(val_accuracy {last.val_accuracy:.3f})",
        f"final train_loss  {last.train_loss:.4f}",
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
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    logger = get_logger()
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    dataset = make_dataset()
    model = LogisticRegression(dataset.n_features)
    result = train(model, dataset, config, logger=logger)
    print(format_report(result))
    return 0
