# Project
A lesson in spec-driven development. `minitrain` is a tiny NumPy library that
trains a logistic-regression classifier; learners write a spec for early
stopping and build it. `demo/` holds a Spec Kit walkthrough with its own
self-contained Python project.

# Map
- src/minitrain/config.py         TrainingConfig (learning rate, epochs, batch size, seed)
- src/minitrain/data.py           make_dataset(): small, wide synthetic data that overfits
- src/minitrain/model.py          LogisticRegression: loss, step, get_params/set_params
- src/minitrain/trainer.py        train(): the loop the lab changes
- src/minitrain/logging_utils.py  log_event(): one JSON line per event, always with run_id
- src/minitrain/cli.py            `python -m minitrain` report
- tests/                          pytest suite (test_docs.py checks Markdown links)
- lab/                            PRD, spec template, checklist, worksheet
- demo/experiment-runs-reference/       untouched Spec Kit scaffold; never edit it
- demo/experiment-runs-example-output/  worked example; has its own pyproject.toml

# Commands
- Install:    `pip install -e ".[dev]"` (inside a virtual environment)
- Run tests:  `pytest`
- Lint:       `ruff check .` and `ruff format --check .`
- Type check: `mypy`
- Run sample: `python -m minitrain`
- Demo project: run the same commands inside `demo/experiment-runs-example-output/`

# Code Style
- PEP 8, 4-space indentation, line length 88, enforced by Ruff.
- Type hints on every function; mypy runs in strict mode.
- Absolute imports from `minitrain`; no wildcard imports.
- Training must stay deterministic for a given seed.
- Keep `train(model, dataset, config)` backward compatible: existing callers
  must get identical results.

# Workflow
- Spec first. If `spec.md` exists at the repo root, implement against it and
  quote the acceptance criterion each test covers.
- When the spec is silent or wrong, propose a spec change before changing code.
- Do not run `/speckit-*` skills inside `demo/`; those folders are references.
