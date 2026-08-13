from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHeaderView, QMessageBox, QStyle

from underline_retldc.app.settings import THEME_DARK, THEME_LIGHT, SettingsService
from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project import (
    PluginReference,
    Project_Load,
    Project_Save,
    Project_SourceHash,
    ProjectDocument,
)
from underline_retldc.core.regions import BurnCandidate
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.gui.pages.export_page import ExportDialog, ExportOption
from underline_retldc.gui.theme import RetldcApplicationStyle, Theme_Apply, Theme_Current
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugin_api.common import TaskContext

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _task_wait(window: MainWindow, timeout_ms: int = 5000) -> None:
    elapsed = 0
    while window._active_task is not None and elapsed < timeout_ms:
        _application().processEvents()
        QTest.qWait(10)
        elapsed += 10
    assert window._active_task is None


def _window(
    translations: TranslationService,
    settings: SettingsService,
    temporary_root: Path,
) -> MainWindow:
    return MainWindow(
        translations,
        settings,
        project_root=temporary_root,
        bundled_plugin_directory=PROJECT_ROOT / "plugins",
        user_plugin_directory=temporary_root / "user_plugins",
    )


def _external_plugin_write(
    root: Path,
    category: str,
    folder: str,
    manifest: dict,
    code: str,
) -> None:
    directory = root / category / folder
    directory.mkdir(parents=True)
    (directory / "plugin.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (directory / "plugin.py").write_text(code, encoding="utf-8")


def test_gui_initializes_two_workspaces_and_switches_locale(tmp_path: Path) -> None:
    app = _application()
    settings = SettingsService(tmp_path / "settings.ini")
    translations = TranslationService("zh_CN")
    window = _window(translations, settings, tmp_path)
    assert window.stack.count() == 2
    assert window.navigation.item(0).text() == "项目"
    assert window.navigation.item(1).text() == "推力分析"
    assert window.project_page.analysis_button.text() == "进入推力分析 →"
    window.project_page.analysis_button.click()
    assert window.stack.currentWidget() is window.thrust_analysis_page
    window._locale_select("en_US")
    app.processEvents()
    assert window.navigation.item(0).text() == "Project"
    assert window.navigation.item(1).text() == "Thrust Analysis"
    assert window.plugins_page.refresh_button.text() == "Refresh"
    assert window.settings_page.language_group.title() == "Language"
    assert window.export_dialog.windowTitle() == "Export…"
    assert settings.locale() == "en_US"
    combo_palette = window.language_combo.palette()
    assert combo_palette.color(QPalette.ColorRole.Button).lightness() > 220
    assert combo_palette.color(QPalette.ColorRole.Text).lightness() < 64
    window.show()
    app.processEvents()
    assert window.language_combo.width() >= 100
    window.language_combo.setCurrentIndex(1)
    window.language_combo.showPopup()
    app.processEvents()
    combo_bottom = window.language_combo.mapToGlobal(
        QPoint(0, window.language_combo.height())
    ).y()
    assert window.language_combo.view().window().geometry().top() >= combo_bottom
    assert window.language_combo.view().verticalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    window.language_combo.hidePopup()

    long_combo = StandardComboBox(window)
    long_combo.addItems([str(index) for index in range(11)])
    long_combo.move(300, 300)
    long_combo.resize(180, 28)
    long_combo.show()
    long_combo.showPopup()
    app.processEvents()
    assert long_combo.maxVisibleItems() == 10
    assert long_combo.view().verticalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert long_combo.view().verticalScrollBar().isVisible()
    expected_popup_height = sum(
        long_combo.view().sizeHintForRow(index) for index in range(10)
    ) + long_combo.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
    assert long_combo.view().window().height() <= expected_popup_height
    long_combo.hidePopup()
    long_combo.deleteLater()

    window._export_dialog_show()
    app.processEvents()
    assert window.export_dialog.isVisible()
    assert len(window.export_dialog.exporter_checks) == 5
    assert all(
        not checkbox.isEnabled()
        for checkbox in window.export_dialog.exporter_checks.values()
    )
    assert all(
        window.export_dialog.required_analysis_ids(plugin_id)
        == ("builtin.analyzer.thrust",)
        for plugin_id in window.export_dialog.exporter_checks
    )
    window.export_dialog.reject()
    window.export_dialog.set_output_locale("zh_CN")
    assert window.export_dialog.export_filename("builtin.exporter.csv") == (
        "processed_thrust_ZH.csv"
    )
    assert window.export_dialog.export_filename("builtin.exporter.thrust_png") == (
        "thrust_curve_ZH.png"
    )
    assert window.export_dialog.export_filename("builtin.exporter.openrocket_eng") == (
        "motor.eng"
    )
    window.export_dialog.set_output_locale("en_US")
    assert window.export_dialog.export_filename("builtin.exporter.analysis_txt") == (
        "analysis_summary_EN.txt"
    )
    assert "expected_propellant_mass_kg" not in window.setup_page.motor_edits
    window.close()
    app.processEvents()


def test_runtime_theme_header_and_settings_stay_synchronized(tmp_path: Path) -> None:
    app = _application()
    settings = SettingsService(tmp_path / "settings.ini")
    window = _window(TranslationService("zh_CN"), settings, tmp_path)
    window.show()
    app.processEvents()

    assert window.language_label.text() == "语言"
    assert window.version_label.text() == "版本 0.1.0"
    assert window.credit_label.text() == "辰星引力开发"
    assert window.theme_button.text() == "深色模式"
    assert window.settings_page.theme_combo.currentData() == THEME_LIGHT
    assert Theme_Current(app) == THEME_LIGHT
    # Qt wraps the configured proxy in QStyleSheetStyle while a global style
    # sheet is active; verify the retained base style instead of that wrapper.
    assert isinstance(app._retldc_application_style, RetldcApplicationStyle)

    window.theme_button.click()
    app.processEvents()
    assert settings.theme() == THEME_DARK
    assert Theme_Current(app) == THEME_DARK
    assert window.settings_page.theme_combo.currentData() == THEME_DARK
    assert window.theme_button.text() == "浅色模式"
    assert app.palette().color(QPalette.ColorRole.Window).lightness() < 60
    assert window.plugins_dialog.palette().color(QPalette.ColorRole.Window).lightness() < 60
    assert window.process_page.plot_widget.backgroundBrush().color().name() == "#0b1220"
    window.language_combo.showPopup()
    app.processEvents()
    assert window.language_combo.view().palette().color(QPalette.ColorRole.Base).lightness() < 80
    window.language_combo.hidePopup()

    window._locale_select("en_US")
    app.processEvents()
    assert window.language_label.text() == "Language"
    assert window.version_label.text() == "Version 0.1.0"
    assert window.credit_label.text() == "By CXYL"
    assert window.theme_button.text() == "Light Mode"

    light_index = window.settings_page.theme_combo.findData(THEME_LIGHT)
    window.settings_page.theme_combo.setCurrentIndex(light_index)
    app.processEvents()
    assert settings.theme() == THEME_LIGHT
    assert Theme_Current(app) == THEME_LIGHT
    assert window.theme_button.text() == "Dark Mode"
    assert app.palette().color(QPalette.ColorRole.Window).lightness() > 220

    Theme_Apply(app, "invalid")
    assert Theme_Current(app) == THEME_LIGHT
    window.close()
    app.processEvents()


def test_gui_plugin_combos_schema_forms_and_burn_candidates(tmp_path: Path) -> None:
    app = _application()
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.show()
    app.processEvents()
    parser_ids = {
        window.import_page.parser_combo.itemData(index)
        for index in range(window.import_page.parser_combo.count())
    }
    assert "builtin.parser.tr_f" in parser_ids
    assert window.import_page.selected_parser_id() == "builtin.parser.tr_f"
    app.processEvents()
    assert window.import_page.selected_parser_id() == "builtin.parser.tr_f"
    assert set(window.import_page.configuration_form.field_names) == {
        "delimiter",
        "time_unit",
        "invalid_row_policy",
    }
    window.import_page.set_parser_id(None)
    app.processEvents()
    assert window.import_page.selected_parser_id() is None
    assert window.import_page.configuration_form.field_names == ()
    window.import_page.set_parser_id("builtin.parser.tr_f")
    app.processEvents()
    assert window.import_page.selected_parser_id() == "builtin.parser.tr_f"
    assert "delimiter" in window.import_page.configuration_form.field_names
    probe_source = tmp_path / "probe.txt"
    probe_source.write_text("0,0\n0.1,1\n0.2,0\n", encoding="utf-8")
    window.import_page.set_source_path(probe_source)
    window.import_page.set_parser_id(None)
    window._parser_detect()
    _task_wait(window)
    assert window.import_page.selected_parser_id() == "builtin.parser.tr_f"
    assert "delimiter" in window.import_page.configuration_form.field_names
    recommendation_header = window.import_page.recommendation_table.horizontalHeader()
    assert recommendation_header.sectionResizeMode(0) is QHeaderView.ResizeMode.Stretch
    assert recommendation_header.sectionResizeMode(1) is QHeaderView.ResizeMode.Stretch
    recommendation_widths = (
        recommendation_header.sectionSize(0),
        recommendation_header.sectionSize(1),
    )
    assert min(recommendation_widths) >= 100
    window._workspace_select("thrust_analysis")
    window._workspace_select("project")
    app.processEvents()
    assert (
        recommendation_header.sectionSize(0),
        recommendation_header.sectionSize(1),
    ) == recommendation_widths

    calibration_ids = {
        window.setup_page.calibration_combo.itemData(index)
        for index in range(window.setup_page.calibration_combo.count())
    }
    assert calibration_ids >= {
        "builtin.calibration.identity",
        "builtin.calibration.linear",
    }
    linear_index = window.setup_page.calibration_combo.findData(
        "builtin.calibration.linear"
    )
    window.setup_page.calibration_combo.setCurrentIndex(linear_index)
    app.processEvents()
    assert window.setup_page.calibration_id() == "builtin.calibration.linear"
    assert set(window.setup_page.calibration_form.field_names) == {
        "K",
        "B",
        "quantity",
        "unit",
    }
    k_editor = window.setup_page.calibration_form.field_widget("K")
    k_editor.setValue(2.5)
    window._locale_select("zh_CN")
    app.processEvents()
    assert window.setup_page.calibration_form.field_widget("K").value() == 2.5
    assert set(window.setup_page.calibration_form.field_names) == {
        "K",
        "B",
        "quantity",
        "unit",
    }
    window._locale_select("en_US")
    app.processEvents()

    dataset = Dataset(
        time=np.linspace(0.0, 10.0, 101),
        channels={
            "thrust_raw": Channel(
                "thrust_raw", "force", "raw", np.zeros(101), "raw"
            ),
            "force_calibrated": Channel(
                "force_calibrated",
                "force",
                "N",
                np.where(
                    (np.linspace(0.0, 10.0, 101) >= 3.0)
                    & (np.linspace(0.0, 10.0, 101) <= 5.0),
                    10.0,
                    0.0,
                ),
                "calibrated",
            ),
        },
    )
    window.process_page.set_datasets(dataset, dataset, None)
    assert set(window.process_page.curve_checks) == {"uncorrected", "corrected"}
    assert window.process_page.detect_button.text() == "Detect Test Interval"
    assert window.process_page.fit_button.text() == "Fit Interval"
    assert window.process_page.candidate_combo.currentData() is None
    assert window.process_page.candidate_combo.currentText() == "Not detected"
    window.session.calibrated_dataset = dataset
    window._burn_detect()
    _task_wait(window)
    assert window.process_page.candidate_combo.count() >= 1
    assert window.process_page.candidate_combo.currentData() == 0
    candidates = [
        BurnCandidate(3.0, 5.0, 10.0, 2.0, 8.0, 100.0, 21),
        BurnCandidate(6.0, 7.0, 5.0, 1.0, 4.0, 20.0, 11),
    ]
    window.process_page.set_candidates(candidates)
    assert window.process_page.candidate_combo.count() == 2
    assert window.process_page.candidate_combo.currentData() == 0
    window.process_page.candidate_combo.setCurrentIndex(1)
    app.processEvents()
    burn_start, burn_end = window.process_page.regions()["burn"]
    assert (burn_start, burn_end) == (6.0, 7.0)
    burn_start_edit, _burn_end_edit = window.process_page.region_edits["burn"]
    assert burn_start_edit.text().strip()
    assert burn_start_edit.palette().color(QPalette.ColorRole.Text).lightness() < 64
    burn_start_edit.setValue(6.1)
    app.processEvents()
    assert window.process_page.regions()["burn"][0] == 6.1
    window.process_page.fit_button.click()
    app.processEvents()
    view_start, view_end = window.process_page.plot_widget.viewRange()[0]
    assert 4.8 < view_start <= 5.0
    assert 8.0 <= view_end < 8.2
    window.close()
    app.processEvents()


def test_external_plugins_refresh_into_generic_gui_selectors(tmp_path: Path) -> None:
    app = _application()
    user_root = tmp_path / "user_plugins"
    _external_plugin_write(
        user_root,
        "processors",
        "weight_compensation",
        {
            "plugin_id": "example.processor.weight",
            "plugin_type": "processor",
            "api_version": "1",
            "version": "1.0.0",
            "entry": "plugin:ExampleWeightProcessor",
            "name": "Example Weight Compensation",
        },
        '''
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType, ProcessingResult
from underline_retldc.plugin_api.processor import ProcessorPlugin

class ExampleWeightProcessor(ProcessorPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "example.processor.weight", PluginType.PROCESSOR,
            "1.0.0", "1", "Example Weight Compensation", ""
        )
    def config_schema(self):
        return {
            "type": "object",
            "properties": {"gain": {"type": "number", "default": 1.0}}
        }
    def requirements(self):
        return {"processor_role": "motor_weight_compensation"}
    def process(self, dataset, config, context):
        return ProcessingResult(dataset, (), {"gain": config.get("gain", 1.0)})
''',
    )
    _external_plugin_write(
        user_root,
        "parsers",
        "example_parser",
        {
            "plugin_id": "example.parser.gui",
            "plugin_type": "parser",
            "api_version": "1",
            "version": "1.0.0",
            "entry": "plugin:ExampleParser",
            "name": "Example Parser",
        },
        '''
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType, ProbeResult
from underline_retldc.plugin_api.parser import ParserPlugin

class ExampleParser(ParserPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "example.parser.gui", PluginType.PARSER,
            "1.0.0", "1", "Example Parser", ""
        )
    def probe(self, source, context):
        return ProbeResult(0.0, "example")
    def config_schema(self):
        return {"type": "object", "properties": {}}
    def parse(self, source, config, context):
        raise NotImplementedError
    def validate(self, dataset):
        return []
''',
    )
    _external_plugin_write(
        user_root,
        "calibrations",
        "example_calibration",
        {
            "plugin_id": "example.calibration.gui",
            "plugin_type": "calibration",
            "api_version": "1",
            "version": "1.0.0",
            "entry": "plugin:ExampleCalibration",
            "name": "Example Calibration",
        },
        '''
import numpy as np
from underline_retldc.plugin_api.calibration import CalibrationModelPlugin
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType

class ExampleCalibration(CalibrationModelPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "example.calibration.gui", PluginType.CALIBRATION,
            "1.0.0", "1", "Example Calibration", ""
        )
    def parameter_schema(self):
        return {"type": "object", "properties": {"factor": {"type": "number", "default": 1.0}}}
    def evaluate(self, raw, parameters):
        return np.array(raw, dtype=float, copy=True) * float(parameters.get("factor", 1.0))
''',
    )
    _external_plugin_write(
        user_root,
        "exporters",
        "example_exporter",
        {
            "plugin_id": "example.exporter.gui",
            "plugin_type": "exporter",
            "api_version": "1",
            "version": "1.0.0",
            "entry": "plugin:ExampleExporter",
            "name": "Example Exporter",
        },
        '''
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType
from underline_retldc.plugin_api.exporter import ExporterPlugin

class ExampleExporter(ExporterPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "example.exporter.gui", PluginType.EXPORTER,
            "1.0.0", "1", "Example Exporter", ""
        )
    def config_schema(self):
        return {
            "type": "object",
            "properties": {},
            "x-underline-retldc-export": {
                "filename": "example.dat",
                "required_analysis_ids": [],
                "locale_qualified": False
            }
        }
    def validate(self, dataset, analysis, config):
        return []
    def export(self, destination, dataset, analysis, config, context):
        raise NotImplementedError
''',
    )

    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window._plugins_refresh()
    processor_ids = {
        window.process_page.processor_combo.itemData(index)
        for index in range(window.process_page.processor_combo.count())
    }
    assert processor_ids >= {
        None,
        "builtin.processor.vertical_linear_baseline",
        "example.processor.weight",
    }
    builtin_processor = window.registry.get(
        "builtin.processor.vertical_linear_baseline"
    )
    assert builtin_processor.requirements()["processor_role"] == (
        "motor_weight_compensation"
    )
    external_index = window.process_page.processor_combo.findData(
        "example.processor.weight"
    )
    window.process_page.processor_combo.setCurrentIndex(external_index)
    assert window.process_page.processor_form.field_names == ("gain",)

    parser_ids = {
        window.import_page.parser_combo.itemData(index)
        for index in range(window.import_page.parser_combo.count())
    }
    calibration_ids = {
        window.setup_page.calibration_combo.itemData(index)
        for index in range(window.setup_page.calibration_combo.count())
    }
    assert "example.parser.gui" in parser_ids
    assert "example.calibration.gui" in calibration_ids
    assert "example.exporter.gui" in window.export_dialog.exporter_checks
    assert window.export_dialog.exporter_checks["example.exporter.gui"].isEnabled()
    assert window.export_dialog.export_filename("example.exporter.gui") == "example.dat"
    assert any(
        record.plugin_id == "example.processor.weight"
        and record.source_kind == "user"
        for record in window.registry.records
    )

    window.process_page.plugins_button.click()
    app.processEvents()
    assert window.plugins_dialog.isVisible()
    window.plugins_dialog.close()
    window.close()
    app.processEvents()


def test_gui_creates_savable_incomplete_project_document(tmp_path: Path) -> None:
    app = _application()
    source = tmp_path / "not_parsed_yet.txt"
    source.write_text("0,0\n1,1\n", encoding="utf-8")
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.import_page.set_source_path(source)
    document = window._project_document_create()
    assert document.source_path == str(source.resolve())
    assert document.source_hash is None
    assert document.parser is not None
    assert document.parser.id == "builtin.parser.tr_f"
    assert document.calibration is not None
    assert len(document.processors) == 1
    assert document.processors[0].id == (
        "builtin.processor.vertical_linear_baseline"
    )
    assert document.regions == {}
    assert document.analyzer is None
    assert document.workflow_state == {
        "parsed": False,
        "calibrated": False,
        "processed": False,
        "analyzed": False,
    }
    hashed_document = window._project_document_create(Project_SourceHash(source))
    recomputed = window._project_recompute(hashed_document, TaskContext())
    assert recomputed[2:] == (None, None, None, None)
    window.close()
    app.processEvents()


def test_gui_pipeline_parses_calibrates_processes_analyzes_and_exports(
    tmp_path: Path, monkeypatch
) -> None:
    app = _application()
    time = np.linspace(0.0, 10.0, 501)
    baseline = 5.0 - 0.05 * time
    thrust = np.where(
        (time >= 3.0) & (time <= 7.0),
        12.0 * np.sin(np.pi * (time - 3.0) / 4.0),
        0.0,
    )
    source = tmp_path / "test.txt"
    source.write_text(
        "".join(
            f"{timestamp:.8f},{value:.8f}\n"
            for timestamp, value in zip(time, baseline + thrust, strict=True)
        ),
        encoding="utf-8",
    )
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id("builtin.parser.tr_f")
    window.import_page.set_parser_config(
        {"delimiter": ",", "time_unit": "s", "invalid_row_policy": "skip"}
    )
    window._source_parse()
    _task_wait(window)
    assert window.session.raw_dataset is not None
    assert window.session.raw_dataset.sample_count == 501

    window.setup_page.set_calibration_config(
        "builtin.calibration.linear",
        {"parameters": {"K": 1.0, "B": 0.0}, "quantity": "force", "unit": "N"},
    )
    window._calibration_apply()
    _task_wait(window)
    assert window.session.calibrated_dataset is not None

    window.process_page.set_regions(
        {"pre": [0.0, 2.5], "burn": [3.0, 7.0], "post": [7.5, 10.0]}
    )
    window._processing_apply()
    _task_wait(window)
    assert window.session.processed_dataset is not None

    window._analysis_calculate()
    _task_wait(window)
    assert window.session.analysis_result is not None
    assert all(
        checkbox.isEnabled()
        for checkbox in window.export_dialog.exporter_checks.values()
    )
    assert all(
        checkbox.isChecked()
        for checkbox in window.export_dialog.exporter_checks.values()
    )
    header = window.analyze_page.metrics_table.horizontalHeader()
    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(1) is QHeaderView.ResizeMode.Stretch
    metrics = window.session.analysis_result.metrics
    assert 11.9 < metrics["peak_thrust_n"] < 12.1
    assert metrics["total_impulse_ns"] > 30.0
    window.analyze_page.confirm_check.setChecked(True)
    app.processEvents()
    assert window.session.curve_confirmed
    assert window.session.project_path is None
    export_directory = tmp_path / "untitled_exports"
    window.export_dialog.set_output_directory(export_directory)
    window.export_dialog.set_selected_exporter_ids(
        (
            "builtin.exporter.csv",
            "builtin.exporter.analysis_json",
            "builtin.exporter.analysis_txt",
            "builtin.exporter.thrust_png",
        )
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok,
    )
    window._export_execute()
    _task_wait(window)
    assert {path.name for path in export_directory.iterdir()} == {
        "processed_thrust_EN.csv",
        "analysis_data_EN.json",
        "analysis_summary_EN.txt",
        "thrust_curve_EN.png",
    }
    document = window._project_document_create(Project_SourceHash(source))
    assert all(document.workflow_state.values())
    project_path = tmp_path / "Test_001.retldc.json"
    Project_Save(document, project_path)
    reopened_document = Project_Load(project_path)
    recomputed = window._project_recompute(reopened_document, TaskContext())
    assert recomputed[-1].metrics == window.session.analysis_result.metrics

    none_index = window.process_page.processor_combo.findData(None)
    window.process_page.processor_combo.setCurrentIndex(none_index)
    window._processing_apply()
    _task_wait(window)
    assert window.session.processor_id is None
    assert window.session.processor_config == {}
    np.testing.assert_allclose(
        window.session.processed_dataset.channel("thrust_processed").values,
        window.session.calibrated_dataset.channel("force_calibrated").values,
    )
    window._analysis_calculate()
    _task_wait(window)
    no_compensation_document = window._project_document_create(
        Project_SourceHash(source)
    )
    assert no_compensation_document.processors == ()
    assert no_compensation_document.workflow_state["processed"]
    no_compensation_recomputed = window._project_recompute(
        no_compensation_document, TaskContext()
    )
    assert no_compensation_recomputed[4].metadata["processor_id"] is None
    assert no_compensation_recomputed[-1].metrics == (
        window.session.analysis_result.metrics
    )
    window.close()
    app.processEvents()


def test_missing_project_processor_is_an_explicit_error(tmp_path: Path) -> None:
    app = _application()
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    document = ProjectDocument(
        processors=(
            PluginReference(
                "example.processor.not_installed",
                "2.3.4",
                "1",
                {},
            ),
        ),
        workflow_state={
            "parsed": False,
            "calibrated": False,
            "processed": False,
            "analyzed": False,
        },
    )
    with pytest.raises(
        ValueError,
        match=r"example\.processor\.not_installed.*2\.3\.4",
    ):
        window._project_recompute(document, TaskContext())
    window.close()
    app.processEvents()


def test_export_dialog_scrolls_after_ten_file_types(
    tmp_path: Path, monkeypatch
) -> None:
    app = _application()
    options = tuple(
        ExportOption(
            f"example.exporter.{index}",
            f"example_{index}.txt",
            f"example.exporter.{index}",
            ("builtin.analyzer.thrust",),
        )
        for index in range(11)
    )
    monkeypatch.setattr(ExportDialog, "EXPORTERS", options)
    dialog = ExportDialog(TranslationService("en_US"))
    dialog.set_output_directory(tmp_path)
    dialog.show()
    app.processEvents()
    assert len(dialog.exporter_checks) == 11
    assert dialog.exporter_scroll.verticalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert dialog.exporter_scroll.verticalScrollBar().isVisible()
    visible_rows_height = sum(
        max(checkbox.sizeHint().height(), 22)
        for checkbox in tuple(dialog.exporter_checks.values())[:10]
    ) + dialog.exporter_list_layout.spacing() * 9
    assert dialog.exporter_scroll.height() == visible_rows_height
    dialog.close()
    app.processEvents()
