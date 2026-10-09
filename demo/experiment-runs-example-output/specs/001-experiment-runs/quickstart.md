# Quickstart: Experiment Runs API

**Feature**: 001-experiment-runs
**Purpose**: runnable scenarios that prove the feature works end to end. This
is not an implementation guide: for the source layout see
[plan.md § Source Code](./plan.md#source-code-repository-root), for the domain
model see [data-model.md](./data-model.md), and for the wire format see
[contracts/openapi.yaml](./contracts/openapi.yaml).

## Prerequisites

- Python 3.10 or newer (`python3 --version`).
- `curl` on `PATH`.
- The working directory is the project root.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Run the test suite

Every user story and functional requirement is covered by a pytest test. The
suite must be green before the feature counts as complete.

```bash
pytest
```

It includes:

- **Contract tests** (`tests/test_routes.py`) for `POST /runs`, `GET /runs`,
  `POST /runs/{run_id}/finish`, and `DELETE /runs/{run_id}`: status codes and
  body shapes match [contracts/openapi.yaml](./contracts/openapi.yaml).
- **Atomic-write tests** (`tests/test_atomic_write.py`): 50 simulated crashes,
  each at a random one of five syscalls, plus 25 real `SIGKILL`s of a writer
  process (POSIX only).
- **Service tests** (`tests/test_service.py`): ordering (FR-004a), stalled
  detection (FR-009), conflict on a second finish (FR-006), and not found on
  unknown ids (FR-008).
- **Repository and startup tests**: missing store, valid store, and corrupt
  store (renamed to `<path>.corrupt.<timestamp>`; the process exits with
  code 1).

To skip the latency check on slow shared CI machines:

```bash
CI_SKIP_PERF=1 pytest            # PowerShell: $env:CI_SKIP_PERF=1; pytest
```

## Run the service

```bash
python -m experiment_runs
```

Defaults: host `127.0.0.1`, port `8000`, store `data/runs.json`. Override with
`HOST`, `PORT`, and `STORE_PATH`. Once the server is listening, one JSON line
is printed:

```json
{"timestamp": "...", "event": "server.started", "host": "127.0.0.1", "port": 8000, "store_path": "data/runs.json", "store_existed": false, "run_count": 0}
```

Run the scenarios below from a second terminal.

## User Story 1: log and list runs

```bash
curl -s -X POST localhost:8000/runs -H 'content-type: application/json' \
  -d '{"name": "baseline", "model_type": "logistic_regression",
       "hyperparameters": {"learning_rate": 0.05, "epochs": 20}}'
# the new run: "status": "running", "stalled": false, a UUID v4 "id"
# (add -i to curl to see the 201 status line)

curl -s localhost:8000/runs
# a JSON array containing the run

curl -s -X POST localhost:8000/runs -H 'content-type: application/json' \
  -d '{"name": "   ", "model_type": "mlp"}'
# 400 {"error": "validation_error", ..., "details": [{"field": "name", ...}]}
```

## User Story 2: survive a crash

Note the run ids. From the second terminal, kill the server abruptly (this
matches any process whose command line contains `experiment_runs`):

```bash
pkill -9 -f experiment_runs
```

Start it again in the first terminal with `python -m experiment_runs`, then
list the runs from the second terminal:

```bash
curl -s localhost:8000/runs      # the same runs, same ids
```

Corrupt-store recovery:

```bash
# Stop the server (Ctrl+C), then:
echo '{oops' > data/runs.json
python -m experiment_runs; echo "exit code: $?"
# server.start_failed with reason "store_corrupt"; exit code: 1
ls data/                         # runs.json.corrupt.<timestamp>
python -m experiment_runs        # starts with an empty store
```

## User Story 3: finish and delete

```bash
RUN=$(curl -s -X POST localhost:8000/runs -H 'content-type: application/json' \
  -d '{"name": "xgb-depth6", "model_type": "xgboost"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -s -X POST localhost:8000/runs/$RUN/finish -H 'content-type: application/json' \
  -d '{"metrics": {"val_auc": 0.91, "val_loss": 0.33}}'
# 200, "status": "finished", the metrics, a "finished_at"

curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/runs/$RUN/finish \
  -H 'content-type: application/json' -d '{"metrics": {"val_auc": 0.99}}'
# 409; the original metrics are kept

curl -s -o /dev/null -w '%{http_code}\n' -X DELETE localhost:8000/runs/$RUN   # 204
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE localhost:8000/runs/$RUN   # 404
```

## User Story 4: stalled runs at a glance

```bash
curl -s -X POST localhost:8000/runs -H 'content-type: application/json' \
  -d '{"name": "quick-check", "model_type": "mlp", "time_budget_minutes": 1}'
curl -s -X POST localhost:8000/runs -H 'content-type: application/json' \
  -d '{"name": "long-job", "model_type": "mlp", "time_budget_minutes": 600}'
sleep 65
curl -s localhost:8000/runs
# "quick-check" is first with "stalled": true; "long-job" has "stalled": false
```
