"""HTTP routes: parse the request, call the service, shape the response.

No business logic and no storage access here (constitution principle IV).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from experiment_runs.schemas import CreateRunRequest, FinishRunRequest, RunResponse
from experiment_runs.service import RunService

router = APIRouter(prefix="/runs")


def get_service(request: Request) -> RunService:
    service: RunService = request.app.state.run_service
    return service


ServiceDep = Annotated[RunService, Depends(get_service)]


@router.post("", status_code=status.HTTP_201_CREATED, name="createRun")
def create_run(body: CreateRunRequest, service: ServiceDep) -> RunResponse:
    view = service.create(
        name=body.name,
        model_type=body.model_type,
        hyperparameters=body.hyperparameters,
        time_budget_minutes=body.time_budget_minutes,
    )
    return RunResponse.from_view(view)


@router.get("", name="listRuns")
def list_runs(service: ServiceDep) -> list[RunResponse]:
    return [RunResponse.from_view(view) for view in service.list_runs()]


@router.post("/{run_id}/finish", name="finishRun")
def finish_run(run_id: str, body: FinishRunRequest, service: ServiceDep) -> RunResponse:
    view = service.finish(run_id, body.metrics)
    return RunResponse.from_view(view)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT, name="deleteRun")
def delete_run(run_id: str, service: ServiceDep) -> Response:
    service.delete(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
