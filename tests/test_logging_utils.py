import io
import json
import logging
import math
import sys

import pytest

from minitrain.logging_utils import LOGGER_NAME, JsonFormatter, get_logger, log_event
from tests.conftest import ListHandler


def reject_constant(name: str) -> float:
    raise ValueError(f"non-standard JSON constant {name}")


def test_lines_are_strict_json_even_for_nan() -> None:
    record = logging.makeLogRecord(
        {"msg": "epoch_end", "fields": {"val_loss": math.nan, "best": -math.inf}}
    )
    line = json.loads(JsonFormatter().format(record), parse_constant=reject_constant)
    assert line["val_loss"] == "nan"
    assert line["best"] == "-inf"


def test_every_line_has_timestamp_level_and_event(
    log_capture: tuple[logging.Logger, ListHandler],
) -> None:
    logger, handler = log_capture
    log_event(logger, "training_started", run_id="r", n_train=10)
    [line] = handler.lines
    assert line["event"] == "training_started"
    assert line["level"] == "info"
    assert line["timestamp"].endswith("Z")
    assert line["n_train"] == 10


def test_nested_non_finite_values_are_also_strict_json() -> None:
    record = logging.makeLogRecord(
        {"msg": "x", "fields": {"losses": [1.0, math.nan], "best": {"v": math.inf}}}
    )
    line = json.loads(JsonFormatter().format(record), parse_constant=reject_constant)
    assert line["losses"] == [1.0, "nan"]
    assert line["best"] == {"v": "inf"}


def test_package_logger_follows_the_current_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replacing sys.stderr (as test capture does) must not strand the handler."""
    monkeypatch.setattr(logging.getLogger(LOGGER_NAME), "handlers", [])
    first, second = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stderr", first)
    log_event(get_logger(), "one")
    monkeypatch.setattr(sys, "stderr", second)
    log_event(get_logger(), "two")
    assert '"one"' in first.getvalue()
    assert '"two"' in second.getvalue()
    assert '"two"' not in first.getvalue()
