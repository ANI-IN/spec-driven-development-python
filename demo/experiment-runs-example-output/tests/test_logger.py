import io
import json
from datetime import datetime

import pytest

from experiment_runs.logger import EventLogger


def test_writes_exactly_one_json_line_per_event() -> None:
    stream = io.StringIO()
    EventLogger(stream).log("store.write", outcome="success", count=3)
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "store.write"
    assert record["outcome"] == "success"
    assert record["count"] == 3


def test_timestamp_is_iso_8601_utc() -> None:
    stream = io.StringIO()
    EventLogger(stream).log("x")
    stamp = json.loads(stream.getvalue())["timestamp"]
    assert stamp.endswith("Z")
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_unserializable_values_are_stringified() -> None:
    stream = io.StringIO()
    EventLogger(stream).log("x", path=object())
    assert "object" in json.loads(stream.getvalue())["path"]


def test_defaults_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    EventLogger().log("hello")
    assert json.loads(capsys.readouterr().out)["event"] == "hello"
