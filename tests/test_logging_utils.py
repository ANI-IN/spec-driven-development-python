import json
import logging
import math

from minitrain.logging_utils import JsonFormatter, log_event
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
