"""App assembly: error mapping, request logging, and disabled endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from experiment_runs.app import create_app
from experiment_runs.errors import StoreWriteError
from experiment_runs.service import RunService
from tests.conftest import Json, LogCapture
from tests.test_routes import Payload, create


def test_write_failures_are_500(
    service: RunService,
    logs: LogCapture,
    create_payload: Payload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise StoreWriteError("disk full")

    monkeypatch.setattr(service, "create", fail)
    client = TestClient(create_app(service, logs.logger))
    response = client.post("/runs", json=create_payload())
    assert response.status_code == 500
    assert response.json() == {"error": "internal_error", "message": "write failed"}


def test_unexpected_errors_are_500_and_logged(
    service: RunService, logs: LogCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(service, "list_runs", boom)
    client = TestClient(create_app(service, logs.logger), raise_server_exceptions=False)
    response = client.get("/runs")
    assert response.status_code == 500
    assert response.json() == {"error": "internal_error", "message": "unexpected error"}
    assert logs.events("request.unexpected_error")[0]["error_class"] == "RuntimeError"
    assert logs.events("request.error")[0]["outcome"] == "RuntimeError"


def test_every_request_logs_one_outcome_line(
    client: TestClient, logs: LogCapture, create_payload: Payload
) -> None:
    run = create(client, create_payload())
    client.get("/runs")
    client.post(f"/runs/{run['id']}/finish", json={"metrics": {"auc": 0.9}})
    client.delete("/runs/missing")
    client.delete(f"/runs/{run['id']}")

    lines = [
        line
        for line in logs.lines()
        if line["event"] in ("request.ok", "request.error")
    ]
    assert [(line["operation"], line["outcome"]) for line in lines] == [
        ("createRun", "success"),
        ("listRuns", "success"),
        ("finishRun", "success"),
        ("deleteRun", "NotFoundError"),
        ("deleteRun", "success"),
    ]
    assert lines[2]["run_id"] == run["id"]
    assert all("timestamp" in line and "status" in line for line in lines)


def test_no_docs_metrics_or_health_endpoints(client: TestClient) -> None:
    for path in ("/docs", "/openapi.json", "/metrics", "/health"):
        assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "status", "error"),
    [
        ("GET", "/nope", 404, "not_found"),
        ("PUT", "/runs", 405, "method_not_allowed"),
        ("GET", "/runs/some-id", 405, "method_not_allowed"),
    ],
)
def test_framework_errors_use_the_error_shape(
    client: TestClient,
    logs: LogCapture,
    method: str,
    path: str,
    status: int,
    error: str,
) -> None:
    response = client.request(method, path)
    assert response.status_code == status
    body: Json = response.json()
    assert body["error"] == error
    assert set(body) == {"error", "message"}
    [line] = logs.events("request.error")
    assert line["operation"] == "unknown"


def test_405_keeps_the_allow_header(client: TestClient) -> None:
    response = client.put("/runs")
    assert response.status_code == 405
    assert "POST" in response.headers["allow"]
