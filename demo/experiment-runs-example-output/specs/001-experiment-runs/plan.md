# Implementation Plan: Experiment Runs API (Single User, No Auth)

**Branch**: `001-experiment-runs` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-experiment-runs/spec.md`

## Summary

A single-process, single-user HTTP API for logging ML training runs (create,
list, finish with metrics, delete), with an at-a-glance stalled indicator and
crash-safe persistence. Technical approach: Python 3.10+, FastAPI for HTTP,
Pydantic v2 for request and response shapes, and pytest for tests. Runs
persist to one JSON file written atomically (temp file, `fsync`,
`os.replace`, directory `fsync`). No database, no ORM, no authentication.

## Technical Context

**Language/Version**: Python 3.10 or newer (tested on 3.10 to 3.13).

**Primary Dependencies**: FastAPI (HTTP routing and exception handlers),
Pydantic v2 (strict request schemas), Uvicorn (ASGI server). Standard library
for everything else: `uuid.uuid4` for identifiers, `os`/`secrets` for the
atomic write, `json` for the store, `threading.Lock` for write serialization.
Dev: pytest, httpx and httpx2 (for FastAPI's `TestClient`), Ruff, mypy.

**Storage**: One JSON file at a configurable path (default `data/runs.json`),
shaped `{"schema_version": 1, "runs": [...]}`. Every mutation goes through one
atomic-write helper: write `<path>.tmp.<pid>.<random>`, `fsync` it,
`os.replace` it over the target, then `fsync` the directory.

**Testing**: pytest under `tests/`, grouped by layer: storage, models,
service, routes, app assembly and error mapping, and startup.
Contract tests for each endpoint use FastAPI's `TestClient`. Unit tests cover
the service, repository, and atomic-write helper. A simulated-crash test and a
real SIGKILL test cover crash safety.

**Target Platform**: Python on Linux, macOS, and Windows developer machines
(single-process local deployment, per the spec's trust model).

**Project Type**: Single-project web service (no frontend).

**Performance Goals**: Per SC-004, every operation under 100 ms at the 95th
percentile with 1,000 runs stored, on a typical developer laptop.

**Constraints**:

- Every persisted write is atomic (spec FR-011, constitution V).
- `mypy --strict` passes with no unjustified `Any` (constitution II).
- Route modules hold no business rules; the service imports no FastAPI types;
  the repository holds no business rules (constitution IV).
- Every deliberate error is an `AppError` subclass (constitution III).
- A failing test comes first for every behavior (constitution I).

**Scale/Scope**: One user, one process, up to about 1,000 runs in typical use.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Against [.specify/memory/constitution.md](../../.specify/memory/constitution.md) v1.0.0:

| # | Principle | Compliance | How this plan satisfies it |
|---|-----------|-----------|-----------------------------|
| I | Tests Before Implementation | PASS | `tasks.md` (next phase) will order every implementation task after a failing-test task. Contract tests and the crash-during-write test are written first. |
| II | Fully Type-Hinted Code | PASS | `mypy --strict` over `src/` and `tests/` with the Pydantic plugin. Request bodies are typed Pydantic models, so no `Any` is needed at the parse boundary. |
| III | Typed Exceptions | PASS | `AppError` base with `ValidationError`, `NotFoundError`, `RunAlreadyFinishedError`, `InvalidRecordError`, `StoreCorruptError`, `StoreUnreadableError`, `StoreWriteError`. One handler module maps classes to HTTP statuses. |
| IV | One Responsibility Per Module | PASS | `routes.py` (FastAPI only), `service.py` (domain only, no FastAPI imports), `repository.py` (JSON file only). Dependencies point routes → service → repository. |
| V | Data Safety Over Convenience | PASS | `atomic_write.py` is the only writer of persisted state. The service applies a change in memory only after the repository has saved it. |

**Initial Gate Result**: PASS, no violations.

**Post-Design Re-Check** (after Phase 1): PASS. The data model, contract, and
quickstart introduce nothing that violates the five principles. Complexity
Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-experiment-runs/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output
├── checklists/
│   └── requirements.md  # From /speckit-specify
├── spec.md              # From /speckit-specify + /speckit-clarify
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/experiment_runs/
├── __main__.py        # python -m experiment_runs
├── main.py            # Process entry: settings, store load, serve, exit codes
├── app.py             # FastAPI assembly + request-log middleware (no server start)
├── config.py          # HOST, PORT, STORE_PATH parsing; no side effects
├── errors.py          # AppError base + typed subclasses
├── logger.py          # One JSON object per line on stdout
├── atomic_write.py    # Sole persistence primitive (temp → fsync → replace → dir fsync)
├── models.py          # Run, RunView, record (de)serialization
├── repository.py      # load(), save_all(); quarantine on corruption
├── service.py         # create/list/finish/delete, stalled, ordering; no HTTP
├── schemas.py         # Pydantic request/response bodies (shape and type only)
├── routes.py          # APIRouter: parse → service → shape
└── error_handlers.py  # Exception class → HTTP status and body

tests/
├── conftest.py              # FakeClock, LogCapture, client fixtures
├── test_atomic_write.py     # includes 50 simulated crashes + real SIGKILL test
├── test_repository.py
├── test_models.py
├── test_service.py
├── test_routes.py           # contract tests against contracts/openapi.yaml
├── test_error_handlers.py   # exception class → status and body
├── test_app.py              # request logging, framework errors, disabled endpoints
├── test_main.py             # startup, shutdown, exit codes (incl. real processes)
├── test_config.py
├── test_errors.py
├── test_logger.py
├── test_restart_cycle.py    # SC-006
└── test_perf.py             # SC-004 (skip with CI_SKIP_PERF=1)

pyproject.toml
```

**Structure Decision**: Single project with a `src/` layout and one module per
layer, which makes constitution principle IV auditable with a single grep: any
import pointing the wrong way is visible at once. Tests live in `tests/`,
grouped by layer, the usual pytest convention.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified.

_No violations. Table intentionally empty._

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | None | None |
