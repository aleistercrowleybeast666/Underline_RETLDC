"""Scoped defaults are drafts; use real Qt controls and bundled scientific plugins."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from threading import Event

import numpy as np
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit
from test_gui_workflow import _application, _task_wait, _window_with_bound_measurements

from underline_retldc.app.session import AnalysisSession
from underline_retldc.core.motor_parameters import MotorPhysicalParameters
from underline_retldc.gui.schema_form import SchemaForm
from underline_retldc.i18n.service import TranslationService


def _analyzed_window(tmp_path: Path):
    _application()
    window, dataset = _window_with_bound_measurements(tmp_path)
    window.setup_page.set_motor_metadata({
        "motor_designation": "Keep-Motor", "manufacturer": "Keep-Maker", "delay_s": 3,
        "propellant_mass_kg": 0.15, "total_motor_mass_kg": 0.3,
        "diameter_mm": 50, "length_mm": 100,
    })
    window._shared_mass_changed()
    window._regions_store({"pre": [0, 2], "active_test": [3, 7], "post": [8, 10]})
    window.process_page.processor_combo.setCurrentIndex(1)
    window._processing_apply(recalculate=True)
    _task_wait(window)
    assert window.session.analysis_result is not None
    return window, dataset


def test_processing_defaults_cancel_then_apply_preserves_inputs(tmp_path):
    window, dataset = _analyzed_window(tmp_path)
    session = window.session
    initial = session.analysis_result
    initial_processing = session.processing_result
    regions = deepcopy(session.regions)
    bindings = session.project_data.primary_channels
    applied = session.processor_id
    window.process_page.defaults_button.click()
    assert window.process_page.processor_id() == AnalysisSession().processor_id
    assert window._processing_has_draft()
    assert session.processor_id == applied
    assert session.analysis_result is initial
    assert session.processing_result is initial_processing
    assert window.analyze_page.applied_notice.text() == window.translations.translate(
        "process.previous_result")
    window.process_page.restore_button.click()
    assert not window._processing_has_draft()
    assert session.analysis_result is initial
    window.process_page.defaults_button.click()
    window.process_page.apply_button.click()
    _task_wait(window)
    assert session.processor_id is None and not window._processing_has_draft()
    assert session.analysis_result is not initial
    assert session.analysis_result.metrics == {
        key: value for key, value in initial.metrics.items() if key != "equivalent_mass_change_kg"}
    assert session.regions == regions and session.project_data.primary_channels == bindings
    assert session.raw_dataset is dataset
    assert session.thrust_polarity == 1


def test_defaults_during_busy_processing_preserve_applied_result(tmp_path, monkeypatch):
    window, _ = _analyzed_window(tmp_path)
    old_analysis = window.session.analysis_result
    old_processing = window.session.processing_result
    processor = window.registry.get(window.session.processor_id)
    process = processor.process
    started, release = Event(), Event()

    def paused(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return process(*args, **kwargs)

    monkeypatch.setattr(processor, "process", paused)
    window.process_page.advanced_button.click()
    window.process_page.apply_only_button.click()
    try:
        assert started.wait(3)
        window.process_page.defaults_button.click()
        assert window._processing_has_draft()
    finally:
        release.set()
    _task_wait(window)
    assert window.session.analysis_result is old_analysis
    assert window.session.processing_result is old_processing
    assert window.process_page.processor_id() is None
    assert window._processing_has_draft()


@pytest.mark.parametrize("accept", [False, True])
def test_physical_defaults_are_private_and_keep_identity(tmp_path, accept):
    window, dataset = _analyzed_window(tmp_path)
    window._locale_select("zh_CN" if accept else "en_US")
    window._theme_select("dark" if accept else "light")
    metadata = deepcopy(window.session.motor_metadata)
    initial_text = {name: edit.text() for name, edit in window.setup_page.motor_edits.items()}
    original = window.session.analysis_result
    processing = window.session.processing_result
    regions = deepcopy(window.session.regions)
    failures = []

    def interact():
        dialog = QApplication.activeModalWidget()
        try:
            assert isinstance(dialog, QDialog)
            buttons = dialog.findChild(QDialogButtonBox)
            assert dialog.width() <= 980 and dialog.height() <= 640
            assert all(not button.visibleRegion().isEmpty() for button in buttons.buttons())
            restore = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
            assert not restore.autoDefault() and not restore.isDefault()
            buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).click()
            for name, value in MotorPhysicalParameters().to_dict().items():
                edit = dialog.findChild(QLineEdit, "motorDraft_" + name)
                assert edit.text() == ("" if value is None else str(value))
            assert window.session.motor_metadata == metadata
            assert window.session.analysis_result is original
            for name in ("motor_designation", "manufacturer", "delay_s"):
                field = dialog.findChild(QLineEdit, "motorDraft_" + name)
                assert field.text() == initial_text[name]
            button = (QDialogButtonBox.StandardButton.Apply if accept
                      else QDialogButtonBox.StandardButton.Cancel)
            buttons.button(button).click()
        except BaseException as exc:
            failures.append(exc)
            dialog.reject()

    QTimer.singleShot(0, window.setup_page, interact)
    window.setup_page.motor_properties.click()
    assert not failures, failures
    assert window.session.analysis_result is (None if accept else original)
    assert window.session.processing_result is processing
    assert window.session.raw_dataset is dataset
    assert window.session.regions == regions
    if accept:
        assert window.session.motor_parameters == MotorPhysicalParameters()
        assert window.session.motor_metadata == {
            name: metadata[name] for name in ("motor_designation", "manufacturer", "delay_s")}
    else:
        assert window.session.motor_metadata == metadata

    def inspect_reopened():
        dialog = QApplication.activeModalWidget()
        try:
            for name, edit in window.setup_page.motor_edits.items():
                assert dialog.findChild(QLineEdit, "motorDraft_" + name).text() == edit.text()
        except BaseException as exc:
            failures.append(exc)
        finally:
            dialog.reject()

    QTimer.singleShot(0, window.setup_page, inspect_reopened)
    window.setup_page.motor_properties.click()
    assert not failures, failures


def test_enter_in_motor_field_never_restores_defaults(tmp_path):
    window, _ = _analyzed_window(tmp_path)
    original = window.session.motor_parameters
    failures = []

    def press_return():
        dialog = QApplication.activeModalWidget()
        try:
            mass = dialog.findChild(QLineEdit, "motorDraft_propellant_mass_kg")
            mass.setFocus()
            mass.setText("-")
            QTest.keyClick(mass, Qt.Key.Key_Return)
            assert dialog.isVisible() and mass.text() == "-"
            assert window.session.motor_parameters == original
            mass.setText("0.25")
            QTest.keyClick(mass, Qt.Key.Key_Return)
            assert mass.text() == "0.25" and not dialog.isVisible()
        except BaseException as exc:
            failures.append(exc)
        finally:
            if dialog.isVisible():
                dialog.reject()

    QTimer.singleShot(0, window.setup_page, press_return)
    window.setup_page.motor_properties.click()
    assert not failures, failures
    assert window.session.motor_parameters.propellant_mass_kg == 0.25


def test_schema_defaults_preserve_unspecified_nullable_and_external_fields():
    _application()
    form = SchemaForm(TranslationService("en_US"))
    form.set_schema({"properties": {
        "gain": {"type": "number", "default": 1.25},
        "enabled": {"type": "boolean", "default": False},
        "required": {"type": "string"},
        "nullable": {"type": ["number", "null"], "default": None},
        "channel": {"type": "string", "default": "old", "x-ui-source": "source"},
        "unit": {"type": "string", "default": "N"},
    }}, {"gain": 8, "enabled": True, "required": "Keep", "nullable": 4,
         "channel": "Keep-Channel", "unit": "Pa"})
    form.field_widget("gain").lineEdit().setText("-")
    form.restore_defaults(preserve=("unit",))
    assert form.validated_values() == {
        "gain": 1.25, "enabled": False, "required": "Keep", "nullable": 4,
        "channel": "Keep-Channel", "unit": "Pa"}


def test_calibration_defaults_cancel_apply_and_pending_numeric_text(tmp_path, monkeypatch):
    from test_gui_workflow import _window

    from underline_retldc.app.settings import SettingsService

    _application()
    window = _window(TranslationService("en_US"), SettingsService(tmp_path / "settings.ini"),
                     tmp_path)
    source = tmp_path / "loadcell.txt"
    original_bytes = b"0,1\n1,2\n2,3\n3,4\n"
    source.write_bytes(original_bytes)
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id("builtin.parser.tr_f")
    window.import_page.set_parser_config({"time_unit": "s", "invalid_row_policy": "error"})
    window._source_parse()
    _task_wait(window)
    page = window.setup_page
    page.set_calibration_config("builtin.calibration.linear", {
        "parameters": {"K": 2, "B": 3}, "quantity": "force", "unit": "N"})
    page.apply_button.click()
    _task_wait(window)
    initial = window.session.calibrated_dataset
    input_id = page.selected_channel().id
    raw = window.session.raw_dataset.channel(input_id).values.copy()
    applied = deepcopy(window.session.calibration_config)
    page.advanced_button.click()
    page.calibration_defaults.click()
    schema = window.registry.get(page.calibration_id()).parameter_schema()["properties"]
    assert page.calibration_config()["parameters"] == {
        name: schema[name]["default"] for name in ("K", "B")}
    assert window.session.calibration_config == applied
    page.calibration_cancel.click()
    assert page.calibration_config()["parameters"] == applied["parameters"]
    assert window.session.calibrated_dataset is initial
    page.advanced_button.click()
    page.calibration_defaults.click()
    page.apply_button.click()
    _task_wait(window)
    assert window.session.calibration_config["parameters"] == {"K": 1.0, "B": 0.0}
    assert page.selected_channel().id == input_id
    assert page.calibration_config()["quantity"] == "force"
    assert page.calibration_config()["unit"] == "N"
    np.testing.assert_array_equal(window.session.raw_dataset.channel(input_id).values, raw)
    assert source.read_bytes() == original_bytes

    # Apply must consume the exact uncommitted text; locale changes cannot rebuild it.
    page.advanced_button.click()
    gain = page.calibration_form.field_widget("K")
    gain.lineEdit().setText("2.75")
    window._locale_select("zh_CN")
    window._theme_select("dark")
    assert page.calibration_form.field_widget("K") is gain
    assert gain.lineEdit().text() == "2.75"
    page.apply_button.click()
    _task_wait(window)
    assert window.session.calibration_config["parameters"]["K"] == 2.75
    page.advanced_button.click()
    page.calibration_form.field_widget("K").lineEdit().setText("-")
    errors = []
    monkeypatch.setattr(window, "_error_show", lambda error: errors.append(str(error)))
    initial = window.session.calibrated_dataset
    page.apply_button.click()
    assert errors and window._active_task is None
    assert window.session.calibrated_dataset is initial
    assert page.calibration_form.field_widget("K").lineEdit().text() == "-"
