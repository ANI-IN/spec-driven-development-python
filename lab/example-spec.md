# Example Spec: Stratified, Reproducible Train/Validation Split (reference only)

> This is a worked example for a *different* feature from the one you build in
> the lab. It shows what a good spec looks like without giving away the
> early-stopping spec. Nobody builds it in this lab.

## 1. Context

`make_dataset()` in `src/minitrain/data.py` splits rows into train and
validation sets with a plain random permutation. On imbalanced data a random
split can leave the validation set with far fewer positives than the training
set, so validation metrics swing from one seed to the next. We want a split
that keeps the class balance the same in both sets and gives the same split
for the same seed. PRD: none (a team request). No existing design notes.

## 2. Scope

- A new public function
  `stratified_split(x, y, val_fraction, seed) -> Dataset` in
  `src/minitrain/data.py`.
- `make_dataset()` is **not** changed in this release (see Non-goals).

## 3. Acceptance criteria

- [ ] AC1: For each class `c`, the number of validation rows with label `c`
      equals `round(count(c) * val_fraction)`, using Python's built-in
      `round`.
- [ ] AC2: Every input row appears in exactly one of the two splits. No row is
      dropped or duplicated, and `len(train) + len(val) == len(y)`.
- [ ] AC3: Two calls with the same `x`, `y`, `val_fraction`, and `seed` return
      identical arrays. On the arrays from `make_dataset(seed=0)` combined,
      seeds 0 and 1 give different validation rows.
- [ ] AC4: Splits are not grouped by class: for an input whose 0-labels all
      come before its 1-labels, with at least 10 rows per class and `seed=0`,
      each split contains a 1-label row before some 0-label row.
- [ ] AC5: If, for any class, the AC1 count would leave that class with no
      rows in the training split or no rows in the validation split, the
      function raises `ValueError` naming the class and its count, and
      returns nothing.
- [ ] AC6: If `val_fraction` is not strictly between 0 and 1, the function
      raises `ValueError`. If `len(x) != len(y)`, it raises `ValueError`.

## 4. Constraints

- NumPy only; no scikit-learn dependency for this one function.
- Randomness comes only from `np.random.default_rng(seed)`. Global NumPy
  random state is never read or modified.
- Labels are `float64` values `0.0` and `1.0`, as elsewhere in the package.
- Runs in under 50 ms for 100,000 rows and 100 features on a developer
  laptop.

## 5. Non-goals

- Switching `make_dataset()` to the new split. That would change the bundled
  data and every number the lesson quotes, so it is a separate change with
  its own spec.
- K-fold or repeated cross-validation splits.
- Stratifying on anything other than the label, such as groups or time.
- Multi-class labels beyond `0.0` and `1.0`.

## 6. Definition of done

- AC1 to AC6 covered by tests in `tests/test_data.py`.
- `pytest`, `ruff check .`, `ruff format --check .`, and `mypy` all pass.
- The `stratified_split()` docstring states AC1 and AC5.
- No new log events. This is a pure function with no I/O.
