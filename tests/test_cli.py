import pytest

from minitrain.cli import main


def test_prints_a_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--max-epochs", "10"]) == 0
    out = capsys.readouterr().out
    assert "epochs run        10" in out
    assert "best val_loss" in out
    assert "final val_loss" in out


def test_bad_config_exits_with_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--max-epochs", "0"]) == 2
    assert "max_epochs" in capsys.readouterr().err
