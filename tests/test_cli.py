import pytest

from minitrain.cli import main


def test_prints_a_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--max-epochs", "10"]) == 0
    out = capsys.readouterr().out
    assert "epochs run        10" in out
    assert "stop reason       max_epochs" in out
    assert "best val_loss" in out
    assert "final val_loss" in out
    assert "returned model    last epoch (10)" in out


def test_bad_config_exits_with_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--max-epochs", "0"]) == 2
    assert "max_epochs" in capsys.readouterr().err


def test_ac13_early_stopping_reports_why_it_stopped_and_what_it_returned(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--early-stopping"]) == 0
    out = capsys.readouterr().out
    assert "epochs run        27" in out
    assert "stop reason       patience_exhausted" in out
    assert "returned model    best epoch (21)" in out


@pytest.mark.parametrize(
    ("flags", "epochs"),
    [
        (["--patience", "3"], "epochs run        20"),
        (["--min-delta", "0"], "epochs run        31"),
        (["--start-from-epoch", "40"], "epochs run        50"),
    ],
)
def test_ac13_tuning_flags_change_when_the_run_stops(
    capsys: pytest.CaptureFixture[str], flags: list[str], epochs: str
) -> None:
    assert main(["--early-stopping", *flags]) == 0
    assert epochs in capsys.readouterr().out


def test_ac13_tuning_flags_without_early_stopping_exit_with_code_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--patience", "3"]) == 2
    assert (
        "--patience: these settings require --early-stopping" in capsys.readouterr().err
    )


def test_ac8_bad_early_stopping_settings_exit_with_code_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--early-stopping", "--patience", "0"]) == 2
    assert "patience" in capsys.readouterr().err
