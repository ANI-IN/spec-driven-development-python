"""HTTP contract tests against contracts/openapi.yaml."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeClock, Json

RUN_FIELDS = {
    "id",
    "name",
    "model_type",
    "hyperparameters",
    "time_budget_minutes",
    "status",
    "started_at",
    "finished_at",
    "metrics",
    "stalled",
}
Payload = Callable[..., Json]


def create(client: TestClient, payload: Json) -> Json:
    response = client.post("/runs", json=payload)
    assert response.status_code == 201, response.text
    body: Json = response.json()
    return body


# POST /runs --------------------------------------------------------------------


def test_create_returns_201_and_the_run(
    client: TestClient, create_payload: Payload
) -> None:
    body = create(client, create_payload(time_budget_minutes=30))
    assert set(body) == RUN_FIELDS
    assert body["status"] == "running"
    assert body["stalled"] is False
    assert body["finished_at"] is None
    assert body["metrics"] is None
    assert body["started_at"].endswith("Z")
    assert body["hyperparameters"] == {"learning_rate": 0.05, "epochs": 20}


def test_hyperparameter_types_are_preserved(
    client: TestClient, create_payload: Payload
) -> None:
    params = {"optimizer": "adam", "layers": 3, "dropout": 0.1, "batch_norm": True}
    body = create(client, create_payload(hyperparameters=params))
    assert body["hyperparameters"] == params
    assert isinstance(body["hyperparameters"]["layers"], int)
    assert body["hyperparameters"]["batch_norm"] is True


def test_client_supplied_ids_are_rejected(
    client: TestClient, create_payload: Payload
) -> None:
    response = client.post("/runs", json=create_payload(id="my-own-id"))
    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "   "},
        {"name": None},
        {"model_type": ""},
        {"hyperparameters": {"layers": [64, 32]}},
        {"time_budget_minutes": "30"},
        {"time_budget_minutes": 0},
        {"time_budget_minutes": True},
    ],
)
def test_invalid_create_bodies_are_400(
    client: TestClient, create_payload: Payload, overrides: Json
) -> None:
    response = client.post("/runs", json=create_payload(**overrides))
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["details"]
    assert client.get("/runs").json() == []


def test_missing_required_fields_are_400(client: TestClient) -> None:
    response = client.post("/runs", json={})
    assert response.status_code == 400
    fields = {d["field"] for d in response.json()["details"]}
    assert {"name", "model_type"} <= fields


def test_malformed_json_is_400(client: TestClient) -> None:
    response = client.post(
        "/runs", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["details"][0]["field"] == "body"


def test_nan_in_json_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/runs",
        content=b'{"name": "r", "model_type": "m", "hyperparameters": {"lr": NaN}}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["details"][0]["field"] == "hyperparameters.lr"


# GET /runs ---------------------------------------------------------------------


def test_list_is_empty_at_first(client: TestClient) -> None:
    response = client.get("/runs")
    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_created_runs(client: TestClient, create_payload: Payload) -> None:
    first = create(client, create_payload(name="first"))
    second = create(client, create_payload(name="second"))
    listed = client.get("/runs").json()
    assert {r["id"] for r in listed} == {first["id"], second["id"]}
    assert all(set(r) == RUN_FIELDS for r in listed)


def test_list_flags_and_orders_stalled_runs(
    client: TestClient, clock: FakeClock, create_payload: Payload
) -> None:
    done = create(client, create_payload(name="done"))
    clock.advance(minutes=1)
    slow = create(client, create_payload(name="slow", time_budget_minutes=5))
    clock.advance(minutes=1)
    fresh = create(client, create_payload(name="fresh", time_budget_minutes=600))
    client.post(f"/runs/{done['id']}/finish", json={"metrics": {"auc": 0.8}})
    clock.advance(minutes=10)

    listed = client.get("/runs").json()
    assert [(r["name"], r["stalled"]) for r in listed] == [
        ("slow", True),
        ("fresh", False),
        ("done", False),
    ]
    assert listed[0]["id"] == slow["id"]
    assert listed[1]["id"] == fresh["id"]


# POST /runs/{id}/finish --------------------------------------------------------


def test_finish_returns_200_with_metrics(
    client: TestClient, create_payload: Payload
) -> None:
    run = create(client, create_payload())
    response = client.post(
        f"/runs/{run['id']}/finish", json={"metrics": {"val_auc": 0.91, "epochs": 20}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "finished"
    assert body["metrics"] == {"val_auc": 0.91, "epochs": 20.0}
    assert body["finished_at"].endswith("Z")


def test_finish_twice_is_409(client: TestClient, create_payload: Payload) -> None:
    run = create(client, create_payload())
    client.post(f"/runs/{run['id']}/finish", json={"metrics": {"auc": 0.9}})
    response = client.post(f"/runs/{run['id']}/finish", json={"metrics": {"auc": 1}})
    assert response.status_code == 409
    assert response.json()["error"] == "already_finished"
    assert client.get("/runs").json()[0]["metrics"] == {"auc": 0.9}


@pytest.mark.parametrize(
    "body",
    [{}, {"metrics": {}}, {"metrics": {"auc": "high"}}, {"metrics": {"auc": True}}],
)
def test_invalid_finish_bodies_are_400(
    client: TestClient, create_payload: Payload, body: Json
) -> None:
    run = create(client, create_payload())
    response = client.post(f"/runs/{run['id']}/finish", json=body)
    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"


@pytest.mark.parametrize(
    "bad_id", ["not-a-uuid", "00000000-0000-4000-8000-000000000000"]
)
def test_finish_unknown_id_is_404(client: TestClient, bad_id: str) -> None:
    response = client.post(f"/runs/{bad_id}/finish", json={"metrics": {"auc": 0.5}})
    assert response.status_code == 404
    assert response.json() == {
        "error": "not_found",
        "message": f"no run with id {bad_id}",
    }


# DELETE /runs/{id} -------------------------------------------------------------


def test_delete_is_204_then_404(client: TestClient, create_payload: Payload) -> None:
    run = create(client, create_payload())
    first = client.delete(f"/runs/{run['id']}")
    assert first.status_code == 204
    assert first.content == b""
    assert client.get("/runs").json() == []
    assert client.delete(f"/runs/{run['id']}").status_code == 404


def test_finish_validates_the_body_before_looking_up_the_id(
    client: TestClient,
) -> None:
    response = client.post("/runs/unknown/finish", json={"metrics": {}})
    assert response.status_code == 400


def test_huge_integer_metric_is_400_not_500(
    client: TestClient, create_payload: Payload
) -> None:
    run = create(client, create_payload())
    response = client.post(
        f"/runs/{run['id']}/finish", json={"metrics": {"auc": 10**400}}
    )
    assert response.status_code == 400
    assert response.json()["details"][0]["field"] == "metrics.auc"


def test_field_names_do_not_include_union_branches(
    client: TestClient, create_payload: Payload
) -> None:
    run = create(client, create_payload())
    response = client.post(
        f"/runs/{run['id']}/finish", json={"metrics": {"auc": {"nested": 1}}}
    )
    assert response.status_code == 400
    assert [d["field"] for d in response.json()["details"]] == ["metrics.auc"]


@pytest.mark.parametrize("key", ["int", "str", "float", "bool"])
def test_keys_named_like_types_keep_their_name(
    client: TestClient, create_payload: Payload, key: str
) -> None:
    response = client.post("/runs", json=create_payload(hyperparameters={key: [1]}))
    assert response.status_code == 400
    assert [d["field"] for d in response.json()["details"]] == [
        f"hyperparameters.{key}"
    ]
