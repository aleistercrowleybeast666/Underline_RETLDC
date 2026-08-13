from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "entry",
    (
        PROJECT_ROOT / "main.py",
        PROJECT_ROOT / "src" / "underline_retldc" / "__main__.py",
    ),
)
def test_python_file_entry_points_start_gui(entry: Path) -> None:
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [sys.executable, "-u", str(entry), "--smoke-test"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
