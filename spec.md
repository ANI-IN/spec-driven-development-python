# Spec: Early Stopping with Best-Model Restore

## 1. Context

`train()` always runs `max_epochs` and returns the last epoch's weights. On the
bundled dataset validation loss bottoms out near epoch 21 (about 0.48) and
reaches about 0.88 by epoch 300, so callers get an overfit model, waste
compute, and get no signal when a run diverges. This spec adds opt-in early
stopping on validation loss with best-model restore.
PRD: [lab/prd-early-stopping.md](lab/prd-early-stopping.md). No existing
design notes.

## 2. Scope

- A new frozen dataclass `EarlyStopping` in `src/minitrain/early_stopping.py`
  with `patience`, `min_delta`, `start_from_epoch`, and `restore_best`.
- A new keyword-only argument `train(..., early_stopping=None)`.
- New `TrainingResult` fields: `stop_reason`, `best_epoch`, `best_val_loss`,
  `restored_best`.
- CLI flags `--early-stopping`, `--patience`, `--min-delta`, and
  `--start-from-epoch`, and report lines saying why the run stopped and which
  epoch's weights were returned.

**Definitions used below.** The monitored value is `val_loss`; lower is
better. The **best epoch** is the epoch with the lowest *finite* `val_loss`
seen so far, earliest on ties. A **significant improvement** at epoch `e`
means `val_loss[e] < r - min_delta`, where `r` is the value at the last
significant improvement (epoch 1 is always significant). Significance only
drives the patience counter; the best epoch moves on *any* decrease.

## 3. Acceptance criteria

- [ ] AC1: With `EarlyStopping()` defaults on `make_dataset()` and
      `TrainingConfig()`, training stops with `stop_reason ==
      "patience_exhausted"` and `epochs_run <= 60`.
- [ ] AC2: With `restore_best=True` (default), after `train()` returns,
      `model.loss(x_val, y_val)` equals the lowest finite `val_loss` in
      `history`, and `result.best_epoch` is that epoch (earliest on ties).
- [ ] AC3: Training stops at the first epoch where the number of
      non-warm-up epochs since the last significant improvement equals
      `patience`.
- [ ] AC4: A decrease of `min_delta` or less from `r` does not reset the
      patience counter, but can still become the best epoch.
- [ ] AC5: Epochs `1..start_from_epoch` are not monitored.
- [ ] AC6: If `val_loss` is `nan`, `inf`, or `-inf` at epoch `k`, training
      stops after epoch `k` with `stop_reason == "non_finite_metric"`. The
      training loss is not checked. If a finite best exists and
      `restore_best`, it is restored. If `k == 1`, `best_epoch` and
      `best_val_loss` are `None` and `restored_best` is `False`.
- [ ] AC7: With `restore_best=False`, the model keeps the weights from the
      last completed epoch.
- [ ] AC8: `EarlyStopping` raises `ConfigError` at construction when
      `patience` is not an integer `>= 1`, `min_delta` is not a finite number
      `>= 0` (booleans are not numbers), `start_from_epoch` is not an integer
      `>= 0`, or `restore_best` is not a bool. NumPy integers, floats, and
      booleans count as their Python kinds and are stored as plain Python values. The CLI prints the error to
      stderr and exits with code 2.
- [ ] AC9: `train(model, dataset, config)` without `early_stopping` returns
      the same history and leaves the same final weights as before this
      change (for the defaults: `history[20].val_loss` about 0.478891,
      `history[-1].val_loss` about 0.877704); `stop_reason == "max_epochs"`,
      `restored_best` is `False`, and `best_epoch` and `best_val_loss` are
      still filled in.
- [ ] AC10: If `max_epochs` is reached before patience runs out,
      `stop_reason == "max_epochs"`, and the best epoch is still restored when
      `restore_best` is set. If patience runs out on the last epoch itself,
      `stop_reason == "patience_exhausted"`.
- [ ] AC11: When early stopping triggers, exactly one
      `early_stopping_triggered` log event is emitted with `run_id`, `epoch`,
      `reason`, `best_epoch`, and `best_val_loss`. When weights are restored,
      exactly one `best_weights_restored` event is emitted. `training_started`
      gains `early_stopping` (true or false), and `training_finished` gains
      `stop_reason`, `best_epoch`, and `restored_best`.
- [ ] AC12: Same model, dataset, config, and `EarlyStopping` give the same
      history, `best_epoch`, and weights.
- [ ] AC13: `python -m minitrain --early-stopping` prints `stop reason` and
      `returned model` lines (`best epoch (N)` or `last epoch (N)`). Passing
      `--patience`, `--min-delta`, or `--start-from-epoch` without
      `--early-stopping` prints an error to stderr and exits with code 2.

## 4. Constraints

- Defaults: `patience=10`, `min_delta=1e-3` (absolute, in the same units
  as `val_loss`), `start_from_epoch=0`, `restore_best=True`.
- `train()` keeps its positional signature; new arguments are keyword-only
  and every new `TrainingResult` field has a default.
- NumPy only. Keeping the best weights costs one copy of the parameters per
  new best epoch, held in memory; nothing is written to disk.
- `patience` larger than `max_epochs` is allowed (see AC10).

## 5. Non-goals

- Monitoring any metric other than `val_loss`, or "higher is better" metrics.
- Relative (percentage) `min_delta`.
- Learning-rate schedules or reduce-on-plateau.
- Checkpointing to disk or resuming after the process exits.
- Stopping on a non-finite *training* loss while validation loss is finite.

## 6. Definition of done

- AC1 to AC12 covered by `tests/test_early_stopping.py`; AC13 and the CLI
  side of AC8 by `tests/test_cli.py`. Each acceptance test's name starts with
  its AC number.
- `pytest`, `ruff check .`, `ruff format --check .`, and `mypy` pass.
- The `trainer.py` module docstring and the `EarlyStopping` docstring describe
  the behavior.
- Observability: the log events and fields in AC11.

## 7. Interfaces

```python
@dataclass(frozen=True)
class EarlyStopping:
    patience: int = 10
    min_delta: float = 1e-3
    start_from_epoch: int = 0
    restore_best: bool = True


StopReason = Literal["max_epochs", "patience_exhausted", "non_finite_metric"]


def train(
    model,
    dataset,
    config,
    *,
    early_stopping: EarlyStopping | None = None,
    run_id: str | None = None,
    logger: logging.Logger | None = None,
) -> TrainingResult: ...


# New TrainingResult fields (all defaulted):
#   stop_reason: StopReason = "max_epochs"
#   best_epoch: int | None = None
#   best_val_loss: float | None = None
#   restored_best: bool = False
```

`EarlyStoppingMonitor` (also in `early_stopping.py`) is the per-run state
machine `train()` uses; it is exported for testing the rules with plain
numbers. `EarlyStopping`, `EarlyStoppingMonitor`, and `StopReason` are
exported from `minitrain`.
