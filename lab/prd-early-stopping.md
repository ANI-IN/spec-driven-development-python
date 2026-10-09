# PRD: Early Stopping with Best-Model Restore

**Status:** Draft (intentionally; your spec fills the gaps).
**Owner:** ML platform team.
**Audience:** ML engineers who train models with `minitrain`, and the platform
engineers who maintain it.

## Problem

Engineers training models with `minitrain` report three problems:

1. **Wasted compute.** `train()` always runs for `max_epochs`. On the
   bundled dataset the validation loss stops improving after about 20 epochs,
   but the run keeps going to epoch 300. On real jobs that is hours of paid
   GPU time spent making the model worse.
2. **The wrong model is returned.** After training, the model holds the
   weights from the *last* epoch. Run `python -m minitrain` and compare the
   two lines of the report: the best validation loss was about 0.48 near epoch
   21, while the model you get back scores about 0.88. The best model existed
   during training and was thrown away.
3. **Broken runs do not fail fast.** When a run diverges (for example, a bad
   learning rate turns the loss into `nan` or `inf`), training carries on to
   the last epoch and returns a useless model with no signal that anything
   went wrong.

We need training that stops once the model stops getting better, returns the
best model it saw, and stops at once when a run has clearly broken.

## Users

- **ML engineers** calling `train()` from notebooks, scripts, and pipelines.
- **Platform engineers** reading training logs to work out why a run stopped
  where it did.

## Goals

- Training stops automatically when the validation metric has stopped
  improving.
- The model returned by `train()` is the best one seen during the run, not
  merely the last one.
- A run whose monitored metric becomes non-finite stops immediately and says
  why.
- Anyone reading the result or the logs can tell when and why a run stopped.

## Non-goals

- Learning-rate schedules, or reducing the learning rate on a plateau.
- Saving checkpoints to disk, or resuming a run after the process exits.
- Hyperparameter search.
- Monitoring more than one metric at a time (one metric, this release).

## High-level requirements

- Early stopping is **opt-in**. Existing callers that do not ask for it get
  exactly the behavior they get today, epoch for epoch.
- The caller chooses how many epochs without improvement to tolerate.
- Tiny improvements caused by noise must not keep a run alive forever.
- The caller can choose whether the best weights are restored at the end.
- The training result records when the run stopped, which epoch was best, and
  why the run ended.
- Every stop decision is visible in the existing structured logs.

## Open questions (deliberately left open)

> The PRD leaves these out on purpose. Your spec must answer them.

- Which metric is monitored, and is "better" lower or higher?
- What exactly counts as an improvement? Is any decrease enough, or must it
  beat the best value by some margin? Is that margin absolute or relative?
- Does the patience counter reset on any improvement, or only on a new best?
- Can early stopping trigger in the first few epochs, while the model is still
  warming up?
- When the run stops, which weights does the caller get: the best epoch's or
  the last epoch's? What if the best epoch *is* the last epoch?
- What happens when the monitored value is `nan` or `inf`? What if it is
  non-finite at epoch 1, before any best value exists?
- What values of the new settings are invalid (negative patience, negative
  margin), and what error does the caller see?
- What if patience is larger than `max_epochs`?
- How does a run that reaches `max_epochs` without triggering report itself?

## Constraints

- Must work with the existing `train(model, dataset, config)` call.
  Positional arguments and the current `TrainingResult` fields must keep
  working, because existing notebooks depend on them.
- NumPy only. No new runtime dependencies.
- Training must stay deterministic: same model, dataset, config, and seed
  give the same result.
- Must be observable through the existing structured logging (`log_event`,
  one JSON line per event, every line carrying `run_id`).
- Must pass the repo's gates: `pytest`, `ruff check .`,
  `ruff format --check .`, and `mypy` in strict mode.

## Acceptance signals (from an ML engineer's view)

- With early stopping on and default settings, training on the bundled
  dataset ends well before epoch 300.
- After training, the model's validation loss equals the best validation loss
  recorded in the history, not the last one.
- A run whose validation loss becomes `nan` stops at that epoch, and the
  result says the reason was a non-finite metric.
- Calling `train()` exactly as before gives an identical history and identical
  weights.
