from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import main as launcher
from underline_retldc.app import application

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


def test_frozen_launch_roots_use_executable_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "Underline_RETLDC_0_1_0.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert launcher.Launcher_ProjectRoot() == tmp_path.resolve()
    assert application.Application_ProjectRoot() == tmp_path.resolve()


def test_folder_packaging_batch_has_stable_output_contract() -> None:
    script_path = PROJECT_ROOT / "打包_文件夹版.bat"
    script_bytes = script_path.read_bytes()
    assert b"\r\n" in script_bytes
    assert b"\n" not in script_bytes.replace(b"\r\n", b"")
    script = script_bytes.decode("utf-8")
    assert 'set "APP_NAME=Underline_RETLDC_0_1_0"' in script
    assert "--onedir" in script
    assert "--windowed" in script
    assert '"%DIST_DIR%\\plugins"' in script
    assert "robocopy" in script
    assert "/XD __pycache__ .pytest_cache" in script
    assert "/XF *.pyc *.pyo" in script
    assert "%APP_NAME%.exe" in script
    assert "--smoke-test --theme light" in script
    assert "--smoke-test --theme dark" in script
