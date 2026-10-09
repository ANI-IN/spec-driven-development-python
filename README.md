# Spec-Driven Development: A Python ML Project

A hands-on project that teaches **spec-driven development** with Claude Code:
write a short, testable spec before any code, let the agent build against it,
and when something goes wrong, fix the spec first.

It is written for early-career software and AI/ML engineers. The code is
small, but it is organized like a real Python project: a `src/` layout, type
hints checked by `mypy --strict`, linting and formatting with Ruff, and a
pytest suite.

## 1. What You Will Learn

- Turn a PRD with deliberate gaps into a one-page spec whose every acceptance
  criterion is testable.
- Check a spec against a quality checklist before an agent ever sees it.
- Drive an implementation from the spec with Claude Code in Plan Mode, and
  patch the spec, not just the code, when a gap surfaces.
- Trace each defect back to the spec gap that caused it.
- Run the same idea at scale with GitHub's **Spec Kit**: constitution →
  specify → clarify → plan → tasks → analyze → implement, with project rules
  the tool enforces.

## 2. The Two Use Cases

Both come from everyday ML engineering work.

**The lab: early stopping for a training loop.** `minitrain` is a tiny NumPy
library that trains a logistic-regression classifier. Its loop always runs
for 300 epochs and returns the last model. On the bundled dataset the
validation loss is lowest near epoch 21 (about 0.48) and climbs to about 0.88
by epoch 300, so you get back a badly overfit model. The
[PRD](lab/prd-early-stopping.md) asks for early stopping with best-model
restore and leaves the hard questions open on purpose: what counts as an
improvement, how much patience, what to do when the loss is `nan`. You
answer them in your spec, then build it.

**The demo: an Experiment Runs API built with Spec Kit.** A single-user
service where an ML engineer logs training runs (model type,
hyperparameters, an optional time budget), finishes them with final metrics,
and sees **stalled** runs at a glance. Spec Kit generates the spec, plan,
tasks, and a FastAPI implementation with crash-safe storage. A complete
worked example is checked in so you can compare your run with it.

## 3. Repository Layout

```text
.
├── README.md                    # this file
├── CLAUDE.md                    # project memory for Claude Code
├── pyproject.toml               # the minitrain package and dev tools
├── src/minitrain/               # lab codebase: data, model, trainer, CLI
├── tests/                       # pytest suite for minitrain and the docs
├── lab/                         # the hand-written spec lab
│   ├── README.md                # step-by-step lab guide
│   ├── prd-early-stopping.md    # the PRD (intentionally incomplete)
│   ├── spec-template.md         # one-page spec template
│   ├── example-spec.md          # worked example for a different feature
│   ├── spec-quality-checklist.md
│   └── worksheet.md             # exercises 1 to 4
├── demo/                        # the Spec Kit walkthrough
│   ├── README.md                # concepts + step-by-step demo
│   ├── experiment-runs-reference/       # untouched `specify init` scaffold
│   └── experiment-runs-example-output/  # full worked example (Python)
├── docs/
│   └── spec-driven-development.docx     # the whole lesson as one document
└── .github/workflows/ci.yml     # lint, type-check, and test on every push
```

## 4. Quickstart

You need Python 3.10 or newer and `git`. The Spec Kit demo also needs
Claude Code and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ANI-IN/spec-driven-development-python.git
cd spec-driven-development-python
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Check that everything is green, then see the problem the lab solves:

```bash
pytest
ruff check .
ruff format --check .
mypy
python -m minitrain
```

`python -m minitrain` prints something like:

```text
run_id            3f2a9c1d7e4b
epochs run        300
best val_loss     0.4789 at epoch 21 (val_accuracy 0.775)
final val_loss    0.8777 at epoch 300 (val_accuracy 0.733)
final train_loss  0.2139
```

To run the worked example of the demo:

```bash
cd demo/experiment-runs-example-output
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## 5. How to Work Through It

1. Read the concept sections at the top of the
   [demo README](demo/README.md) (about 10 minutes).
2. Do the [lab](lab/README.md): read the PRD, write `spec.md`, build early
   stopping with Claude Code, and fill in the [worksheet](lab/worksheet.md)
   (about 90 minutes).
3. Run the [Spec Kit demo](demo/README.md#demo-build-an-experiment-runs-api-with-spec-kit)
   in a scratch directory and compare each phase with the worked example
   (about 45 minutes).

The same material is collected in
[`docs/spec-driven-development.docx`](docs/spec-driven-development.docx) if
you prefer one document.

## 6. Branches

| Branch | Contents |
|---|---|
| `main` | The starting point. `minitrain` has no early stopping. Do the lab here, on your own `feature/early-stopping-<initials>` branch. |
| `solution/early-stopping` | A reference solution: a filled-in `spec.md`, `src/minitrain/early_stopping.py`, the changes to `trainer.py` and the CLI, tests for every acceptance criterion, and a completed worksheet. Compare with it after you finish. |

```bash
git fetch origin
git diff main origin/solution/early-stopping --stat
```

## 7. Quality Gates

Every change in this repository passes the same gates locally and in CI:

| Gate | Command |
|---|---|
| Tests | `pytest` |
| Lint | `ruff check .` |
| Format | `ruff format --check .` |
| Types | `mypy` (strict mode) |

CI runs them on Python 3.10, 3.11, 3.12, and 3.13 for both `minitrain` and
the demo's worked example. `tests/test_docs.py` also checks that every
relative link in the Markdown files points at a file that exists.
