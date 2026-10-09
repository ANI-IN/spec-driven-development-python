from pathlib import Path

import pytest

from experiment_runs.errors import (
    AppError,
    FieldError,
    NotFoundError,
    RunAlreadyFinishedError,
    StoreCorruptError,
    StoreWriteError,
    ValidationError,
)


@pytest.mark.parametrize(
    "error",
    [
        ValidationError("bad"),
        NotFoundError("missing"),
        RunAlreadyFinishedError("done"),
        StoreCorruptError("corrupt", Path("x.corrupt")),
        StoreWriteError("write"),
    ],
)
def test_every_error_is_an_app_error(error: AppError) -> None:
    assert isinstance(error, AppError)
    assert error.message == str(error)


def test_validation_error_keeps_its_details() -> None:
    details = [FieldError("name", "must not be empty")]
    assert ValidationError("invalid", details).details == details
    assert ValidationError("invalid").details == []


def test_store_corrupt_error_records_the_quarantine_path() -> None:
    assert StoreCorruptError("c", Path("a/b")).quarantined_path == Path("a/b")
