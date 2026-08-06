import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run-catalog-update.sh"


def select_mode(*args: str, day: str = "2") -> subprocess.CompletedProcess[str]:
    environment = os.environ | {"CATALOG_UPDATE_DAY": day}
    return subprocess.run(
        [str(SCRIPT), "--print-mode", *args],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


@pytest.mark.parametrize("day", ["1", "4"])
def test_auto_mode_is_full_on_monday_and_thursday(day: str):
    result = select_mode(day=day)

    assert result.returncode == 0
    assert result.stdout == "full\n"


@pytest.mark.parametrize("day", ["2", "3", "5", "6", "7"])
def test_auto_mode_is_incremental_on_non_reconciliation_days(day: str):
    result = select_mode(day=day)

    assert result.returncode == 0
    assert result.stdout == "incremental\n"


@pytest.mark.parametrize("requested", ["incremental", "full"])
def test_explicit_mode_overrides_auto_schedule(requested: str):
    result = select_mode(requested, day="1")

    assert result.returncode == 0
    assert result.stdout == f"{requested}\n"


@pytest.mark.parametrize(
    ("args", "day"),
    [(("unknown",), "2"), ((), "0")],
)
def test_invalid_mode_or_weekday_fails_before_network_work(args: tuple[str, ...], day: str):
    result = select_mode(*args, day=day)

    assert result.returncode == 2
