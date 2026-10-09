# experiment-runs

Single-user, single-process HTTP API for logging ML training runs: log a run
with its model type and hyperparameters, list runs with an at-a-glance
**stalled** indicator, finish a run by recording its final metrics, and delete
a run. Storage is crash-safe. It is meant for local, single-machine use and
ships without authentication.

Full behavioral spec: [specs/001-experiment-runs/spec.md](./specs/001-experiment-runs/spec.md).

## Prerequisites

- Python 3.10 or newer (`python3 --version` must print 3.10 or later).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Test

```bash
pytest
ruff check .
ruff format --check .
mypy
```

The pytest suite includes the atomic-write crash simulation, real `SIGKILL`
and `SIGTERM` tests (POSIX only), and the 100-cycle restart test. To skip the
latency check on slow CI hardware:

```bash
CI_SKIP_PERF=1 pytest            # PowerShell: $env:CI_SKIP_PERF=1; pytest
```

## Run

```bash
python -m experiment_runs
```

Defaults: host `127.0.0.1`, port `8000`, store `data/runs.json`. Override with
the `HOST`, `PORT`, and `STORE_PATH` environment variables. Startup prints two
JSON lines to stdout: one about the store (`store.initialized` or
`store.loaded`), then `server.started` once the server is listening, saying
whether the store existed and how many runs were loaded.

For curl scenarios covering each user story, see
[specs/001-experiment-runs/quickstart.md](./specs/001-experiment-runs/quickstart.md).

## Notes

- No authentication, no metrics endpoint, no health endpoint, and no
  interactive docs (spec FR-014 and FR-019).
- Storage is one JSON file updated with an atomic temp-file, `fsync`, and
  rename. If the file is unreadable at startup, it is renamed to
  `<store>.corrupt.<UTC timestamp>` and the process exits with code 1 instead
  of silently starting empty.
- Exit codes: `0` clean shutdown (Ctrl+C or SIGTERM), `1` corrupt store
  (quarantined), `2` invalid configuration, `3` the server could not start
  (for example, the port is taken), `4` the store exists but cannot be read
  (it is left untouched).
