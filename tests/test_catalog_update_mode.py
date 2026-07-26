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


def test_auto_mode_is_full_on_monday():
    result = select_mode(day="1")

    assert result.returncode == 0
    assert result.stdout == "full\n"


def test_auto_mode_is_incremental_after_monday():
    result = select_mode(day="2")

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
