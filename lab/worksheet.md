# Worksheet: Spec-Driven Development (reference answers)

This is a completed worksheet for the reference solution. Yours will differ;
what matters is that each gap and each defect is written down and traced.

## Exercise 1: Read the PRD

Open [prd-early-stopping.md](prd-early-stopping.md) and run
`python -m minitrain` to see the problem for yourself.

Three things the PRD does **not** answer (its open questions touch on some
of these, but none spells them out):

1. **What "best" means when `min_delta` is in play.** If tiny improvements do
   not count for patience, is the best model the one with the lowest loss, or
   the last one that counted as a significant improvement?
2. **What happens on a non-finite loss before any best exists**, for example
   `nan` at epoch 1. There is nothing to restore.
3. **Whether the best weights are restored when the run reaches
   `max_epochs`** without early stopping ever triggering.

Others worth answering: which loss is checked for `nan`, whether warm-up
delays that check, how ties are broken, which log fields are added, how the
CLI exposes the feature, and which types the settings accept.

## Exercise 2: Write the spec

Saved as `spec.md` at the repo root and committed before any code (the first
commit on `solution/early-stopping`). All items in
[spec-quality-checklist.md](spec-quality-checklist.md) were checked.

## Exercise 3: Implement, then iterate the spec once

The three defects below surfaced in a first implementation attempt against
the draft spec. That attempt was thrown away, not committed. Each spec fix is
its own `Spec: ...` commit, and the implementation was redone afterwards. See
them with `git log --oneline main..origin/solution/early-stopping`. One
iteration of the loop can produce several spec patches; here it produced
three.

| Spec gap | Defect that surfaced | Fix in spec |
|---|---|---|
| The draft defined the best epoch as the epoch of the last significant improvement. | On the bundled data the run restored epoch 17 (val_loss 0.4794) although epoch 21 had 0.4789, so AC2, "restored loss equals the lowest loss in history", failed. | Split the two ideas: the best epoch moves on *any* decrease (earliest on ties); significance only drives the patience counter. |
| The draft said "if the loss becomes `nan` or `inf`, stop and restore the best weights", without saying which loss or what happens with no best. | The attempt also stopped when the *training* loss was `nan` and the validation loss was fine, and crashed restoring a best that did not exist at epoch 1. | AC6 names `val_loss` only and defines the epoch-1 case; a non-goal excludes non-finite training loss. |
| The draft said warm-up epochs "are not monitored". | A run that diverged to `nan` at epoch 2 with `start_from_epoch=5` carried on training on garbage through epoch 5 and only stopped at epoch 6, the first monitored epoch. | AC5 limits warm-up to the patience counter; AC6 says the non-finite check is never delayed. |

In one sentence each:

- *The wrong-epoch restore traces to "best" being defined by the patience
  rule instead of by the lowest loss.*
- *The crash at epoch 1 traces to the spec never saying what happens when
  there is no best to restore.*
- *Training on `nan` during warm-up traces to warm-up being defined as "do not
  monitor" rather than "do not count toward patience".*

## Exercise 4: Lock the build

- [x] `spec.md` committed before any implementation code
- [x] Implementation committed on `solution/early-stopping`
- [x] At least one acceptance test passing (every AC, AC1 to AC13, is covered)
- [x] `pytest`, `ruff check .`, `ruff format --check .`, and `mypy` all pass
- [x] Branch pushed
