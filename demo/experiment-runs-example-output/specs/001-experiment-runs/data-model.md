# Data Model: Experiment Runs API

**Feature**: 001-experiment-runs
**Date**: 2026-10-10

## Entity: Run

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string (UUID v4) | yes | Server-assigned, canonical hyphenated form. Never changes. |
| `name` | string | yes | Trimmed; 1 to 200 characters. |
| `model_type` | string | yes | Trimmed; 1 to 100 characters. For example `xgboost`, `mlp`, `logistic_regression`. |
| `hyperparameters` | object: string → string, integer, float, or boolean | yes (may be `{}`) | At most 50 entries; keys 1 to 100 non-blank characters; floats finite. |
| `time_budget_minutes` | integer or null | no | 1 to 10,080 when present. |
| `status` | `"running"` or `"finished"` | yes | Starts as `"running"`. |
| `started_at` | timestamp (UTC) | yes | Set by the server at creation. |
| `finished_at` | timestamp (UTC) or null | no | Set by the server at finish. |
| `metrics` | object: string → finite number, or null | no | 1 to 50 entries; set once at finish. |

### Derived at read time (never stored)

| Field | Rule |
|---|---|
| `stalled` | `status == "running"` and `time_budget_minutes` is not null and `now - started_at > time_budget_minutes` (strictly greater). `now` is read once per list request, in UTC. |

### State transitions

```text
          create                 finish(metrics)
  (none) ────────▶ running ─────────────────────▶ finished
                     │                               │
                     │ delete                        │ delete
                     ▼                               ▼
                  (gone)                           (gone)

  finish on a finished run → RunAlreadyFinishedError (409); nothing changes
  finish or delete on an unknown id → NotFoundError (404); nothing changes
```

### Invariants

1. `id` values are unique within the store.
2. `status == "finished"` if and only if both `finished_at` and `metrics` are
   present.
3. `metrics`, once set, never change (FR-006).
4. Every number in `hyperparameters` and `metrics` is finite.
5. Every timestamp carries a timezone and is stored in UTC.
6. The store document has `schema_version == 1`. Any other value, or any
   record that breaks invariants 1 to 5, makes the whole store corrupt: it is
   quarantined at startup (FR-013).

## Entity: Run Store

The single persistent document:

```json
{
  "schema_version": 1,
  "runs": [
    {
      "id": "5b1f2a8e-1c2d-4e3f-8a9b-0c1d2e3f4a5b",
      "name": "baseline",
      "model_type": "xgboost",
      "hyperparameters": {"max_depth": 6, "eta": 0.3},
      "time_budget_minutes": 30,
      "status": "finished",
      "started_at": "2026-10-01T09:00:00.000Z",
      "finished_at": "2026-10-01T09:12:00.000Z",
      "metrics": {"val_auc": 0.91, "val_loss": 0.33}
    }
  ]
}
```

## Validation Rules

| Input | Rule | Failure |
|---|---|---|
| Create body | Only `name`, `model_type`, `hyperparameters`, `time_budget_minutes`; strict types | 400 `validation_error` |
| `name`, `model_type` | Not blank after trimming; length limits above | 400, field named in `details` |
| `hyperparameters` | Scalar values only; limits above; no `NaN`/`Infinity` | 400 |
| `time_budget_minutes` | Integer (not boolean) from 1 to 10,080 | 400 |
| Finish body | Only `metrics`; values are integers or floats (not booleans) | 400 |
| `metrics` | 1 to 50 entries; finite values; keys 1 to 100 non-blank characters | 400 |
| Path `run_id` | Looked up as given; malformed ids are simply unknown | 404 `not_found` |
