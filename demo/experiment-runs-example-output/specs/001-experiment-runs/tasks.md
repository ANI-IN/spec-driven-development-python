---
description: "Task list for the Experiment Runs API (001-experiment-runs)"
---

# Tasks: Experiment Runs API (Single User, No Auth)

**Input**: Design documents in [specs/001-experiment-runs/](./)

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/openapi.yaml](./contracts/openapi.yaml)

**Tests**: REQUIRED for every task that adds or changes behavior. This is not optional: [constitution.md](../../.specify/memory/constitution.md) Principle I ("Tests Before Implementation") is NON-NEGOTIABLE. Every implementation task follows a test task, and that test MUST fail before the implementation task begins.

## Format: `- [ ] [ID] [P?] [Story?] Description`

- **[P]**: can run in parallel with other [P] tasks in the same phase (different files, no ordering dependency).
- **[Story]**: `[US1]` to `[US4]`, mapping to the four user stories in [spec.md](./spec.md). Setup, Foundational, and Polish tasks have no story label.
- Every task names the exact file path(s) it touches.

## Path Conventions

Single-project Python service with a `src/` layout. Source under `src/experiment_runs/`, tests under `tests/`, one test module per source module. See [plan.md § Source Code](./plan.md#source-code-repository-root).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: get the packaging, test, lint, and type-check toolchain in place. No behavior yet.

- [X] T001 Create `pyproject.toml` with dependencies (`fastapi`, `pydantic>=2`, `uvicorn`), a `dev` extra (`pytest`, `httpx`, `httpx2`, `ruff`, `mypy`), the `experiment-runs` console script, and tool settings: pytest `testpaths = ["tests"]`, Ruff rules `E,F,W,I,B,UP,SIM`, mypy `strict = true` with the Pydantic plugin.
- [X] T002 [P] Create `src/experiment_runs/__init__.py`, `src/experiment_runs/py.typed`, and `tests/__init__.py` so `pip install -e ".[dev]"`, `pytest`, and `mypy` all succeed on an empty project. Later tests then fail for the *right* reason (missing behavior), not missing packages.

**Checkpoint**: `pip install -e ".[dev]" && pytest` reports zero tests; `mypy` and `ruff check .` pass.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: cross-cutting pieces every story needs: the error hierarchy, the structured logger, settings, and the app skeleton with error mapping. **No user story work starts until this phase is complete.**

- [X] T003 [P] Create `tests/test_errors.py` asserting every error class is an `AppError`, `ValidationError.details` round-trips, and `StoreCorruptError` carries its quarantine path. Test first.
- [X] T004 [P] Create `src/experiment_runs/errors.py` with `AppError`, `FieldError`, `ValidationError`, `NotFoundError`, `RunAlreadyFinishedError`, `StoreCorruptError`, `StoreWriteError` (constitution III). Depends on T003.
- [X] T005 [P] Create `tests/test_logger.py` asserting `log(event, **fields)` writes exactly one JSON line, includes `timestamp` (ISO 8601 UTC) and every field, stringifies unserializable values, and defaults to stdout. Test first.
- [X] T006 [P] Create `src/experiment_runs/logger.py` with `EventLogger` per FR-016 to FR-018. Standard library only. Depends on T005.
- [X] T007 [P] Create `tests/test_config.py` asserting defaults (`127.0.0.1`, `8000`, `data/runs.json`), environment overrides, empty values falling back to defaults, and invalid `PORT` raising `ValidationError`. Test first.
- [X] T008 [P] Create `src/experiment_runs/config.py` with `load_settings(env) -> Settings`. No side effects. Depends on T007.
- [X] T009 Create `src/experiment_runs/error_handlers.py` mapping exception classes to the statuses and bodies in [research.md § Decision 2](./research.md), mapping FastAPI `RequestValidationError` to 400, and logging unexpected errors with their stack. Depends on T004, T006. (Covered by T018 and T031 contract tests.)
- [X] T010 Create `src/experiment_runs/app.py` with `create_app(service, logger)`: mounts the router, registers error handlers, adds the request-log middleware that emits `request.ok` or `request.error` with `operation` and `outcome`, and disables `/docs` and `/openapi.json` (FR-019). Depends on T009.

**Checkpoint**: foundational tests green. `create_app` builds an app that maps errors correctly.

---

## Phase 3: User Story 2 - Never lose data across crashes (Priority: P1)

**Goal**: one atomic-write primitive and a repository that uses it. After this phase the storage layer is crash-safe before any HTTP route exists.

**Independent Test**: run `pytest tests/test_atomic_write.py tests/test_repository.py tests/test_models.py`. The suite includes 50 simulated crashes and a real `SIGKILL` test (SC-002), plus quarantine on corruption (FR-013).

**Why first**: US2 provides the storage every other story uses. Building US1 first would mean throwaway persistence or postponing crash safety, and both violate constitution V.

### Tests for User Story 2 (write first, must FAIL)

- [X] T011 [P] [US2] Create `tests/test_atomic_write.py` asserting: (a) new content is written and replaces old content; (b) a crash during `write`, `fsync`, or `replace` leaves the target unchanged and no `*.tmp.*` file behind; (c) the temp name contains the pid and a 16-hex-char suffix; (d) the file and its directory are both fsynced; (e) 50 random simulated crashes never leave an unparsable store; (f) killing a real writer process with `SIGKILL` at random moments never leaves a partial store (POSIX only).
- [X] T012 [P] [US2] Create `tests/test_models.py` asserting run records round-trip (running and finished), timestamps are UTC with a `Z` suffix, and `Run.from_record` rejects records `to_record` could not have produced (unknown status, blank name, nested hyperparameters, non-finite numbers, string or boolean budgets, missing fields, finished without metrics).
- [X] T013 [P] [US2] Create `tests/test_repository.py` asserting: (a) a missing store loads empty and logs `store.initialized`; (b) saved runs load back and log `store.loaded` with the count; (c) unparsable JSON, a wrong `schema_version`, a non-list `runs`, invalid records, and duplicate ids each raise `StoreCorruptError`, rename the file to `runs.json.corrupt.<timestamp>`, and log `store.quarantined`; (d) two quarantines never overwrite each other; (e) the next start after a quarantine is empty; (f) saves go through the atomic-write helper and log `store.write` success; (g) a write failure logs the error class and raises `StoreWriteError`; (h) concurrent saves never overlap.

### Implementation for User Story 2

- [X] T014 [US2] Create `src/experiment_runs/atomic_write.py` with `atomic_write_bytes(target, data)` per [research.md § Decision 1](./research.md). Standard library only. Depends on T011.
- [X] T015 [US2] Create `src/experiment_runs/models.py` with `Run`, `RunView`, `format_timestamp`, `parse_timestamp`, and `Run.to_record` / `Run.from_record`. No HTTP and no I/O. Depends on T012.
- [X] T016 [US2] Create `src/experiment_runs/repository.py` with `RunRepository.load()` and `RunRepository.save_all()`, using `atomic_write_bytes` for every write and a lock to serialize writes. It MUST NOT import FastAPI. Depends on T013, T014, T015, T004, T006.

**Checkpoint**: the store persists and reloads runs safely across crashes with no HTTP layer. `pytest tests/test_atomic_write.py tests/test_models.py tests/test_repository.py` is green.

---

## Phase 4: User Story 1 - Log and list runs (Priority: P1) 🎯 MVP

**Goal**: `POST /runs` and `GET /runs`. After this phase the MVP works end to end, and runs survive a restart thanks to US2.

**Independent Test**: run `pytest tests/test_service.py tests/test_routes.py -k "create or list"` and follow the User Story 1 scenario in [quickstart.md](./quickstart.md).

**Dependencies**: Phase 2 and Phase 3 complete.

### Tests for User Story 1 (write first, must FAIL)

- [X] T017 [P] [US1] Create `tests/test_service.py` (US1 section) asserting `create` returns a running run with a UUID v4 id, the injected clock's time, and the given hyperparameters; names are trimmed; ids are unique; `list_runs` returns every run; blank names, over-long names, non-finite or excess hyperparameters, and out-of-range budgets raise `ValidationError` naming the field and store nothing; all invalid fields are reported together. Uses a `FakeClock`.
- [X] T018 [P] [US1] Create `tests/test_routes.py` (US1 section) asserting `POST /runs` returns 201 with every `Run` field from [contracts/openapi.yaml](./contracts/openapi.yaml); hyperparameter types are preserved; a client-supplied `id` is rejected; invalid bodies, missing fields, malformed JSON, and `NaN` return 400 `validation_error`; `GET /runs` returns created runs.
- [X] T019 [P] [US1] Create `tests/test_main.py` asserting `build()` logs `server.started` with `store_existed` and `run_count` (FR-018); a corrupt store makes `main()` return 1 after logging `server.start_failed` and the next start succeeds; a bad `PORT` returns 2; `HOST` and `PORT` reach Uvicorn.

### Implementation for User Story 1

- [X] T020 [US1] Create `src/experiment_runs/service.py` with `RunService.create()` and `RunService.list_runs()`, injected `clock` and `new_id`, validation per [data-model.md § Validation Rules](./data-model.md), and save-before-swap commits per [research.md § Decision 6](./research.md). MUST NOT import FastAPI. Depends on T016, T017.
- [X] T021 [US1] Create `src/experiment_runs/schemas.py` (strict Pydantic request bodies with `extra="forbid"`, `RunResponse.from_view`, error bodies) and `src/experiment_runs/routes.py` with `POST /runs` and `GET /runs`. Routes only parse, delegate, and shape. Depends on T020, T018.
- [X] T022 [US1] Create `src/experiment_runs/main.py` (`build`, `main`, exit codes per [research.md § Decision 5](./research.md)) and `src/experiment_runs/__main__.py`. Depends on T021, T019.

**Checkpoint**: MVP complete. `python -m experiment_runs`, run the US1 scenario in [quickstart.md](./quickstart.md), kill and restart the process, and the runs are still there.

---

## Phase 5: User Story 3 - Finish and delete (Priority: P2)

**Goal**: `POST /runs/{run_id}/finish` and `DELETE /runs/{run_id}`, with a conflict on a second finish and clear 404s.

**Independent Test**: `pytest tests/test_service.py tests/test_routes.py -k "finish or delete or unknown"` and the US3 scenario in [quickstart.md](./quickstart.md).

**Dependencies**: Phase 4 complete. US3 extends the same test modules with new sections; no new files.

### Tests for User Story 3 (write first, must FAIL)

- [X] T023 [US3] Extend `tests/test_service.py` with: `finish` records metrics and the clock's time; a second `finish` raises `RunAlreadyFinishedError` and keeps the first metrics; empty, non-finite, blank-keyed, or excess metrics raise `ValidationError` and the run stays running; `delete` removes the run; unknown ids raise `NotFoundError` and change nothing; a failed write leaves state unchanged; acknowledged changes survive a restart.
- [X] T024 [US3] Extend `tests/test_routes.py` with: finish returns 200 with metrics as numbers; a second finish returns 409 `already_finished`; invalid finish bodies (including booleans and strings) return 400; unknown and malformed ids return 404 `not_found`; delete returns 204 with an empty body, then 404.

### Implementation for User Story 3

- [X] T025 [US3] Extend `src/experiment_runs/service.py` with `finish(run_id, metrics)` and `delete(run_id)`. Depends on T023.
- [X] T026 [US3] Extend `src/experiment_runs/routes.py` with the finish and delete handlers. Any id that is not stored is "not found", never a validation error. Depends on T025, T024.

**Checkpoint**: US1 and US3 together cover the full surface. The US3 quickstart scenario passes.

---

## Phase 6: User Story 4 - See stalled runs at a glance (Priority: P2)

**Goal**: `GET /runs` derives `stalled` and returns runs in FR-004a order.

**Independent Test**: `pytest tests/test_service.py tests/test_routes.py -k "stall or order"` and the US4 scenario in [quickstart.md](./quickstart.md).

**Dependencies**: Phase 4 complete. The "finished last" rule is only observable once US3's `finish` exists, so schedule after Phase 5.

### Tests for User Story 4 (write first, must FAIL)

- [X] T027 [P] [US4] Extend `tests/test_service.py` with: a run is not stalled exactly at its budget and is stalled one second later; runs without a budget never stall; finished runs never stall; the list order is stalled (oldest start first), then running (oldest first), then finished (latest finish first); `list_runs` reads the clock exactly once.
- [X] T028 [P] [US4] Extend `tests/test_routes.py` with a scenario mixing a finished run, an over-budget run, and a within-budget run, asserting the `GET /runs` order and every `stalled` flag.

### Implementation for User Story 4

- [X] T029 [US4] Add `is_stalled` and `order_runs` to `src/experiment_runs/service.py` per [research.md § Decision 7](./research.md) and use them in `list_runs`, `create`, and `finish`. Depends on T027, T028.

**Checkpoint**: all four user stories independently green. The full quickstart runs end to end.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: final hardening across stories. Every task here depends on all earlier phases.

- [X] T030 [P] Run `mypy`, `ruff check .`, and `ruff format --check .`; confirm zero errors, and that every `Any` or `type: ignore` in `src/` and `tests/` has a justifying comment (constitution II).
- [X] T031 [P] Extend `tests/test_routes.py` with: write failures return 500 `write failed`; unexpected errors return 500 and are logged with their class (also in the request line); every request logs exactly one outcome line with `operation`, `outcome`, `status`, and `run_id` where one applies (FR-016); `/docs`, `/openapi.json`, `/metrics`, and `/health` return 404 (FR-019).
- [X] T032 [P] Create `tests/test_restart_cycle.py`: 100 cycles of reopening the store and applying random creates, finishes, and deletes, asserting nothing acknowledged is ever lost (SC-006).
- [X] T033 [P] Create `tests/test_perf.py`: seed 1,000 runs, then time 50 iterations of each operation and assert p95 under 100 ms (SC-004). Skipped when `CI_SKIP_PERF` is set, but it must exist and run locally.
- [X] T034 [P] Add `README.md` with prerequisites, setup, test, and run sections, and a note that this is a single-user, no-auth service for local use.
- [X] T035 Manual pass: follow [quickstart.md](./quickstart.md) end to end on a fresh clone. Confirm SC-001 and SC-005 by walking each user story. (SC-002, SC-004, and SC-006 are asserted automatically by T011, T033, and T032.)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies.
- **Phase 2 (Foundational)**: depends on Phase 1. **Blocks every user story phase.**
- **Phase 3 (US2, persistence)**: depends on Phase 2. Blocks US1, US3, and US4, which all use the repository.
- **Phase 4 (US1, log and list)**: depends on Phase 3.
- **Phase 5 (US3, finish and delete)**: depends on Phase 4.
- **Phase 6 (US4, stalled at a glance)**: depends on Phase 4, and in practice on Phase 5 for the finished-last rule to be observable.
- **Phase 7 (Polish)**: depends on every user story phase in the release.

### Within Each User Story

- Every implementation task names the test task it depends on. Tests are written and failing before their implementation starts (constitution I).
- Order inside a story: **test → model/service → schema/route → wiring in `app.py`/`main.py`**.

### Parallel Opportunities

- Phase 2: T003/T004, T005/T006, and T007/T008 are three independent test-and-implementation pairs. T009 and T010 form a chain.
- Phase 3: T011, T012, and T013 are independent [P] test files. T014 and T015 can proceed in parallel; T016 needs both.
- Phase 4: T017, T018, and T019 are independent [P]. Implementation is a chain: T020 → T021 → T022.
- Phase 5: T023 and T024 extend files from Phase 4, so they are sequential edits, not [P].
- Phase 6: T027 and T028 touch different files, so [P]. T029 is one edit.
- Phase 7: T030 to T034 are independent [P]; T035 is the final manual pass.

### Parallel Team Example (two developers, after Phase 2)

```text
Dev A: T011 → T014              # atomic-write helper
Dev B: T012 → T015, T013 → T016 # models, then repository (T016 waits for T014)
```

Then converge on Phase 4 together.

---

## Implementation Strategy

### MVP scope

**Phases 1 → 2 → 3 → 4.** At the end of Phase 4 the service delivers both P1
stories ("log and list runs" and "never lose data across crashes"). Ship here
if needed.

### Incremental delivery after the MVP

- Add Phase 5 (US3, finish and delete), demo, deliver.
- Add Phase 6 (US4, stalled runs at a glance), demo, deliver.
- Phase 7 polish before any wider release.

### Constitution reminders (apply to every task)

- **I**: write the test, watch it fail for the intended reason, then implement.
- **II**: `mypy --strict` passes; no unjustified `Any` or `type: ignore`.
- **III**: raise only `AppError` subclasses; handle errors by class.
- **IV**: routes parse and shape, the service owns rules, the repository owns storage. No imports in the wrong direction.
- **V**: every persisted write goes through `atomic_write.py`.

---

## Notes

- Task count: 35 tasks across 7 phases (T001 to T035).
- `/speckit-analyze` remediations applied: G1 (added T033 for SC-004), G2 (added T032 to automate SC-006), G3 (added the request-log assertions in T031 for FR-016), G4 (added startup-log assertions in T019 for FR-018), U1 (added the `schema_version` check to T013), A1 (tightened SC-003 wording in spec.md).
- File-conflict note: `service.py`, `routes.py`, `tests/test_service.py`, and `tests/test_routes.py` are extended across US1, US3, and US4. Those edits are sequenced across phases, never parallel.
- Commit after each task or after each test-and-implementation pair.
