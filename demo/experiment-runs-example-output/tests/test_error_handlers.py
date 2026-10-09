"""Exception class to HTTP status and body (research.md, Decision 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiment_runs.error_handlers import error_response
from experiment_runs.errors import (
    AppError,
    FieldError,
    NotFoundError,
    RunAlreadyFinishedError,
    StoreCorruptError,
    StoreWriteError,
    ValidationError,
)
from tests.conftest import Json


def body_of(exc: AppError) -> tuple[int, Json]:
    response = error_response(exc)
    parsed: Json = json.loads(bytes(response.body))
    return response.status_code, parsed


def test_validation_errors_are_400_with_details() -> None:
    status, body = body_of(ValidationError("invalid run", [FieldError("name", "x")]))
    assert status == 400
    assert body == {
        "error": "validation_error",
        "message": "invalid run",
        "details": [{"field": "name", "message": "x"}],
    }


@pytest.mark.parametrize(
    ("exc", "status", "error", "message"),
    [
        (NotFoundError("no run with id a"), 404, "not_found", "no run with id a"),
        (RunAlreadyFinishedError("done"), 409, "already_finished", "done"),
        (StoreWriteError("disk full"), 500, "internal_error", "write failed"),
        (
            StoreCorruptError("bad", Path("x")),
            500,
            "internal_error",
            "store is corrupt",
        ),
        (AppError("other"), 500, "internal_error", "unexpected error"),
    ],
)
def test_each_error_class_maps_to_one_status(
    exc: AppError, status: int, error: str, message: str
) -> None:
    assert body_of(exc) == (status, {"error": error, "message": message})


def test_internal_details_never_leak_into_500_bodies() -> None:
    _, body = body_of(StoreWriteError("/secret/path: permission denied"))
    assert "secret" not in json.dumps(body)
