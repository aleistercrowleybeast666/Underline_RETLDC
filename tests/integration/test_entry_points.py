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
    executable = tmp_path / "Underline_RETLDC.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert launcher.Launcher_ProjectRoot() == tmp_path.resolve()
    assert application.Application_ProjectRoot() == tmp_path.resolve()


def test_folder_packaging_batch_has_stable_output_contract() -> None:
    script_path = PROJECT_ROOT / "打包.bat"
    script_bytes = script_path.read_bytes()
    assert b"\r\n" in script_bytes
    assert b"\n" not in script_bytes.replace(b"\r\n", b"")
    script = script_bytes.decode("utf-8")
    assert 'set "APP_NAME=Underline_RETLDC"' in script
    assert "--onedir" in script
    assert "--windowed" in script
    assert '"%DIST_DIR%\\plugins"' in script
    assert "robocopy" in script
    assert "/XD __pycache__ .pytest_cache" in script
    assert "/XF *.pyc *.pyo" in script
    assert "%APP_NAME%.exe" in script
    assert "--smoke-test --theme light" in script
    assert "--smoke-test --theme dark" in script


def test_packaging_preflight_runs_before_pyinstaller_and_fails_fast() -> None:
    script = (PROJECT_ROOT / "打包.bat").read_text(encoding="utf-8")
    pytest_index = script.index('"%VENV_PYTHON%" -m pytest')
    ruff_index = script.index('"%VENV_PYTHON%" -m ruff check .')
    build_index = script.index('"%VENV_PYTHON%" -m PyInstaller')
    assert pytest_index < ruff_index < build_index
    for start, end in ((pytest_index, ruff_index), (ruff_index, build_index)):
        assert "if errorlevel 1 (" in script[start:end]
        assert "exit /b 1" in script[start:end]


@pytest.mark.parametrize("available_size", [(1536, 816), (1280, 680)])
def test_initial_native_frame_fits_available_logical_screen(tmp_path, available_size) -> None:
    from PySide6.QtCore import QRect
    from test_gui_workflow import _application, _window

    from underline_retldc.app.settings import SettingsService
    from underline_retldc.i18n.service import TranslationService

    app = _application()
    window = _window(
        TranslationService("en_US"), SettingsService(tmp_path / "settings.ini"), tmp_path)
    window.show()
    window.move(100, 80)
    app.processEvents()
    available = QRect(0, 0, *available_size)
    assert not available.contains(window.frameGeometry())
    application.Application_ConstrainInitialGeometry(window, available)
    app.processEvents()
    assert available.contains(window.frameGeometry())
    export_button = window.toolbar.widgetForAction(window.export_action)
    assert window.rect().contains(export_button.mapTo(window, export_button.rect().bottomRight()))


def test_initial_geometry_preserves_valid_position_and_later_view_changes(tmp_path) -> None:
    from PySide6.QtCore import QRect
    from test_gui_workflow import _application, _window

    from underline_retldc.app.settings import SettingsService
    from underline_retldc.i18n.service import TranslationService

    app = _application()
    window = _window(
        TranslationService("en_US"), SettingsService(tmp_path / "settings.ini"), tmp_path)
    window.show()
    window.resize(980, 600)
    window.move(20, 20)
    app.processEvents()
    available = QRect(0, 0, 1280, 680)
    before = window.frameGeometry()
    assert available.contains(before)
    application.Application_ConstrainInitialGeometry(window, available)
    assert window.frameGeometry() == before
    window._theme_select("dark")
    window._locale_select("zh_CN")
    app.processEvents()
    assert window.frameGeometry() == before
