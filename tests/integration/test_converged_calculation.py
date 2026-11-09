"""Exercise the public calculation/export actions with real imported source bytes."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_gui_workflow import _application, _task_wait, _window

from underline_retldc.app.settings import SettingsService
from underline_retldc.i18n.service import TranslationService


@pytest.fixture
def imported_window(tmp_path, monkeypatch, request):
    _application()
    window = _window(
        TranslationService("en_US"), SettingsService(tmp_path / "settings.ini"), tmp_path,
    )
    errors = []
    monkeypatch.setattr(window, "_error_show", lambda error: errors.append(str(error)))
    path = tmp_path / "synthetic_loadcell.csv"
    path.write_text(
        "time_s,thrust_N\n" + "".join(
            f"{index / 20:.2f},{10 + max(0, 200 * (1 - abs(index / 20 - 3))):.6f}\n"
            for index in range(121)
        ), encoding="utf-8",
    )
    config = {
        "delimiter": ",", "header_row": 1, "data_start_row": 2,
        "time": {"mode": "column", "column": 0, "unit": "s"},
        "columns": [
            {"column": 0, "usage": "time"},
            {"column": 1, "usage": "data", "channel_id": "thrust",
             "quantity": "force", "role": "thrust", "unit": getattr(request, "param", "N")},
        ], "invalid_row_policy": "error",
    }
    window.import_page.set_source_path(path)
    window.import_page.set_parser_id("builtin.parser.generic_delimited")
    parser = window.registry.get("builtin.parser.generic_delimited")
    window.import_page.tabular_mapping_editor.set_preview(
        parser.preview(path, config), config=config,
    )
    window.import_page.parse_button.click()
    _task_wait(window)
    window._regions_store({"pre": [0, 1], "active_test": [2, 4], "post": [5, 6]})
    window._workspace_select("thrust_analysis")
    window._test_errors = errors
    assert not errors
    return window


def _previous_result(window):
    window._processing_apply()
    _task_wait(window)
    window._analysis_calculate()
    _task_wait(window)
    assert window.session.analysis_result is not None
    return window.session.processing_result, window.session.analysis_result


def test_first_toolbar_calculation_processes_and_analyzes(imported_window):
    window = imported_window
    assert window.session.processing_result is None
    assert window.calculate_action.isEnabled()
    window.calculate_action.trigger()
    _task_wait(window)
    assert window.session.processing_result is not None
    assert window.session.analysis_result.metrics["total_impulse_ns"] == pytest.approx(220)
    assert not window._test_errors


@pytest.mark.parametrize("imported_window", ["ADC"], indirect=True)
def test_nonphysical_primary_keeps_relative_analysis_without_physical_export(imported_window):
    window = imported_window
    assert window.calculate_action.isEnabled()
    assert window.calculate_action.text() == "Calculate relative statistics"
    window.calculate_action.trigger()
    _task_wait(window)
    result = window.session.analysis_result
    assert result.metrics["relative_integral"] == pytest.approx(220)
    assert result.metrics["total_impulse_ns"] is None
    assert result.metrics["specific_impulse_s"] is None
    assert result.metadata["physical_force_available"] is False
    assert any(item.code == "analysis.force_unit_not_physical" for item in result.diagnostics)
    window.export_action.trigger()
    assert "None" not in window.export_dialog.result_identity.text()
    assert window.export_dialog.exporter_checks["builtin.exporter.analysis_txt"].isEnabled()
    assert not window.export_dialog.exporter_checks["builtin.exporter.openrocket_eng"].isEnabled()
    assert not window.export_dialog.exporter_checks[
        "builtin.exporter.treediagram_motor"].isEnabled()
    assert not window._test_errors


def test_toolbar_applies_current_processing_draft(imported_window):
    window = imported_window
    old_processing, old_result = _previous_result(window)
    window.process_page.processor_combo.setCurrentIndex(1)
    assert window._processing_draft() is not None
    assert window.session.analysis_result is old_result
    window.calculate_action.trigger()
    _task_wait(window)
    assert window._processing_draft() is None
    assert window.session.processing_result is not old_processing
    assert window.session.analysis_result.metrics["total_impulse_ns"] == pytest.approx(200)
    assert not window._test_errors


def test_analysis_failure_retains_previous_applied_pair(imported_window, monkeypatch):
    window = imported_window
    old_processing, old_result = _previous_result(window)
    window.process_page.processor_combo.setCurrentIndex(1)

    def fail(*_args):
        raise ValueError("injected analyzer failure")

    monkeypatch.setattr(window.registry.get("builtin.analyzer.thrust"), "analyze", fail)
    window.process_page.apply_button.click()
    _task_wait(window)
    assert window.session.processing_result is old_processing
    assert window.session.analysis_result is old_result
    assert window._processing_draft() is not None
    assert window._test_errors and "injected analyzer failure" in window._test_errors[-1]


def test_export_with_draft_discloses_applied_result(imported_window):
    window = imported_window
    _previous_result(window)
    window.process_page.processor_combo.setCurrentIndex(1)
    window.export_action.trigger()
    _application().processEvents()
    dialog = window.export_dialog
    assert dialog.result_notice.isVisible()
    assert "not included" in dialog.result_notice.text()
    assert "synthetic_loadcell.csv" in dialog.result_identity.text()
    assert dialog.return_to_calculation.isVisible()
    dialog.return_to_calculation.click()
    assert not dialog.isVisible()
    assert window.stack.currentWidget() is window.thrust_analysis_page
    assert window._processing_draft() is not None


def test_interval_text_then_export_explains_committed_change_and_recalculation(imported_window):
    window = imported_window
    window.calculate_action.trigger()
    _task_wait(window)
    assert window.session.analysis_result.metrics["total_impulse_ns"] == pytest.approx(220)
    window.show()
    end = window.process_page.interval_editor.region_edits["active_test"][1]
    window.thrust_analysis_page.shell.controls_scroll.ensureWidgetVisible(end)
    end.setFocus()
    end.selectAll()
    QTest.keyClicks(end, "3.95")
    QTest.mouseClick(
        window.toolbar.widgetForAction(window.export_action), Qt.MouseButton.LeftButton)
    _application().processEvents()
    assert window.session.regions["active_test"] == [2.0, 3.95]
    assert window.session.analysis_result is None
    assert window.session.processing_result is None
    assert window._processing_draft() is None
    dialog = window.export_dialog
    assert dialog.result_notice.isVisible()
    assert "current inputs or test interval" in dialog.result_notice.text()
    assert dialog.return_to_calculation.isVisible()
    assert not dialog.exporter_checks["builtin.exporter.treediagram_motor"].isEnabled()
    dialog.return_to_calculation.click()
    assert window.calculate_action.isEnabled()
    window.calculate_action.trigger()
    _task_wait(window)
    assert window.session.analysis_result.metrics["total_impulse_ns"] == pytest.approx(219.25)
    assert not window.analyze_page.applied_notice.isVisible()
    assert not window._test_errors


@pytest.mark.parametrize("cancel", [False, True])
def test_cancel_or_newer_draft_does_not_replace_valid_result(imported_window, monkeypatch, cancel):
    from threading import Event

    window = imported_window
    old_processing, old_result = _previous_result(window)
    window.process_page.processor_combo.setCurrentIndex(1)
    processor = window.registry.get(window.process_page.processor_id())
    original = processor.process
    started, release = Event(), Event()

    def blocked(*args):
        started.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(processor, "process", blocked)
    window.calculate_action.trigger()
    assert started.wait(3)
    if cancel:
        window.cancel_button.click()
    else:
        window.process_page.processor_combo.setCurrentIndex(0)
    release.set()
    _task_wait(window)
    assert window.session.processing_result is old_processing
    assert window.session.analysis_result is old_result
    assert window.process_page.processor_combo.currentIndex() == (1 if cancel else 0)
    assert not window._test_errors


def _number_draft(window, monkeypatch):
    processor = window.registry.get("builtin.processor.vertical_linear_baseline")
    schema = processor.config_schema()
    schema["properties"]["test_setting"] = {
        "type": "number", "minimum": -10, "maximum": 10, "default": 1,
    }
    monkeypatch.setattr(processor, "config_schema", lambda: schema)
    window.process_page.processor_combo.setCurrentIndex(1)
    return window.process_page.processor_form.field_widget("test_setting")


@pytest.mark.parametrize("text, valid", [("2.75", True), ("-", False)])
@pytest.mark.parametrize("button_target", ["toolbar", "panel"])
def test_primary_buttons_consume_unfocused_numeric_text(
    imported_window, monkeypatch, text, valid, button_target,
):
    window = imported_window
    old_processing, old_result = _previous_result(window)
    editor = _number_draft(window, monkeypatch)
    window.show()
    window.thrust_analysis_page.shell.controls_scroll.ensureWidgetVisible(editor)
    editor.setFocus()
    editor.selectAll()
    QTest.keyClicks(editor, text)
    assert editor.lineEdit().text() == text
    button = (window.toolbar.widgetForAction(window.calculate_action)
              if button_target == "toolbar" else window.process_page.apply_button)
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    _task_wait(window)
    if valid:
        assert window.session.processor_config["test_setting"] == 2.75
        assert window.session.analysis_result is not old_result
        assert not window._test_errors
    else:
        assert window.session.processing_result is old_processing
        assert window.session.analysis_result is old_result
        assert window._test_errors
        assert editor.lineEdit().text() == text


def test_locale_and_theme_keep_unfinished_numeric_draft(imported_window, monkeypatch):
    window = imported_window
    editor = _number_draft(window, monkeypatch)
    editor.setFocus()
    editor.selectAll()
    QTest.keyClicks(editor, "-")
    window._locale_select("zh_CN")
    window._theme_select("dark")
    assert window.process_page.processor_form.field_widget("test_setting") is editor
    assert editor.lineEdit().text() == "-"
    assert window.session.processing_result is None


def test_invalid_draft_blocks_save_and_survives_registry_refresh(
    imported_window, monkeypatch, tmp_path,
):
    window = imported_window
    editor = _number_draft(window, monkeypatch)
    editor.setFocus()
    editor.selectAll()
    QTest.keyClicks(editor, "-")
    window._plugins_refresh()
    _task_wait(window)
    assert window.process_page.processor_form.field_widget("test_setting") is editor
    assert editor.lineEdit().text() == "-"
    assert window._processing_has_draft()
    destination = tmp_path / "must_not_save.json"
    window._project_save_path(destination)
    _task_wait(window)
    assert not destination.exists()
    assert editor.lineEdit().text() == "-"
    assert window._test_errors


def test_explicit_previous_result_export_uses_applied_snapshot(imported_window, tmp_path):
    import json

    window = imported_window
    _previous_result(window)
    window.export_dialog.set_output_directory(tmp_path / "exported")
    original = b""
    for expected_draft in (False, True):
        if expected_draft:
            window.process_page.processor_combo.setCurrentIndex(1)
        window.export_action.trigger()
        window.export_dialog.set_selected_exporter_ids(["builtin.exporter.treediagram_motor"])
        window.export_dialog.export_button.click()
        _task_wait(window)
        path = tmp_path / "exported" / "motor.tdmotor.json"
        data = path.read_bytes()
        assert json.loads(data)["metrics"]["total_impulse_ns"] == pytest.approx(220)
        if expected_draft:
            assert data == original
            assert window._processing_draft() is not None
        else:
            original = data
    assert not window._test_errors
