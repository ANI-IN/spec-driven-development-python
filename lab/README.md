# Lab: Write the Spec, Then Build Early Stopping

**Time:** about 90 minutes (5 to read the PRD, 20 to write the spec, 40 to
build, 15 for tests, 10 to trace defects and lock the build).

**Output:** a branch `feature/early-stopping-<initials>` with a committed
`spec.md`, an implementation, and at least one passing acceptance test.

> The [Spec Kit demo](../demo/README.md) shows the same PRD → spec → code
> chain driven by GitHub's Spec Kit toolkit (`/speckit-constitution →
> /speckit-specify → /speckit-plan → /speckit-tasks → /speckit-implement`).
> Run it before or after this lab to compare the tool-driven form with the
> hand-written template used here.

## The codebase

`minitrain` (under `src/minitrain/`) is a tiny NumPy library that trains a
logistic-regression classifier with mini-batch gradient descent. Its training
loop always runs for `max_epochs` and hands back the model from the last
epoch. On the bundled dataset that model is badly overfit. Your feature fixes
that.

| File | What it does |
|---|---|
| `config.py` | `TrainingConfig`: learning rate, epochs, batch size, seed |
| `data.py` | `make_dataset()`: a small, wide synthetic dataset that overfits |
| `model.py` | `LogisticRegression` with `loss`, `step`, `get_params`, `set_params` |
| `trainer.py` | `train()`: the loop you will change |
| `logging_utils.py` | `log_event()`: one JSON log line per event |
| `cli.py` | `python -m minitrain`: trains and prints a report |

## Setup

1. Install and check that everything is green (see the
   [repo README](../README.md#4-quickstart) for the virtual environment):

   ```bash
   pip install -e ".[dev]"
   pytest
   python -m minitrain
   ```

2. Read the PRD: [prd-early-stopping.md](prd-early-stopping.md).
3. Open the spec template: [spec-template.md](spec-template.md).
4. Read the worked example for a different feature:
   [example-spec.md](example-spec.md).
5. Open the checklist: [spec-quality-checklist.md](spec-quality-checklist.md).

## Steps

### 1. Note the PRD gaps (5 min)

In your [worksheet](worksheet.md), write down **three things the PRD does not
answer**. Each one is a spec-writing opportunity. The PRD lists some open
questions; find at least one it does not list.

### 2. Write the spec (20 min)

- Create the branch: `git switch -c feature/early-stopping-<initials>`.
- Fill in the template and save it as `spec.md` at the repo root.
- Go through the checklist until every box is ticked.
- Commit the spec **before** any code: `git add spec.md && git commit -m "Add
  early-stopping spec"`.

### 3. Drive the implementation through Plan Mode (40 min)

- Start Claude Code at the repo root and point it at `spec.md`.
- Use Plan Mode (press `Shift+Tab` until the mode indicator shows plan mode)
  so you review the plan before any file changes.
- Implement against the spec. When a gap surfaces, **patch the spec first,
  then re-run**.
- Aim for one spec iteration. The point is the loop, not perfection.

A starting prompt:

```text
Read spec.md and src/minitrain/trainer.py. Propose a plan to implement the
spec. Do not write code yet. List every acceptance criterion and the test that
will prove it.
```

### 4. Tests (15 min)

- At minimum, one passing test for one acceptance criterion. Aim for one test
  per criterion.
- Put tests in `tests/`, following the existing files (`test_trainer.py` is
  the closest neighbor).
- Run every gate before you call it done:

  ```bash
  pytest
  ruff check .
  ruff format --check .
  mypy
  ```

### 5. Defect-to-spec trace (5 min)

For each defect or rework moment, fill in a row of the
[worksheet](worksheet.md) and be ready to say:

> *"This defect traces to this spec gap."*

### 6. Lock the build (5 min)

- `spec.md` committed
- Implementation committed
- Tests and gates passing locally
- Branch pushed: `git push -u origin feature/early-stopping-<initials>`

## What "done" looks like

```text
feature/early-stopping-<initials>
├── spec.md                          # your spec, committed first
├── src/minitrain/early_stopping.py  # or wherever your spec puts it
├── src/minitrain/trainer.py         # touched
└── tests/test_early_stopping.py
```

When you are finished, compare your work with the reference solution on the
`solution/early-stopping` branch:

```bash
git fetch origin
git diff main origin/solution/early-stopping --stat
git show origin/solution/early-stopping:spec.md
```

Your spec does not have to match it. Look at the decisions it made that yours
did not, and ask which of your gaps would have become defects.
