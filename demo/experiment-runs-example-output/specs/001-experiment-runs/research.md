# Phase 0 Research: Experiment Runs API

**Feature**: 001-experiment-runs
**Date**: 2026-10-10
**Status**: All unknowns resolved.

The `/speckit-plan` arguments and the answers in
[spec.md § Clarifications](./spec.md#clarifications) fix the stack. No
`NEEDS CLARIFICATION` markers remained. This document records the technical
choices that still needed a decision, with rationale and rejected
alternatives.

---

## Decision 1: Atomic write mechanics

**Decision**: open `<target>.tmp.<pid>.<16 hex chars>` with `O_CREAT | O_EXCL`,
write all bytes, `os.fsync` the file, close it, `os.replace(temp, target)`,
then `fsync` the target's directory. On any failure before the replace, delete
the temp file and re-raise.

**Rationale**:

1. `os.replace` is atomic on the same filesystem on POSIX and Windows, so a
   reader sees either the old file or the new one, never a partial one.
2. `fsync` on the temp file forces its bytes to disk before the rename, so a
   crash cannot leave a renamed but empty file.
3. `fsync` on the directory makes the rename itself durable; without it, a
   power loss can undo the rename even though the temp file was written.
   Windows cannot open directories, so this step is skipped there.
4. The pid and random suffix prevent temp-name collisions if another process
   ever touches the directory. The spec assumes one process, but it costs
   nothing.

**Alternatives considered**:

- **`Path.write_text` on the target**: rejected. It violates constitution V:
  a crash mid-write leaves the target truncated.
- **`tempfile.NamedTemporaryFile(delete=False)`**: workable, but its naming and
  cleanup rules differ across platforms. Explicit `os.open` keeps the
  behavior obvious and testable.
- **Append-only log plus snapshots**: rejected. Even safer, but it adds
  compaction and replay the spec does not need at about 1,000 runs.
- **SQLite**: rejected. The user excluded databases.

## Decision 2: Exception to HTTP status mapping

**Decision**: one module, `error_handlers.py`, maps exception classes:

| Exception | HTTP status | Body |
|-----------|-------------|------|
| `ValidationError` (service) | 400 | `{"error": "validation_error", "message", "details": [{"field", "message"}]}` |
| `RequestValidationError` (FastAPI) | 400 | same shape; malformed JSON is reported with field `body` |
| `NotFoundError` | 404 | `{"error": "not_found", "message"}` |
| `RunAlreadyFinishedError` | 409 | `{"error": "already_finished", "message"}` |
| `StoreWriteError` | 500 | `{"error": "internal_error", "message": "write failed"}` |
| `StoreCorruptError` | 500 | `{"error": "internal_error", "message": "store is corrupt"}` (normally seen only at startup, see Decision 5) |
| Any other exception | 500 | `{"error": "internal_error", "message": "unexpected error"}`, logged with its stack |

**Rationale**: keeps constitution III (branch on class, never on text) and IV
(mapping lives in one module), and gives clients a stable `error` code.
FastAPI's default for invalid bodies is 422; mapping it to 400 gives clients
one validation status whether the schema or the service caught the problem.

## Decision 3: Where validation lives

**Decision**: Pydantic schemas check *shape and type* with strict types
(`StrictStr`, `StrictInt`, `StrictFloat`, `StrictBool`) and
`extra="forbid"`. The service checks *business rules*: trimmed names are not
empty, length limits, budget range, finite numbers, entry counts.

**Rationale**: strict types stop silent coercion (`"30"` is not a budget,
`true` is not a metric). Python's JSON parser accepts `NaN` and `Infinity`,
so finiteness must be checked explicitly, and that rule belongs to the domain
because it applies however a run is created.

**Alternatives considered**: putting every rule in Pydantic validators was
rejected because it would make the service trust its callers, breaking
constitution IV for any non-HTTP caller.

## Decision 4: Store file layout

**Decision**: `{"schema_version": 1, "runs": [<run record>, ...]}`, written
with two-space indentation and a trailing newline. Timestamps are ISO 8601
UTC with millisecond precision and a `Z` suffix.

**Rationale**: `schema_version` lets a future release migrate the file, and
any other version is treated as corruption (see data-model invariant 6).
Indented JSON makes the store easy to read when debugging.

## Decision 5: Startup and shutdown

**Decision**: `main.build()` loads settings and the store and returns the app.
`main.main()` maps failures to exit codes: `1` for a corrupt store (after
quarantine), `2` for invalid configuration, `0` after a clean shutdown. It logs
`server.started` (with `store_existed` and `run_count`), `server.start_failed`
(with a `reason`), and `server.stopped`.

**Rationale**: splitting `build` from `main` lets tests check startup
behavior without starting a server. Distinct exit codes let a supervisor tell
"fix the config" from "inspect the quarantined store".

## Decision 6: Serializing writes and in-memory state

**Decision**: the service keeps runs in a dictionary guarded by one
`threading.Lock`. Each mutation builds the new state, asks the repository to
save it, and swaps the in-memory state only after the save succeeds. The
repository also serializes `save_all` with its own lock.

**Rationale**: FastAPI runs synchronous endpoints in a thread pool, so
requests can be concurrent even in one process (FR-015). Saving before
swapping means an acknowledged change is always on disk and a failed write
changes nothing.

## Decision 7: Stalled detection and ordering

**Decision**: `is_stalled(run, now)` is
`status == "running" and budget is not None and now - started_at > budget`.
`order_runs(runs, now)` partitions into stalled, other running, and finished,
then sorts by `(started_at, id)`, `(started_at, id)`, and `(finished_at, id)`
descending respectively. `list_runs` reads the clock exactly once.

**Rationale**: a single `now` per request means the stalled flag and the
ordering can never disagree within one response. Breaking ties on `id` makes
the order fully deterministic, which keeps tests stable. The comparison is
strict, so a run exactly at its budget is not yet stalled.

**Alternatives considered**: storing a `stalled` flag was rejected because it
goes stale the moment time passes; it is derived at read time instead.
