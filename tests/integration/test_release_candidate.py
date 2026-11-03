"""User-visible release regressions. Use real plugin discovery and Qt controls."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox
from test_gui_workflow import (
    PROJECT_ROOT,
    _application,
    _task_wait,
    _window_with_bound_measurements,
)


def test_data_cli_without_qt(tmp_path: Path):
    (tmp_path / "sitecustomize.py").write_text(
        "import sys\nclass Guard:\n def find_spec(self, name, *args):\n"
        "  if name.split('.')[0] in ('PySide6','pyqtgraph'): raise ImportError('Qt unavailable')\n"
        "sys.meta_path.insert(0, Guard())\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "underline_retldc.cli",
            "export",
            "tests/fixtures/motor_test_package/v1/synthetic_positive.retldc.json",
            str(tmp_path / "engine.tdmotor.json"),
        ],
        cwd=PROJECT_ROOT,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(tmp_path), str(PROJECT_ROOT / "src"))),
        },
        capture_output=True,
        text=True,
        timeout=35,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "engine.tdmotor.json").is_file()


def test_export_mass_and_processing_draft(tmp_path, monkeypatch):
    _application()
    window, _ = _window_with_bound_measurements(tmp_path)
    window.setup_page.motor_edits["propellant_mass_kg"].setText("0.15")
    window._regions_store({"pre": [0, 2], "active_test": [3, 7], "post": [8, 10]})
    window._processing_apply()
    _task_wait(window)
    window._analysis_calculate()
    _task_wait(window)
    initial = window.session.analysis_result
    assert initial is not None
    window._export_dialog_show()
    assert window.export_dialog.eng_edits["propellant_mass_kg"].isReadOnly()
    window.export_dialog.set_selected_exporter_ids(["builtin.exporter.analysis_txt"])
    _application().processEvents()
    assert window.export_dialog.edit_project_parameters.isVisible()
    assert "0.15" in window.export_dialog.project_motor_summary.text()
    window.export_dialog.reject()
    window.process_page.processor_combo.setCurrentIndex(1)
    assert window._processing_draft() is not None
    assert window.session.analysis_result is initial
    assert window._project_document_create().processing_draft is not None
    window._processing_restore()
    assert window._processing_draft() is None
    assert window.session.analysis_result is initial
    window.setup_page.motor_edits["propellant_mass_kg"].setText("0.30")
    assert window.session.analysis_result is None
    window._analysis_calculate()
    _task_wait(window)
    assert window.session.analysis_result.metrics["specific_impulse_s"] == (
        initial.metrics["specific_impulse_s"] / 2
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Discard)


def test_mass_replay_and_unsaved_guard(tmp_path, monkeypatch):
    import json
    import shutil

    from PySide6.QtWidgets import QFileDialog
    from test_gui_workflow import _window

    from underline_retldc.app.settings import SettingsService
    from underline_retldc.core.project import Project_Load
    from underline_retldc.i18n.service import TranslationService

    _application()
    fixtures = PROJECT_ROOT / "tests/fixtures/motor_test_package/v1"
    for name in ("synthetic.csv", "synthetic_positive.retldc.json"):
        shutil.copyfile(fixtures / name, tmp_path / name)
    path = tmp_path / "synthetic_positive.retldc.json"
    window = _window(
        TranslationService("en_US"), SettingsService(tmp_path / "settings.ini"), tmp_path
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    errors = []
    monkeypatch.setattr(window, "_error_show", lambda error: errors.append(str(error)))
    window._project_open_dialog()
    _task_wait(window)
    session = window.session
    assert session.analysis_result.metrics["total_impulse_ns"] == pytest.approx(200)
    assert session.analysis_result.metrics["specific_impulse_s"] == pytest.approx(
        135.96216, rel=1e-5
    )
    saved_key = window._saved_key
    window._theme_select("dark")
    window._locale_select("zh_CN")
    assert window._project_key() == saved_key
    window.setup_page.motor_edits["propellant_mass_kg"].setText("0.30")
    assert session.analysis_result is None
    window._analysis_calculate()
    _task_wait(window)
    assert session.analysis_result.metrics["specific_impulse_s"] == pytest.approx(
        67.98108, rel=1e-5
    )
    window.process_page.processor_combo.setCurrentIndex(1)
    assert window._processing_draft()
    # Save/Cancel/failed save each leaves the original session intact.
    monkeypatch.setattr(window, "_leave_decision", lambda: QMessageBox.StandardButton.Cancel)
    window._project_new()
    window._project_open_dialog()
    assert window.session is session
    monkeypatch.setattr(window, "_leave_decision", lambda: QMessageBox.StandardButton.Save)
    session.project_path = None
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    window._project_new()
    assert window.session is session
    bad = tmp_path / "not-a-directory"
    bad.write_text("original", encoding="utf8")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(bad / "x"), ""))
    window._project_new()
    _task_wait(window)
    assert errors and window.session is session
    destination = tmp_path / "saved.retldc.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(destination), ""))
    window._project_new()
    _task_wait(window)
    assert window.session is not session
    doc = Project_Load(destination)
    assert doc.processing_draft and not doc.processors
    assert doc.workflow_state["analyzed"] and doc.motor_metadata["propellant_mass_kg"] == 0.30
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(destination), ""))
    window._project_open_dialog()
    _task_wait(window)
    assert window._processing_draft() == doc.processing_draft
    assert window.session.analysis_result.metrics["specific_impulse_s"] == pytest.approx(
        67.98108, rel=1e-5
    )
    assert json.loads(destination.read_text(encoding="utf8"))["processing_draft"]
    window._processing_restore()
    old_regions = dict(window.session.regions)
    window._regions_store({**old_regions, "active_test": [0.6, 2.4]})
    assert window.session.analysis_result is None
    window._science_undo()
    _task_wait(window)
    assert window.session.regions == old_regions
    assert window.session.analysis_result is not None
    assert len(errors) == 1


def test_busy_refresh_keeps_running_implementation(tmp_path, monkeypatch):
    from threading import Event

    _application()
    window, _ = _window_with_bound_measurements(tmp_path)
    started, release = Event(), Event()
    original = window.registry
    calculator = original.get("builtin.analyzer.thrust")

    def work(context):
        started.set()
        assert release.wait(5)
        return calculator

    received = []
    window._task_start("fixture worker", work, received.append)
    assert started.wait(3)
    window._plugins_refresh()
    assert window._refresh_pending and window.registry is original
    release.set()
    _task_wait(window, timeout_ms=12000)
    assert received == [calculator]
    assert window.registry is not original
    assert window.registry.get("builtin.analyzer.thrust") is calculator


def test_raw_property_cancel_revokes_pending_calibration(tmp_path, monkeypatch):
    from threading import Event

    from test_gui_workflow import _window

    from underline_retldc.app.settings import SettingsService
    from underline_retldc.i18n.service import TranslationService

    app = _application()
    window = _window(
        TranslationService("en_US"), SettingsService(tmp_path / "settings.ini"), tmp_path
    )
    window.resize(980, 640)
    window.show()
    source = tmp_path / "loadcell.txt"
    source.write_text("0,1\n1,2\n2,3\n3,4\n", encoding="utf8")
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id("builtin.parser.tr_f")
    window.import_page.set_parser_config({"time_unit": "s", "invalid_row_policy": "error"})
    window._source_parse()
    _task_wait(window)
    app.processEvents()
    button = window.setup_page.input_help
    assert button.visibleRegion().contains(button.rect().center())
    button.click()
    assert window.setup_page.calibration_dialog.isVisible()
    initial = window.session.calibrated_dataset
    window.setup_page.set_calibration_config(
        "builtin.calibration.linear",
        {"parameters": {"K": 2.0, "B": 0.0}, "quantity": "force", "unit": "N"},
    )
    started, release = Event(), Event()
    model = window.registry.get("builtin.calibration.linear")
    evaluate = model.evaluate

    def pause(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return evaluate(*args, **kwargs)

    monkeypatch.setattr(model, "evaluate", pause)
    window.setup_page.apply_button.click()
    try:
        assert started.wait(3)
        window.setup_page.calibration_dialog.reject()
    finally:
        release.set()
    _task_wait(window)
    assert window.session.calibrated_dataset is initial
    assert window.setup_page.calibration_id() == "builtin.calibration.identity"
    assert window._input_blocker() is not None
