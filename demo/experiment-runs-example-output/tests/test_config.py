from pathlib import Path

import pytest

from experiment_runs.config import Settings, load_settings
from experiment_runs.errors import ValidationError


def test_defaults() -> None:
    assert load_settings({}) == Settings(
        host="127.0.0.1", port=8000, store_path=Path("data/runs.json")
    )


def test_environment_overrides() -> None:
    settings = load_settings(
        {"HOST": "0.0.0.0", "PORT": "9001", "STORE_PATH": "/tmp/r.json"}
    )
    assert settings == Settings(
        host="0.0.0.0", port=9001, store_path=Path("/tmp/r.json")
    )


def test_empty_values_fall_back_to_defaults() -> None:
    assert load_settings({"PORT": "", "STORE_PATH": ""}) == Settings()


@pytest.mark.parametrize(
    "port", ["abc", "0", "65536", "-1", "80.5", "²", "٨٠", "9" * 5000]
)
def test_invalid_port_is_a_validation_error(port: str) -> None:
    with pytest.raises(ValidationError) as caught:
        load_settings({"PORT": port})
    assert caught.value.details[0].field == "PORT"


def test_a_directory_store_path_is_invalid_config(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as caught:
        load_settings({"STORE_PATH": str(tmp_path)})
    assert caught.value.details[0].field == "STORE_PATH"
