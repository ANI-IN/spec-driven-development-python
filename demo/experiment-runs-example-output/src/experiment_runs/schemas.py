"""Wire format: request and response bodies (see contracts/openapi.yaml).

Schemas check *shape and type* only. Business rules such as "name is not just
whitespace" or "metrics are finite" live in the service.
"""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)

from experiment_runs.models import RunStatus, RunView, format_timestamp

ScalarValue = StrictStr | StrictBool | StrictInt | StrictFloat
NumberValue = StrictInt | StrictFloat


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    model_type: StrictStr
    hyperparameters: dict[str, ScalarValue] = {}
    time_budget_minutes: StrictInt | None = None


class FinishRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: dict[str, NumberValue]


class RunResponse(BaseModel):
    id: str
    name: str
    model_type: str
    hyperparameters: dict[str, ScalarValue]
    time_budget_minutes: int | None
    status: RunStatus
    started_at: str
    finished_at: str | None
    metrics: dict[str, float] | None
    stalled: bool

    @classmethod
    def from_view(cls, view: RunView) -> RunResponse:
        run = view.run
        return cls(
            id=run.id,
            name=run.name,
            model_type=run.model_type,
            hyperparameters=dict(run.hyperparameters),
            time_budget_minutes=run.time_budget_minutes,
            status=run.status,
            started_at=format_timestamp(run.started_at),
            finished_at=format_timestamp(run.finished_at) if run.finished_at else None,
            metrics=dict(run.metrics) if run.metrics is not None else None,
            stalled=view.stalled,
        )


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: list[ErrorDetail] | None = None
