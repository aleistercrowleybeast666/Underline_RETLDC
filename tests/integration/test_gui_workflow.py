from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt, qInstallMessageHandler
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QStyle,
)

from underline_retldc.app.session import ChannelCalibrationState
from underline_retldc.app.settings import (
    THEME_DARK,
    THEME_LIGHT,
    UNIT_DISPLAY_SI_SCIENTIFIC,
    SettingsService,
)
from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project import (
    PluginReference,
    Project_Load,
    Project_Save,
    Project_SourceHash,
    ProjectDocument,
)
from underline_retldc.core.project_data import (
    ChannelReference,
    PrimaryChannelBindings,
    ProjectData,
    Source,
    Stream,
)
from underline_retldc.core.regions import BurnCandidate
from underline_retldc.core.tabular import TabularPreview
from underline_retldc.core.workspace_capabilities import (
    WorkspaceCapabilities_Default,
    WorkspaceChannelCapability,
)
from underline_retldc.gui.analysis_widgets import AnalysisPlotWidget
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.gui.pages.export_page import ExportDialog, ExportOption
from underline_retldc.gui.pages.workspace_pages import WorkspaceSeries
from underline_retldc.gui.plugin_install_dialog import PluginInstallPreviewDialog
from underline_retldc.gui.tabular_mapping_editor import TabularMappingEditor
from underline_retldc.gui.theme import RetldcApplicationStyle, Theme_Apply, Theme_Current
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugin_api.common import (
    AnalysisResult,
    ProcessingResult,
    TaskContext,
)

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


def _window_with_bound_measurements(
    tmp_path: Path,
) -> tuple[MainWindow, Dataset]:
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    time = np.linspace(0.0, 10.0, 101)
    active = (time >= 3.0) & (time <= 7.0)
    dataset = Dataset(
        time,
        {
            "thrust": Channel(
                "thrust",
                "force",
                "N",
                np.where(active, 12.0, 0.0),
                "calibrated",
                semantic_role="thrust",
                name="Thrust A",
            ),
            "pressure": Channel(
                "pressure",
                "pressure",
                "MPa",
                np.where(active, -2.0, 0.0),
                "calibrated",
                semantic_role="chamber_pressure",
                name="Chamber Pressure A",
            ),
            "temperature": Channel(
                "temperature",
                "temperature",
                "°C",
                np.linspace(20.0, 80.0, time.size),
                "calibrated",
                semantic_role="temperature",
                name="Temperature A",
            ),
            "web": Channel(
                "web",
                "length",
                "mm",
                np.linspace(0.0, 13.0, time.size),
                "calibrated",
                semantic_role="auxiliary",
                name="Burned Web",
            ),
        },
    )
    source = Source("source", tmp_path / "measurements.csv")
    stream = Stream("stream", source.id, dataset)
    thrust_ref = ChannelReference(source.id, stream.id, "thrust")
    pressure_ref = ChannelReference(source.id, stream.id, "pressure")
    temperature_ref = ChannelReference(source.id, stream.id, "temperature")
    bindings = PrimaryChannelBindings(
        thrust=thrust_ref,
        chamber_pressure=pressure_ref,
        temperature_channels=(temperature_ref,),
    )
    window.session.project_data = ProjectData(
        {source.id: source},
        {stream.id: stream},
        bindings,
    )
    window.session.primary_stream_id = stream.id
    window.session.active_stream_id = stream.id
    window.session.raw_dataset = stream.dataset
    window.session.calibrated_dataset = stream.dataset
    window.session.calibrated_streams = {stream.id: stream.dataset}
    states = {
        channel_id: ChannelCalibrationState(
            channel_id,
            channel_id,
            "builtin.calibration.identity",
        )
        for channel_id in stream.dataset.channels
    }
    window.session.channel_calibrations = states
    window.session.stream_channel_calibrations = {
        ChannelReference(source.id, stream.id, channel_id).stable_id: state
        for channel_id, state in states.items()
    }
    window._primary_channels_update()
    window._measurement_workspaces_update()
    window._segmentation_views_sync()
    return window, stream.dataset


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


def test_gui_initializes_measurement_workspaces_and_switches_locale(
    tmp_path: Path,
) -> None:
    app = _application()
    settings = SettingsService(tmp_path / "settings.ini")
    translations = TranslationService("zh_CN")
    window = _window(translations, settings, tmp_path)
    assert window.windowTitle() == "Underline_RETLDC"
    assert window.header_title.text() == "Underline 火箭发动机试车数据解算"
    assert not hasattr(window, "header_project_title")
    assert window.stack.count() == 5
    assert window.navigation.item(0).text() == "工程"
    assert window.navigation.item(1).text() == "推力"
    assert window.navigation.item(2).text() == "燃烧室压力"
    assert window.navigation.item(3).text() == "温度"
    assert window.navigation.item(4).text() == "数据浏览器"
    assert window.plugins_page.warning_label.text() == (
        "外部 Python 插件属于可执行代码，请安装可信来源的插件。"
    )
    assert window.plugins_page.location_label.text() == (
        "建议将本程序安装在 D 盘等可写目录。插件优先安装到程序插件目录；"
        "程序目录无写入权限时自动使用用户插件目录。"
    )
    assert window.plugins_page.install_button.text() == "安装插件…"
    assert window.plugins_page.application_button.text() == "打开程序插件目录"
    assert window.plugins_page.user_button.text() == "打开用户插件目录"
    file_actions = window.project_menu.actions()
    assert file_actions[:5] == [
        window.open_raw_action,
        window.export_action,
        window.save_project_action,
        window.save_project_as_action,
        window.open_project_action,
    ]
    save_as_index = file_actions.index(window.save_project_as_action)
    assert file_actions[save_as_index + 1] is window.open_project_action
    assert not file_actions[save_as_index + 1].isSeparator()
    assert window.toolbar.actions() == [
        window.open_raw_action,
        window.export_action,
        window.save_project_action,
        window.open_project_action,
    ]
    assert not hasattr(window.project_page, "analysis_button")
    assert not hasattr(window.project_page, "analysis_requested")
    window.navigation.setCurrentRow(1)
    assert window.stack.currentWidget() is window.thrust_analysis_page
    window._locale_select("en_US")
    app.processEvents()
    assert window.navigation.item(0).text() == "Project"
    assert window.navigation.item(1).text() == "Thrust"
    assert window.navigation.item(2).text() == "Chamber Pressure"
    assert window.navigation.item(3).text() == "Temperature"
    assert window.navigation.item(4).text() == "Data Explorer"
    assert window.header_title.text() == (
        "Underline Rocket Engine Test Log Decoder and Calculator"
    )
    assert window.process_page.reset_chart_button.text() == "Reset Chart"
    assert window.chamber_pressure_page.reset_chart_button.text() == "Reset Chart"
    assert window.chamber_pressure_page.view_group is None
    assert window.temperature_page.view_group is None
    assert window.data_explorer_page.view_group is not None
    assert (
        window.chamber_pressure_page.statistics_group.title()
        == "Chamber Pressure Analysis Results"
    )
    assert (
        window.temperature_page.statistics_group.title()
        == "Temperature Analysis Results"
    )
    assert (
        window.analyze_page.metrics_table.horizontalHeaderItem(0).text()
        == "Analysis Metrics"
    )
    assert not hasattr(window.analyze_page, "confirm_check")
    assert window.plugins_page.refresh_button.text() == "Refresh"
    assert window.plugins_page.warning_label.text() == (
        "External Python plugins contain executable code. Only install plugins from "
        "trusted sources."
    )
    assert window.plugins_page.location_label.text() == (
        "Installing the application in a writable non-system location such as the D: "
        "drive is recommended. Plugins are installed to the application plugin folder "
        "when possible; the user plugin folder is used only when the application folder "
        "is not writable."
    )
    assert window.plugins_page.install_button.text() == "Install Plugin…"
    assert (
        window.plugins_page.application_button.text()
        == "Open Application Plugin Folder"
    )
    assert window.plugins_page.user_button.text() == "Open User Plugin Folder"
    assert window.settings_page.language_group.title() == "UI Language"
    assert window.export_dialog.windowTitle() == "Export…"
    assert settings.locale() == "en_US"
    combo_palette = window.language_combo.palette()
    assert combo_palette.color(QPalette.ColorRole.Button).lightness() < 120
    assert combo_palette.color(QPalette.ColorRole.Text).lightness() > 220
    window.show()
    app.processEvents()
    assert window.language_combo.width() >= 100
    assert window.language_combo.minimumContentsLength() == 6
    assert window.theme_combo.minimumContentsLength() == 5
    window.language_combo.setCurrentIndex(1)
    window.language_combo.showPopup()
    app.processEvents()
    assert window.language_combo.view().objectName() == "headerComboPopup"
    popup_palette = window.language_combo.view().palette()
    assert popup_palette.color(QPalette.ColorRole.Base).lightness() < 120
    assert popup_palette.color(QPalette.ColorRole.Text).lightness() > 220
    combo_bottom = window.language_combo.mapToGlobal(
        QPoint(0, window.language_combo.height())
    ).y()
    assert window.language_combo.view().window().geometry().top() >= combo_bottom
    assert window.language_combo.view().verticalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    window.language_combo.hidePopup()
    window.theme_combo.showPopup()
    app.processEvents()
    assert window.theme_combo.view().objectName() == "headerComboPopup"
    popup_palette = window.theme_combo.view().palette()
    assert popup_palette.color(QPalette.ColorRole.Base).lightness() < 120
    assert popup_palette.color(QPalette.ColorRole.Text).lightness() > 220
    window.theme_combo.hidePopup()

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
    assert window.export_dialog.width() >= 820
    assert window.export_dialog.output_language_combo.count() == 3
    assert window.export_dialog.output_language_combo.itemData(0) == (
        ExportDialog.OUTPUT_LOCALE_FOLLOW_UI
    )
    assert window.export_dialog.output_language_combo.currentIndex() == 0
    assert window.export_dialog.output_language_combo.currentText() == (
        "Follow UI Language (Default)"
    )
    assert window.export_dialog.output_locale_selection() == (
        ExportDialog.OUTPUT_LOCALE_FOLLOW_UI
    )
    assert window.export_dialog.output_locale() == "en_US"
    assert window.export_dialog.export_filename("builtin.exporter.csv") == (
        "thrust_data_EN.csv"
    )
    assert window._project_document_create().export_settings["output_locale"] == (
        ExportDialog.OUTPUT_LOCALE_FOLLOW_UI
    )
    window._locale_select("zh_CN")
    app.processEvents()
    assert window.export_dialog.output_locale_selection() == (
        ExportDialog.OUTPUT_LOCALE_FOLLOW_UI
    )
    assert window.export_dialog.output_language_combo.currentText() == "跟随界面（默认）"
    assert window.export_dialog.output_locale() == "zh_CN"
    assert window.export_dialog.export_filename("builtin.exporter.csv") == (
        "thrust_data_ZH.csv"
    )
    window._locale_select("en_US")
    app.processEvents()
    assert window.export_dialog.output_locale() == "en_US"
    assert window.export_dialog.content_scroll.verticalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert window.export_dialog.content_scroll.horizontalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    window.export_dialog._eng_enabled_update(True)
    app.processEvents()
    assert window.export_dialog.content_scroll.verticalScrollBar().isVisible()
    assert window.export_dialog.content_scroll.verticalScrollBar().maximum() > 0
    export_button_bottom = window.export_dialog.export_button.mapTo(
        window.export_dialog,
        QPoint(0, window.export_dialog.export_button.height()),
    ).y()
    assert export_button_bottom <= window.export_dialog.contentsRect().bottom()
    window.export_dialog._eng_enabled_update(False)
    assert max(
        checkbox.sizeHint().width()
        for checkbox in window.export_dialog.exporter_checks.values()
    ) <= window.export_dialog.exporter_scroll.viewport().width()
    assert len(window.export_dialog.exporter_checks) == 9
    assert all(
        not checkbox.isEnabled()
        for checkbox in window.export_dialog.exporter_checks.values()
    )
    assert all(
        window.export_dialog.required_analysis_ids(plugin_id) == ()
        for plugin_id in window.export_dialog.exporter_checks
    )
    window.export_dialog.reject()
    window.export_dialog.set_output_locale("zh_CN")
    assert window.export_dialog.export_filename("builtin.exporter.csv") == (
        "thrust_data_ZH.csv"
    )
    assert window.export_dialog.export_filename("builtin.exporter.thrust_png") == (
        "thrust_curve_ZH.png"
    )
    assert window.export_dialog.export_filename(
        "builtin.exporter.chamber_pressure_csv"
    ) == "chamber_pressure_data_ZH.csv"
    assert window.export_dialog.export_filename(
        "builtin.exporter.temperature_png"
    ) == "temperature_curve_ZH.png"
    assert window.export_dialog.export_filename("builtin.exporter.openrocket_eng") == (
        "motor.eng"
    )
    window.export_dialog.set_output_locale("en_US")
    assert window.export_dialog.export_filename("builtin.exporter.analysis_txt") == (
        "analysis_summary_EN.txt"
    )
    assert "expected_propellant_mass_kg" not in window.setup_page.motor_edits
    assert not hasattr(window.process_page, "select_input_button")
    window.close()
    app.processEvents()


def test_runtime_theme_header_and_settings_stay_synchronized(tmp_path: Path) -> None:
    app = _application()
    settings = SettingsService(tmp_path / "settings.ini")
    window = _window(TranslationService("zh_CN"), settings, tmp_path)
    window.show()
    app.processEvents()

    assert window.language_label.text() == "界面语言"
    assert window.theme_label.text() == "主题"
    assert window.version_label.text() == "v0.0.3"
    assert window.credit_label.text() == "辰星引力开发"
    assert window.version_label.font().weight() > window.credit_label.font().weight()
    assert window.language_label.font().weight() > window.language_combo.font().weight()
    assert window.theme_label.font().weight() > window.theme_combo.font().weight()
    assert window.credit_label.font().weight() == window.language_combo.font().weight()
    header_widgets = (
        window.header_title,
        window.version_label,
        window.credit_separator,
        window.credit_label,
        window.language_label,
        window.language_combo,
        window.theme_label,
        window.theme_combo,
    )
    header_centers = [
        widget.mapTo(window.header_widget, widget.rect().center()).y()
        for widget in header_widgets
    ]
    assert max(header_centers) - min(header_centers) <= 1
    central_layout = window.centralWidget().layout()
    central_margins = central_layout.contentsMargins()
    assert (
        central_margins.left(),
        central_margins.top(),
        central_margins.right(),
        central_margins.bottom(),
    ) == (0, 0, 0, 0)
    assert central_layout.spacing() == 0
    assert (
        window.menuBar().mapTo(window, QPoint(0, 0)).y()
        + window.menuBar().height()
        == window.toolbar.mapTo(window, QPoint(0, 0)).y()
    )
    assert (
        window.toolbar.mapTo(window, QPoint(0, 0)).y()
        + window.toolbar.height()
        == window.header_widget.mapTo(window, QPoint(0, 0)).y()
    )
    assert (
        window.header_widget.mapTo(window, QPoint(0, 0)).y()
        + window.header_widget.height()
        == window.navigation.mapTo(window, QPoint(0, 0)).y()
    )
    assert not hasattr(window, "theme_button")
    assert window.theme_combo.currentData() == THEME_LIGHT
    assert window.theme_combo.currentText() == "浅色"
    assert window.settings_page.theme_combo.currentData() == THEME_LIGHT
    assert Theme_Current(app) == THEME_LIGHT
    # Qt wraps the configured proxy in QStyleSheetStyle while a global style
    # sheet is active; verify the retained base style instead of that wrapper.
    assert isinstance(app._retldc_application_style, RetldcApplicationStyle)

    dark_index = window.theme_combo.findData(THEME_DARK)
    window.theme_combo.setCurrentIndex(dark_index)
    app.processEvents()
    assert settings.theme() == THEME_DARK
    assert Theme_Current(app) == THEME_DARK
    assert window.settings_page.theme_combo.currentData() == THEME_DARK
    assert window.theme_combo.currentData() == THEME_DARK
    assert window.theme_combo.currentText() == "深色"
    assert SettingsService(tmp_path / "settings.ini").theme() == THEME_DARK
    assert app.palette().color(QPalette.ColorRole.Window).lightness() < 60
    assert window.plugins_dialog.palette().color(QPalette.ColorRole.Window).lightness() < 60
    assert window.process_page.plot_widget.backgroundBrush().color().name() == "#0b1220"
    for combo in (window.language_combo, window.theme_combo):
        combo.showPopup()
        app.processEvents()
        assert combo.view().objectName() == "headerComboPopup"
        assert combo.view().palette().color(QPalette.ColorRole.Base).lightness() < 80
        assert combo.view().palette().color(QPalette.ColorRole.Text).lightness() > 220
        combo.hidePopup()

    window._locale_select("en_US")
    app.processEvents()
    assert window.language_label.text() == "UI Language"
    assert window.theme_label.text() == "Theme"
    assert window.version_label.text() == "v0.0.3"
    assert window.credit_label.text() == "By CXYL"
    assert window.header_title.text() == (
        "Underline Rocket Engine Test Log Decoder and Calculator"
    )
    assert window.theme_combo.currentData() == THEME_DARK
    assert window.theme_combo.currentText() == "Dark"

    light_index = window.settings_page.theme_combo.findData(THEME_LIGHT)
    window.settings_page.theme_combo.setCurrentIndex(light_index)
    app.processEvents()
    assert settings.theme() == THEME_LIGHT
    assert Theme_Current(app) == THEME_LIGHT
    assert window.theme_combo.currentData() == THEME_LIGHT
    assert window.theme_combo.currentText() == "Light"
    assert app.palette().color(QPalette.ColorRole.Window).lightness() > 220
    assert SettingsService(tmp_path / "settings.ini").theme() == THEME_LIGHT

    Theme_Apply(app, "invalid")
    assert Theme_Current(app) == THEME_LIGHT
    window.close()
    app.processEvents()


def test_application_stylesheets_parse_without_qt_warnings() -> None:
    app = _application()
    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda _message_type, _context, message: messages.append(message)
    )
    try:
        Theme_Apply(app, THEME_LIGHT)
        Theme_Apply(app, THEME_DARK)
        Theme_Apply(app, THEME_LIGHT)
    finally:
        qInstallMessageHandler(previous_handler)
    assert not [
        message
        for message in messages
        if "Could not parse application stylesheet" in message
    ]


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
    assert window.import_page.selected_parser_id() is None
    app.processEvents()
    assert window.import_page.selected_parser_id() is None
    assert window.import_page.configuration_form.field_names == ()
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
    assert window.import_page.selected_parser_id() is None
    assert len(window.import_page._ambiguity_buttons) == 3
    window.import_page.set_parser_id("builtin.parser.tr_f")
    app.processEvents()
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
    window.process_page.set_datasets(
        dataset,
        dataset,
        None,
        input_channel_id="force_calibrated",
    )
    assert set(window.process_page.curve_checks) == {"uncorrected", "corrected"}
    assert (
        window.process_page.detect_button.text()
        == "Auto-Detect Interval from Thrust Data"
    )
    controls_layout = window.process_page.controls_widget.layout()
    assert controls_layout.indexOf(window.process_page.input_group) == 0
    assert controls_layout.indexOf(window.process_page.interval_editor) == 1
    assert controls_layout.indexOf(window.process_page.polarity_group) == 2
    assert controls_layout.indexOf(window.process_page.curves_group) == 3
    assert window.process_page.fit_button.text() == "Fit View"
    assert window.process_page.candidate_combo.currentData() is None
    assert window.process_page.candidate_combo.currentText() == "Not detected"
    candidates = [
        BurnCandidate(3.0, 5.0, 10.0, 2.0, 8.0, 100.0, 21),
        BurnCandidate(6.0, 7.0, 5.0, 1.0, 4.0, 20.0, 11),
    ]
    window.process_page.set_candidates(candidates)
    assert window.process_page.candidate_combo.count() == 2
    assert window.process_page.candidate_combo.currentData() == 0
    window.process_page.candidate_combo.setCurrentIndex(1)
    app.processEvents()
    window.process_page.set_regions(
        {
            "pre": [5.0, 5.9],
            "active_test": [6.0, 7.0],
            "post": [7.1, 8.0],
        }
    )
    burn_start, burn_end = window.process_page.regions()["active_test"]
    assert (burn_start, burn_end) == (6.0, 7.0)
    burn_start_edit, _burn_end_edit = window.process_page.region_edits["burn"]
    assert burn_start_edit.text().strip()
    assert burn_start_edit.palette().color(QPalette.ColorRole.Text).lightness() < 64
    burn_start_edit.setValue(6.1)
    app.processEvents()
    assert window.process_page.regions()["active_test"][0] == 6.1
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


def test_plugin_dialog_installs_folder_to_writable_application_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _application()
    source_root = tmp_path / "selected_source"
    _external_plugin_write(
        source_root,
        "package",
        "example_parser",
        {
            "plugin_id": "example.parser.install_gui",
            "plugin_type": "parser",
            "api_version": "1",
            "version": "1.0.0",
            "entry": "plugin:ExampleParser",
            "name": "Install GUI Parser",
        },
        '''
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType, ProbeResult
from underline_retldc.plugin_api.parser import ParserPlugin

class ExampleParser(ParserPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "example.parser.install_gui", PluginType.PARSER,
            "1.0.0", "1", "Install GUI Parser", ""
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
    selected_source = source_root / "package" / "example_parser"
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"
    window = MainWindow(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        project_root=tmp_path,
        application_plugin_directory=application_root,
        user_plugin_directory=user_root,
    )
    messages: list[str] = []
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: ("Plugin folder", True),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(selected_source),
    )
    monkeypatch.setattr(window, "_plugin_install_confirm", lambda: True)
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: (
            messages.append(str(message)) or QMessageBox.StandardButton.Ok
        ),
    )
    monkeypatch.setattr(
        PluginInstallPreviewDialog,
        "exec",
        lambda _dialog: QDialog.DialogCode.Accepted,
    )

    window._plugin_install_dialog()
    _task_wait(window)

    record = next(
        item
        for item in window.registry.records
        if item.plugin_id == "example.parser.install_gui"
    )
    assert record.source_kind == "application"
    assert Path(record.source).is_relative_to(application_root.resolve())
    assert not user_root.exists()
    assert len(messages) == 1
    assert "Install GUI Parser" in messages[0]
    assert "Application plugin folder" in messages[0]
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
    assert document.parser is None
    assert document.calibration is None
    assert document.processors == ()
    assert document.regions == {}
    assert document.analyzer is None
    assert document.workflow_state == {
        "parsed": False,
        "calibrated": False,
        "processed": False,
        "analyzed": False,
        "chamber_pressure_analyzed": False,
        "temperature_analyzed": False,
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

    window._regions_store(
        {
            "pre": [0.0, 2.5],
            "active_test": [3.0, 7.0],
            "post": [7.5, 10.0],
        }
    )
    window._processing_apply()
    _task_wait(window)
    assert window.session.processed_dataset is not None

    window._analysis_calculate()
    _task_wait(window)
    assert window.session.analysis_result is not None
    for plugin_id, checkbox in window.export_dialog.exporter_checks.items():
        group_id = window.export_dialog.export_group_id(plugin_id)
        if group_id in {"overall", "thrust"}:
            assert checkbox.isEnabled()
        else:
            assert not checkbox.isEnabled()
            assert not checkbox.isChecked()
    assert window.export_dialog.exporter_checks[
        "builtin.exporter.openrocket_eng"
    ].isChecked()
    header = window.analyze_page.metrics_table.horizontalHeader()
    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(1) is QHeaderView.ResizeMode.Stretch
    metrics = window.session.analysis_result.metrics
    assert 11.9 < metrics["peak_thrust_n"] < 12.1
    assert metrics["total_impulse_ns"] > 30.0
    assert not hasattr(window.analyze_page, "confirm_check")
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
        "thrust_data_EN.csv",
        "analysis_data_EN.json",
        "analysis_summary_EN.txt",
        "thrust_curve_EN.png",
    }
    document = window._project_document_create(Project_SourceHash(source))
    assert all(
        document.workflow_state[key]
        for key in ("parsed", "calibrated", "processed", "analyzed")
    )
    assert not document.workflow_state["chamber_pressure_analyzed"]
    assert not document.workflow_state["temperature_analyzed"]
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
        window.session.calibrated_dataset.channel("thrust_raw_calibrated").values,
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


def test_gui_imports_multiple_sources_with_independent_project_time(
    tmp_path: Path,
) -> None:
    app = _application()
    source_a = tmp_path / "thrust_a.txt"
    source_b = tmp_path / "thrust_b.txt"
    source_a.write_text("0,0\n1,5\n2,0\n", encoding="utf-8")
    source_b.write_text("0,0\n0.5,3\n1.5,0\n", encoding="utf-8")
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.import_page.set_source_entries(
        [(source_a, 0.0), (source_b, 10.0)]
    )
    window.import_page.set_parser_id("builtin.parser.tr_f")
    window.import_page.set_parser_config(
        {"delimiter": ",", "time_unit": "s", "invalid_row_policy": "skip"}
    )
    window._source_parse()
    _task_wait(window)

    assert len(window.session.project_data.sources) == 2
    assert len(window.session.project_data.streams) == 2
    assert len(window.session.calibrated_streams) == 2
    assert window.session.project_data.primary_channels.thrust is None
    second = window.session.project_data.streams["stream_2"].dataset
    np.testing.assert_allclose(second.project_time, [10.0, 10.5, 11.5])
    np.testing.assert_allclose(second.time, [0.0, 0.5, 1.5])
    for dataset in window.session.calibrated_streams.values():
        assert "thrust_raw_calibrated" in dataset.channels
        assert dataset.channel("thrust_raw_calibrated").data_unit == "raw"
    assert window.data_explorer_page.channel_combo.count() == 2

    window.import_page.source_list.setCurrentRow(1)
    app.processEvents()
    assert window.session.active_stream_id == "stream_2"
    window.setup_page.set_calibration_config(
        "builtin.calibration.linear",
        {
            "input_channel_id": "thrust_raw",
            "output_channel_id": "thrust_raw_calibrated",
            "quantity": "force",
            "unit": "N",
            "parameters": {"K": 2.0, "B": 1.0},
            "data_quantity": "force",
            "data_unit": "raw",
            "display_unit": "raw",
            "semantic_role": "thrust",
        },
    )
    window._calibration_apply()
    _task_wait(window)
    assert window.session.primary_stream_id == "stream_1"
    assert (
        window.session.calibrated_dataset.channel("thrust_raw_calibrated").data_unit
        == "raw"
    )
    secondary_calibrated = window.session.calibrated_streams["stream_2"]
    assert secondary_calibrated.channel("thrust_raw_calibrated").data_unit == "N"
    np.testing.assert_allclose(
        secondary_calibrated.channel("thrust_raw_calibrated").values,
        [1.0, 7.0, 1.0],
    )

    selected_thrust = ChannelReference("source_2", "stream_2", "thrust_raw")
    thrust_selector = window.project_page.primary_channels.thrust_combo
    thrust_selector.setCurrentIndex(
        thrust_selector.findData(selected_thrust.stable_id)
    )
    app.processEvents()
    assert window.session.project_data.primary_channels.thrust == selected_thrust
    assert window.session.primary_stream_id == "stream_2"

    document = window._project_document_create()
    assert len(document.sources) == 2
    assert len(document.streams) == 2
    assert len(document.channels) == 2
    assert document.streams[1].time_offset_s == 10.0
    secondary_state = document.channels["source_2/stream_2/thrust_raw"]
    assert secondary_state.calibration is not None
    assert secondary_state.calibration.id == "builtin.calibration.linear"
    assert document.primary_channels.thrust == selected_thrust
    document = ProjectDocument.from_dict(document.to_dict())
    recomputed = window._project_recompute(document, TaskContext())
    assert recomputed[2] is not None
    assert len(window._recomputed_project_data.sources) == 2
    assert len(window._recomputed_calibrated_streams) == 2
    np.testing.assert_allclose(
        window._recomputed_project_data.streams["stream_2"].dataset.project_time,
        [10.0, 10.5, 11.5],
    )
    restored_secondary = window._recomputed_calibrated_streams["stream_2"]
    assert restored_secondary.channel("thrust_raw_calibrated").data_unit == "N"
    np.testing.assert_allclose(
        restored_secondary.channel("thrust_raw_calibrated").values,
        [1.0, 7.0, 1.0],
    )
    window.close()
    app.processEvents()


def test_raw_identity_analysis_keeps_relative_results_but_disables_eng(
    tmp_path: Path,
) -> None:
    app = _application()
    source = tmp_path / "raw_force.txt"
    source.write_text("0,0\n1,5\n2,5\n3,0\n", encoding="utf-8")
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
    assert window.session.calibration_id == "builtin.calibration.identity"
    assert (
        window.session.calibrated_dataset.channel("thrust_raw_calibrated").data_unit
        == "raw"
    )

    window._regions_store(
        {"pre": None, "active_test": [0.5, 2.5], "post": None}
    )
    none_index = window.process_page.processor_combo.findData(None)
    window.process_page.processor_combo.setCurrentIndex(none_index)
    window._processing_apply()
    _task_wait(window)
    window._analysis_calculate()
    _task_wait(window)

    result = window.session.analysis_result
    assert result is not None
    assert result.metrics["peak_value"] == 5.0
    assert result.metrics["peak_thrust_n"] is None
    eng = window.export_dialog.exporter_checks[
        "builtin.exporter.openrocket_eng"
    ]
    assert not eng.isEnabled()
    assert not eng.isChecked()
    for plugin_id, checkbox in window.export_dialog.exporter_checks.items():
        group_id = window.export_dialog.export_group_id(plugin_id)
        if group_id in {"overall", "thrust"} and plugin_id != (
            "builtin.exporter.openrocket_eng"
        ):
            assert checkbox.isEnabled() and checkbox.isChecked()
        elif plugin_id != "builtin.exporter.openrocket_eng":
            assert not checkbox.isEnabled()
            assert not checkbox.isChecked()
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
            requires_motor_metadata=index == 0,
        )
        for index in range(11)
    )
    monkeypatch.setattr(ExportDialog, "EXPORTERS", options)
    dialog = ExportDialog(TranslationService("en_US"))
    dialog.set_output_directory(tmp_path)
    dialog.set_completed_analysis_ids(("builtin.analyzer.thrust",))
    dialog.resize(820, 420)
    dialog.show()
    app.processEvents()
    assert len(dialog.exporter_checks) == 11
    assert dialog.exporter_scroll.verticalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert dialog.exporter_scroll.verticalScrollBar().isVisible()
    assert dialog.content_scroll.verticalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert dialog.content_scroll.verticalScrollBar().isVisible()
    assert dialog.content_scroll.verticalScrollBar().maximum() > 0
    assert dialog.export_button.isVisible()
    assert dialog.export_button.isEnabled()
    export_button_bottom = dialog.export_button.mapTo(
        dialog,
        QPoint(0, dialog.export_button.height()),
    ).y()
    assert export_button_bottom <= dialog.contentsRect().bottom()
    visible_rows_height = sum(
        max(checkbox.sizeHint().height(), 22)
        for checkbox in tuple(dialog.exporter_checks.values())[:10]
    )
    heading_height = sum(
        max(label.sizeHint().height(), 24)
        for label in dialog.group_labels.values()
    )
    visible_rows_height += heading_height
    visible_rows_height += dialog.exporter_list_layout.spacing() * (
        10 + len(dialog.group_labels) - 1
    )
    assert dialog.exporter_scroll.height() == visible_rows_height
    dialog.close()


def test_generic_tabular_mapping_flows_into_project_and_workspaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _application()
    source = tmp_path / "unknown_headers.csv"
    source.write_text(
        "T0,CH_A,CH_B\n0.0,0.10,10\n0.1,0.20,20\n0.25,0.30,15\n",
        encoding="utf-8",
    )
    original = source.read_bytes()
    settings = SettingsService(tmp_path / "settings.ini")
    translations = TranslationService("en_US")
    window = _window(translations, settings, tmp_path)
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id("builtin.parser.generic_delimited")
    app.processEvents()
    _task_wait(window)

    editor = window.import_page.tabular_mapping_editor
    assert window.import_page.uses_tabular_mapping()
    assert editor.preview_table.columnCount() == 3
    mapping = {
        "delimiter": "auto",
        "encoding": "auto",
        "header_row": 1,
        "data_start_row": 2,
        "data_end_row": None,
        "invalid_row_policy": "preserve",
        "time": {"mode": "column", "column": 0, "unit": "s"},
        "columns": [
            {
                "column": 0,
                "usage": "time",
                "unit": "s",
                "expected_header": "T0",
            },
            {
                "column": 1,
                "usage": "data",
                "display_name": "Pressure A",
                "channel_id": "pressure_a",
                "quantity": "pressure",
                "role": "chamber_pressure",
                "unit": "MPa",
                "expected_header": "CH_A",
            },
            {
                "column": 2,
                "usage": "data",
                "display_name": "Force B",
                "channel_id": "force_b",
                "quantity": "force",
                "role": "thrust",
                "unit": "N",
                "expected_header": "CH_B",
            },
        ],
    }
    editor.set_config(mapping)

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *_args, **_kwargs: ("Lab Rig", True),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    editor.preset_save_button.click()
    user_preset = tmp_path / "presets" / "tabular" / "Lab_Rig.json"
    assert user_preset.is_file()
    preset_payload = json.loads(user_preset.read_text(encoding="utf-8"))
    assert preset_payload["schema"] == "underline-retldc-tabular-preset/1"
    assert preset_payload["config"]["columns"][2]["channel_id"] == "force_b"

    exported_preset = tmp_path / "exported_lab.json"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(exported_preset), ""),
    )
    editor.preset_export_button.click()
    assert exported_preset.is_file()
    editor.preset_delete_button.click()
    assert not user_preset.exists()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(exported_preset), ""),
    )
    editor.preset_import_button.click()
    app.processEvents()
    _task_wait(window)
    assert (tmp_path / "presets" / "tabular" / "exported_lab.json").is_file()
    assert editor.config()["columns"][1]["channel_id"] == "pressure_a"

    window._source_parse()
    _task_wait(window)

    assert source.read_bytes() == original
    assert window.session.raw_dataset is not None
    assert np.allclose(window.session.raw_dataset.time, [0.0, 0.1, 0.25])
    pressure = window.session.raw_dataset.channel("pressure_a")
    thrust = window.session.raw_dataset.channel("force_b")
    assert (pressure.quantity, pressure.semantic_role, pressure.data_unit) == (
        "pressure",
        "chamber_pressure",
        "MPa",
    )
    assert (thrust.quantity, thrust.semantic_role, thrust.data_unit) == (
        "force",
        "thrust",
        "N",
    )
    assert window.session.project_data.primary_channels.thrust is not None
    assert (
        window.session.project_data.primary_channels.chamber_pressure is not None
    )
    assert window.chamber_pressure_page.channel_combo.count() == 2
    assert window.temperature_page.channel_combo.count() == 0
    assert window.data_explorer_page.channel_combo.count() == 2
    assert len(window.process_page._curve_items) == 1
    assert len(window.chamber_pressure_page.analysis_plot._series) == 1
    assert window.stack.currentWidget() is window.project_page

    document = window._project_document_create(Project_SourceHash(source))
    project_path = tmp_path / "mapped.retldc.json"
    Project_Save(document, project_path)
    loaded = Project_Load(project_path)
    assert loaded.sources[0].parser is not None
    saved_mapping = loaded.sources[0].parser.config
    assert saved_mapping["time"]["column"] == 0
    assert saved_mapping["columns"][2]["channel_id"] == "force_b"
    assert loaded.primary_channels.thrust is not None
    assert loaded.primary_channels.thrust.channel_id == "force_b"
    assert loaded.primary_channels.chamber_pressure is not None
    assert loaded.primary_channels.chamber_pressure.channel_id == "pressure_a"
    window.close()

    reopened = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "reopened_settings.ini"),
        tmp_path,
    )
    recomputed = reopened._project_recompute(
        loaded,
        TaskContext(),
        raw_source=source,
    )
    reopened_dataset = recomputed[2].dataset
    assert np.allclose(reopened_dataset.time, [0.0, 0.1, 0.25])
    assert reopened_dataset.channel("force_b").semantic_role == "thrust"
    source_config = reopened._recomputed_project_data.sources["source_1"].parser_config
    assert source_config["columns"][1]["channel_id"] == "pressure_a"
    assert reopened._recomputed_project_data.primary_channels == loaded.primary_channels
    reopened.close()
    app.processEvents()


def test_workspace_capability_extends_quick_mapping_without_editor_changes() -> None:
    app = _application()
    registry = WorkspaceCapabilities_Default()
    registry.register(
        WorkspaceChannelCapability(
            capability_id="mass_flow",
            workspace_id="mass_flow",
            display_key="mapping.type.mass_flow",
            quantity="mass_flow",
            semantic_role="mass_flow",
        )
    )
    editor = TabularMappingEditor(TranslationService("en_US"), registry)
    editor.set_parser(
        "builtin.parser.generic_delimited",
        "1.0.0",
        "delimited",
    )
    editor.set_preview(
        TabularPreview(
            headers=("Time", "Mass Flow"),
            rows=(("0", "1"), ("1", "2")),
            row_numbers=(2, 3),
            column_count=2,
        ),
        config={
            "header_row": 1,
            "data_start_row": 2,
            "time": {"mode": "column", "column": 0, "unit": "s"},
            "columns": [
                {"column": 0, "usage": "time", "unit": "s"},
                {
                    "column": 1,
                    "usage": "data",
                    "display_name": "Mass Flow",
                    "channel_id": "mass_flow",
                    "quantity": "mass_flow",
                    "role": "mass_flow",
                    "unit": "kg/s",
                },
            ],
        },
    )
    assert editor.simple_type_ids() == (
        "time",
        "thrust",
        "chamber_pressure",
        "temperature",
        "mass_flow",
        "other",
    )
    type_combo = editor.quick_table.cellWidget(1, 2)
    assert {
        type_combo.itemData(index) for index in range(type_combo.count())
    } == set(editor.simple_type_ids())
    editor.deleteLater()
    app.processEvents()


def test_analysis_workspaces_share_plot_shell_and_temperature_is_multi_series(
    tmp_path: Path,
) -> None:
    app = _application()
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    pages = (
        window.process_page,
        window.chamber_pressure_page,
        window.temperature_page,
    )
    assert all(isinstance(page.analysis_plot, AnalysisPlotWidget) for page in pages)
    window._theme_select(THEME_DARK)
    backgrounds = {
        page.plot_widget.backgroundBrush().color().name() for page in pages
    }
    assert backgrounds == {"#0b1220"}

    time = np.linspace(0.0, 4.0, 9)
    first_reference = ChannelReference("source_1", "stream_1", "tc_1")
    second_reference = ChannelReference("source_1", "stream_1", "tc_2")
    dataset = Dataset(
        time=time,
        source_id="source_1",
        stream_id="stream_1",
        channels={
            "tc_1_calibrated": Channel(
                "tc_1_calibrated",
                "temperature",
                "K",
                np.linspace(300.0, 340.0, 9),
                "calibrated",
                semantic_role="temperature",
            ),
            "tc_2_calibrated": Channel(
                "tc_2_calibrated",
                "temperature",
                "K",
                np.linspace(310.0, 370.0, 9),
                "calibrated",
                semantic_role="temperature",
            ),
        },
    )
    series = (
        WorkspaceSeries(
            first_reference,
            dataset,
            "tc_1_calibrated",
            "fixture.csv · TC1 [K]",
        ),
        WorkspaceSeries(
            second_reference,
            dataset,
            "tc_2_calibrated",
            "fixture.csv · TC2 [K]",
        ),
    )
    window.temperature_page.set_series(
        series,
        selected=(first_reference, second_reference),
    )
    regions = {
        "pre": [0.0, 0.5],
        "burn": [1.0, 3.0],
        "post": [3.5, 4.0],
    }
    for page in pages:
        page.analysis_plot.set_regions(regions)
        assert page.pre_region.isVisible()
        if page is window.process_page:
            assert page.burn_region.isVisible()
        else:
            assert page.active_region.isVisible()
        assert page.post_region.isVisible()
    assert len(window.temperature_page.analysis_plot._series) == 2
    assert len(window.temperature_page.analysis_plot.legend.items) == 2
    assert window.temperature_page.metrics_table.rowCount() == 0
    assert {
        checkbox.text()
        for checkbox in window.temperature_page.curve_checks.values()
    } == {"fixture.csv · TC1 [K]", "fixture.csv · TC2 [K]"}
    window.temperature_page.set_regions(regions)
    assert window.temperature_page.calculate_button is not None
    window.temperature_page.calculate_button.click()
    app.processEvents()
    assert window.temperature_page.metrics_table.rowCount() == 8
    assert window.temperature_page.analysis_complete
    next(iter(window.temperature_page.curve_checks.values())).setChecked(False)
    app.processEvents()
    assert len(window.temperature_page.analysis_plot._series) == 1

    auxiliary_reference = ChannelReference("source_1", "stream_1", "aux")
    auxiliary_dataset = Dataset(
        time=time,
        source_id="source_1",
        stream_id="stream_1",
        channels={
            "aux_calibrated": Channel(
                "aux_calibrated",
                "custom.aux",
                "1",
                np.arange(9),
                "calibrated",
                semantic_role="auxiliary",
            )
        },
    )
    window.data_explorer_page.set_series(
        (
            series[0],
            WorkspaceSeries(
                auxiliary_reference,
                auxiliary_dataset,
                "aux_calibrated",
                "fixture.csv · Other [1]",
                auxiliary=True,
            ),
        )
    )
    assert window.data_explorer_page.channel_combo.count() == 1
    window.data_explorer_page.show_auxiliary_check.setChecked(True)
    assert window.data_explorer_page.channel_combo.count() == 2
    window.close()
    app.processEvents()


def test_quick_import_binds_thrust_pressure_and_routes_workspaces(
    tmp_path: Path,
) -> None:
    app = _application()
    source = tmp_path / "quick.csv"
    source.write_text(
        "Time [s],Chamber Pressure [MPa],Thrust [N],Kn [1]\n"
        "0.0,0.1,0,100\n"
        "0.1,0.2,10,110\n"
        "0.25,0.15,0,105\n",
        encoding="utf-8",
    )
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id("builtin.parser.generic_delimited")
    app.processEvents()
    _task_wait(window)
    editor = window.import_page.tabular_mapping_editor
    if editor.quick_table.rowCount() == 0:
        window._tabular_preview_refresh(True)
        _task_wait(window)
    assert not editor.advanced_container.isVisible()
    assert tuple(
        editor.quick_table.cellWidget(row, 2).currentData()
        for row in range(editor.quick_table.rowCount())
    ) == ("time", "chamber_pressure", "thrust", "other")

    window._source_parse()
    _task_wait(window)
    bindings = window.session.project_data.primary_channels
    assert bindings.thrust is not None
    assert bindings.thrust.channel_id == "thrust"
    assert bindings.chamber_pressure is not None
    assert bindings.chamber_pressure.channel_id == "chamber_pressure"
    assert window.session.raw_dataset.channel("kn").semantic_role == "auxiliary"
    assert len(window.process_page.analysis_plot._series) == 1
    assert len(window.chamber_pressure_page.analysis_plot._series) == 1
    assert window.data_explorer_page.channel_combo.count() == 2
    assert (
        window.temperature_page.analysis_plot._stack.currentWidget()
        is window.temperature_page.analysis_plot.empty_widget
    )
    assert window.temperature_page.analysis_plot.empty_label.text() == (
        "This Project has no temperature data."
    )
    document = ProjectDocument.from_dict(
        window._project_document_create(Project_SourceHash(source)).to_dict()
    )
    recomputed = window._project_recompute(document, TaskContext())
    assert recomputed[2].dataset.channel("kn").semantic_role == "auxiliary"
    window.close()
    app.processEvents()


@pytest.mark.parametrize(
    ("parser_id", "channel_id", "workspace_name"),
    (
        ("builtin.parser.tr_p", "pressure_raw", "chamber_pressure_page"),
        ("builtin.parser.tr_t", "temperature_raw", "temperature_page"),
    ),
)
def test_tr_pressure_and_temperature_route_directly_to_their_workspaces(
    tmp_path: Path,
    parser_id: str,
    channel_id: str,
    workspace_name: str,
) -> None:
    app = _application()
    source = tmp_path / f"{channel_id}.txt"
    source.write_text("0.0,0\n0.1,1\n0.2,0\n", encoding="utf-8")
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id(parser_id)
    window._source_parse()
    _task_wait(window)
    bindings = window.session.project_data.primary_channels
    if parser_id.endswith("tr_p"):
        assert bindings.chamber_pressure is not None
        assert bindings.chamber_pressure.channel_id == channel_id
    else:
        assert [item.channel_id for item in bindings.temperature_channels] == [
            channel_id
        ]
    workspace = getattr(window, workspace_name)
    assert len(workspace.analysis_plot._series) == 1
    plotted_channel = workspace._selected_series()[0].dataset.channel(
        f"{channel_id}_calibrated"
    )
    assert plotted_channel.data_unit == "raw"
    window.close()
    app.processEvents()


def test_pressure_parser_dropdown_works_before_any_thrust_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _application()
    source = tmp_path / "pressure_only.txt"
    source.write_text("0.0,0\n0.1,1\n0.2,0\n", encoding="utf-8")
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id(None)
    window._parser_detect()
    _task_wait(window)

    page = window.import_page
    assert not page.parse_button.isEnabled()
    pressure_parser_id = "builtin.parser.tr_p"
    page.parser_combo.setCurrentIndex(page.parser_combo.findData(pressure_parser_id))
    app.processEvents()
    assert page.selected_parser_id() == pressure_parser_id
    assert page.parse_button.isEnabled()
    assert next(
        button
        for button in page._ambiguity_buttons
        if button.property("parserPluginId") == pressure_parser_id
    ).isChecked()

    page.parse_button.click()
    _task_wait(window)
    bindings = window.session.project_data.primary_channels
    assert bindings.thrust is None
    assert bindings.chamber_pressure is not None
    assert bindings.chamber_pressure.channel_id == "pressure_raw"
    assert len(window.chamber_pressure_page.analysis_plot._series) == 1

    monkeypatch.setattr(
        "underline_retldc.gui.main_window.Activity_DetectSegments",
        lambda _time, _values, *, sign=1: [
            BurnCandidate(0.05, 0.15, 1.0, 0.1, 1.0, 1.0, 1)
        ],
    )
    assert window.chamber_pressure_page.interval_editor is not None
    window.chamber_pressure_page.interval_editor.detect_button.click()
    _task_wait(window)
    assert window.session.segmentation_reference_priority == "chamber_pressure"
    assert window.session.regions["active_test"] == [0.05, 0.15]
    window.close()
    app.processEvents()


def test_shared_segmentation_uses_positive_pressure_sign_and_syncs_both_pages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _application()
    window, _dataset = _window_with_bound_measurements(tmp_path)
    captured: dict[str, int] = {}

    def fake_detect(time, values, *, sign=1, **_kwargs):
        captured["sign"] = int(sign)
        return [BurnCandidate(3.0, 7.0, -2.0, 4.0, 2.0, 20.0, 41)]

    monkeypatch.setattr(
        "underline_retldc.gui.main_window.Activity_DetectSegments",
        fake_detect,
    )
    window.session.thrust_polarity = -1
    window.process_page.set_thrust_polarity(-1)
    assert window.chamber_pressure_page.interval_editor is not None
    window.chamber_pressure_page.interval_editor.detect_button.click()
    _task_wait(window)

    assert captured["sign"] == 1
    assert window.session.segmentation_reference_priority == "chamber_pressure"
    assert window.session.segmentation_reference is not None
    assert window.session.segmentation_reference.channel_id == "pressure"
    assert window.session.regions["active_test"] == [3.0, 7.0]
    assert window.process_page.regions() == window.chamber_pressure_page._regions

    thrust_start = window.process_page.region_edits["active_test"][0]
    thrust_start.setValue(3.2)
    app.processEvents()
    assert window.session.regions["active_test"][0] == 3.2
    assert (
        window.chamber_pressure_page.interval_editor.region_edits[
            "active_test"
        ][0].value()
        == 3.2
    )

    pressure_end = window.chamber_pressure_page.interval_editor.region_edits[
        "active_test"
    ][1]
    pressure_end.setValue(6.8)
    app.processEvents()
    assert window.session.regions["active_test"][1] == 6.8
    assert window.process_page.region_edits["active_test"][1].value() == 6.8
    assert window.session.segmentation_manually_modified
    window.close()
    app.processEvents()


def test_thrust_segmentation_uses_oriented_signal_with_positive_detector_sign(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _application()
    window, dataset = _window_with_bound_measurements(tmp_path)
    bindings = window.session.project_data.primary_channels
    window.session.project_data = window.session.project_data.with_primary_channels(
        PrimaryChannelBindings(
            thrust=bindings.thrust,
            chamber_pressure=None,
            temperature_channels=bindings.temperature_channels,
        )
    )
    window.session.thrust_polarity = -1
    window.process_page.set_thrust_polarity(-1)
    window._primary_channels_update()
    captured: dict[str, object] = {}

    def fake_detect(time, values, *, sign=1, **_kwargs):
        captured["sign"] = int(sign)
        captured["values"] = np.asarray(values).copy()
        return []

    monkeypatch.setattr(
        "underline_retldc.gui.main_window.Activity_DetectSegments",
        fake_detect,
    )
    window.process_page.detect_button.click()
    _task_wait(window)

    assert captured["sign"] == 1
    np.testing.assert_allclose(
        captured["values"],
        -dataset.channel("thrust").values,
    )
    assert window.session.segmentation_reference_priority == "thrust"
    window.close()
    app.processEvents()


def test_thrust_polarity_remains_enabled_without_correction_and_drives_analysis(
    tmp_path: Path,
) -> None:
    app = _application()
    window, dataset = _window_with_bound_measurements(tmp_path)
    window.show()
    window.navigation.setCurrentRow(1)
    app.processEvents()

    none_index = window.process_page.processor_combo.findData(None)
    window.process_page.processor_combo.setCurrentIndex(none_index)
    assert window.process_page.polarity_combo.isVisible()
    assert window.process_page.polarity_combo.isEnabled()
    reversed_index = window.process_page.polarity_combo.findData(-1)
    window.process_page.polarity_combo.setCurrentIndex(reversed_index)
    app.processEvents()

    assert window.session.thrust_polarity == -1
    assert window.process_page.processor_id() is None
    np.testing.assert_allclose(
        window.process_page._calibrated_dataset.channel("thrust_oriented").values,
        -dataset.channel("thrust").values,
    )
    window._regions_store(
        {"pre": None, "active_test": [3.0, 7.0], "post": None}
    )
    window._processing_apply()
    _task_wait(window)
    np.testing.assert_allclose(
        window.session.processed_dataset.channel("thrust_processed").values,
        -dataset.channel("thrust").values,
    )
    assert window.session.processor_id is None

    window._analysis_calculate()
    _task_wait(window)
    assert window.session.analysis_result is not None
    assert window.session.analysis_result.metrics["peak_value"] == -12.0
    window.close()
    app.processEvents()


def test_unit_mode_axes_results_and_analysis_layout_are_consistent(
    tmp_path: Path,
) -> None:
    app = _application()
    window, _dataset = _window_with_bound_measurements(tmp_path)
    window.show()
    window.resize(980, 640)
    window.navigation.setCurrentRow(0)
    app.processEvents()

    project_page = window.project_page
    assert project_page.splitter.orientation() is Qt.Orientation.Vertical
    assert not project_page.splitter.childrenCollapsible()
    assert all(not project_page.splitter.isCollapsible(index) for index in range(2))
    assert project_page.import_scroll.horizontalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert project_page.setup_scroll.horizontalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )

    window.navigation.setCurrentRow(1)
    app.processEvents()

    shell = window.thrust_analysis_page.shell
    header_theme_right = window.theme_combo.mapTo(
        window.header_widget,
        window.theme_combo.rect().bottomRight(),
    ).x()
    assert header_theme_right <= window.header_widget.contentsRect().right()
    assert shell.controls_scroll.verticalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert shell.controls_scroll.horizontalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert not shell.splitter.childrenCollapsible()
    assert all(not shell.splitter.isCollapsible(index) for index in range(3))
    assert shell.controls_scroll.maximumWidth() == 400
    assert shell.controls_scroll.minimumWidth() == 320
    assert shell.results.minimumWidth() == 220
    assert shell.results.maximumWidth() == 310
    assert shell.plot.minimumWidth() == 250
    assert shell.controls_scroll.width() >= 320
    assert shell.results.width() >= 220
    assert shell.plot.width() >= 250
    compact_plot_width = shell.plot.width()
    shell.splitter.setSizes([0, 1000, 0])
    app.processEvents()
    assert shell.controls_scroll.width() >= 320
    assert shell.results.width() >= 220
    assert shell.plot.width() >= 250

    window.navigation.setCurrentRow(2)
    app.processEvents()
    pressure_shell = window.chamber_pressure_page.shell
    assert not pressure_shell.splitter.childrenCollapsible()
    assert pressure_shell.controls_scroll.width() >= 320
    assert pressure_shell.results.width() >= 220
    pressure_editor = window.chamber_pressure_page.interval_editor
    assert pressure_editor is not None
    assert pressure_editor.detect_button.text() == (
        "Auto-Detect Interval from Chamber Pressure"
    )
    assert pressure_editor.minimumSizeHint().width() <= pressure_editor.width()
    assert pressure_editor.width() <= pressure_shell.controls_scroll.viewport().width()
    pressure_plot_widget = window.chamber_pressure_page.analysis_plot.plot_widget
    pressure_plot_widget.setXRange(4.0, 4.5, padding=0.0)
    pressure_plot_widget.setYRange(-1.0, -0.5, padding=0.0)
    window.chamber_pressure_page.reset_chart_button.click()
    app.processEvents()
    reset_x, reset_y = pressure_plot_widget.viewRange()
    assert reset_x[0] <= 0.0
    assert reset_x[1] >= 10.0
    assert reset_y[0] <= -2.0
    assert reset_y[1] >= 0.0
    window.navigation.setCurrentRow(1)
    app.processEvents()
    assert window.process_page.candidates_group is window.process_page.regions_group
    assert window.chamber_pressure_page.interval_editor is not None
    assert window.chamber_pressure_page.channel_group.title() == "Primary Channels"
    assert window.temperature_page.channel_group.title() == "Primary Channels"
    assert window.data_explorer_page.channel_group.title() == "Data Channel"
    assert window.chamber_pressure_page.view_group is None
    assert window.temperature_page.view_group is None
    assert window.chamber_pressure_page.curves_group is not None
    assert window.temperature_page.curves_group is not None
    assert set(window.chamber_pressure_page.curve_checks) == {"pressure"}
    assert (
        window.chamber_pressure_page.curve_checks["pressure"].text()
        == "Chamber Pressure"
    )
    assert window.chamber_pressure_page.metrics_table.rowCount() == 0
    assert window.chamber_pressure_page.calculate_button is not None
    window.chamber_pressure_page.calculate_button.click()
    app.processEvents()
    assert window.chamber_pressure_page.metrics_table.rowCount() == 5

    explorer = window.data_explorer_page
    explorer.show_auxiliary_check.setChecked(True)
    app.processEvents()
    web_index = explorer.channel_combo.findData("source/stream/web")
    assert web_index >= 0
    explorer.channel_combo.setCurrentIndex(web_index)
    app.processEvents()
    assert explorer.analysis_plot.left_axis.labelUnits == "mm"
    assert "kmm" not in explorer.analysis_plot.left_axis.labelText
    assert not explorer.analysis_plot.left_axis.autoSIPrefix

    window.resize(1280, 820)
    app.processEvents()
    assert shell.plot.width() >= compact_plot_width
    assert window.header_title.font().pixelSize() == 20
    assert window.header_title.width() > 0
    assert window.header_title.toolTip() == window.header_title.text()
    window.navigation.setCurrentRow(0)
    app.processEvents()
    assert project_page.splitter.orientation() is Qt.Orientation.Horizontal

    window._regions_store(
        {"pre": None, "active_test": [3.0, 7.0], "post": None}
    )
    assert not window.chamber_pressure_page.analysis_complete
    assert window.chamber_pressure_page.metrics_table.rowCount() == 0
    window._unit_display_mode_select(UNIT_DISPLAY_SI_SCIENTIFIC)
    app.processEvents()
    pressure_plot = window.chamber_pressure_page.analysis_plot
    temperature_plot = window.temperature_page.analysis_plot
    assert not pressure_plot.left_axis.autoSIPrefix
    assert not pressure_plot.bottom_axis.autoSIPrefix
    assert pressure_plot.left_axis.labelUnits == "Pa"
    assert temperature_plot.left_axis.labelUnits == "K"
    assert pressure_plot.left_axis.tickStrings([1_000_000.0], 1.0, 1.0) == [
        "1.000e+06"
    ]
    window.chamber_pressure_page.calculate_button.click()
    app.processEvents()
    pressure_value = window.chamber_pressure_page.metrics_table.item(0, 1).text()
    assert "e" in pressure_value.lower()
    window.close()
    app.processEvents()


def test_export_capabilities_group_sorting_and_one_time_defaults(
    tmp_path: Path,
) -> None:
    app = _application()
    window, _dataset = _window_with_bound_measurements(tmp_path)
    dialog = window.export_dialog
    other = ExportOption(
        "example.exporter.other",
        "other.txt",
        "",
        (),
        display_name="Other Export",
    )
    dialog._export_options_set((*dialog._options, other))
    assert dialog._options[-1].plugin_id == other.plugin_id
    group_order = [option.group_id for option in dialog._options]
    assert group_order == sorted(
        group_order,
        key={"overall": 0, "thrust": 10, "chamber_pressure": 20,
             "temperature": 30, "other": 1000}.get,
    )

    dialog.reset_default_selection()
    capabilities = (
        "project_summary_ready",
        "thrust_ready",
        "segmentation_ready",
        "physical_force",
        "chamber_pressure_ready",
    )
    dialog.set_completed_capability_ids(capabilities)
    for option in dialog._options:
        checkbox = dialog.exporter_checks[option.plugin_id]
        if option.group_id == "temperature":
            assert not checkbox.isEnabled()
            assert not checkbox.isChecked()
        else:
            assert checkbox.isEnabled()
            assert checkbox.isChecked()

    thrust_csv = dialog.exporter_checks["builtin.exporter.csv"]
    thrust_csv.setChecked(False)
    dialog.set_completed_capability_ids(capabilities)
    assert not thrust_csv.isChecked()

    dialog.set_completed_capability_ids((*capabilities, "temperature_ready"))
    for option in dialog._options:
        if option.group_id == "temperature":
            checkbox = dialog.exporter_checks[option.plugin_id]
            assert checkbox.isEnabled()
            assert checkbox.isChecked()

    dialog.set_completed_capability_ids(())
    dialog.reset_default_selection()
    dialog.set_selected_exporter_ids(())
    dialog.set_completed_capability_ids(capabilities)
    for option in dialog._options:
        if option.group_id in {"thrust", "chamber_pressure"}:
            checkbox = dialog.exporter_checks[option.plugin_id]
            assert checkbox.isEnabled()
            assert checkbox.isChecked() is option.default_selected
    window.close()
    app.processEvents()


def test_measurement_exports_unlock_only_after_explicit_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modal_errors: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, _title, message: (
            modal_errors.append(str(message))
            or QMessageBox.StandardButton.Ok
        ),
    )
    app = _application()
    window, _dataset = _window_with_bound_measurements(tmp_path)
    window._regions_store(
        {"pre": None, "active_test": [3.0, 7.0], "post": None}
    )
    pressure_checks = tuple(
        checkbox
        for plugin_id, checkbox in window.export_dialog.exporter_checks.items()
        if window.export_dialog.export_group_id(plugin_id) == "chamber_pressure"
    )
    temperature_checks = tuple(
        checkbox
        for plugin_id, checkbox in window.export_dialog.exporter_checks.items()
        if window.export_dialog.export_group_id(plugin_id) == "temperature"
    )
    assert pressure_checks and temperature_checks
    assert all(not checkbox.isEnabled() for checkbox in pressure_checks)
    assert all(not checkbox.isEnabled() for checkbox in temperature_checks)

    assert window.chamber_pressure_page.calculate_button is not None
    window.chamber_pressure_page.calculate_button.click()
    app.processEvents()
    assert window.chamber_pressure_page.analysis_complete
    assert all(checkbox.isEnabled() and checkbox.isChecked() for checkbox in pressure_checks)
    assert all(not checkbox.isEnabled() for checkbox in temperature_checks)

    assert window.temperature_page.calculate_button is not None
    window.temperature_page.calculate_button.click()
    app.processEvents()
    assert window.temperature_page.analysis_complete
    assert all(
        checkbox.isEnabled() and checkbox.isChecked()
        for checkbox in temperature_checks
    )

    bindings = window.session.project_data.primary_channels
    window.session.project_data = window.session.project_data.with_primary_channels(
        PrimaryChannelBindings(
            thrust=bindings.thrust,
            chamber_pressure=bindings.chamber_pressure,
            temperature_channels=(),
        )
    )
    window._measurement_workspaces_update()
    window._export_availability_update()
    assert not modal_errors
    assert window.chamber_pressure_page.analysis_complete
    assert not window.temperature_page.analysis_complete
    assert all(checkbox.isEnabled() for checkbox in pressure_checks)
    assert all(not checkbox.isEnabled() for checkbox in temperature_checks)
    window.session.project_data = window.session.project_data.with_primary_channels(
        bindings
    )
    window._measurement_workspaces_update()
    window._export_availability_update()
    window.temperature_page.calculate_button.click()
    app.processEvents()
    assert not modal_errors

    document = window._project_document_create()
    assert document.workflow_state["chamber_pressure_analyzed"]
    assert document.workflow_state["temperature_analyzed"]
    initialized = set(
        document.export_settings["selection_initialized_exporter_ids"]
    )
    assert {
        "builtin.exporter.chamber_pressure_csv",
        "builtin.exporter.chamber_pressure_png",
        "builtin.exporter.temperature_csv",
        "builtin.exporter.temperature_png",
    } <= initialized

    window._regions_store(
        {"pre": None, "active_test": [3.2, 6.8], "post": None}
    )
    assert not window.chamber_pressure_page.analysis_complete
    assert not window.temperature_page.analysis_complete
    assert all(
        not checkbox.isEnabled() and not checkbox.isChecked()
        for checkbox in pressure_checks
    )
    assert all(
        not checkbox.isEnabled() and not checkbox.isChecked()
        for checkbox in temperature_checks
    )
    window.close()
    app.processEvents()


def test_parser_ambiguity_has_exclusive_visible_radio_selection(
    tmp_path: Path,
) -> None:
    app = _application()
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    source = tmp_path / "ambiguous.txt"
    source.write_text("0,0\n0.1,1\n0.2,0\n", encoding="utf-8")
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id(None)
    window._parser_detect()
    _task_wait(window)
    page = window.import_page
    assert page.ambiguity_button_group.exclusive()
    assert len(page._ambiguity_buttons) == 3
    assert set(page.ambiguity_button_group.buttons()) == set(page._ambiguity_buttons)
    assert all("Confidence:" in button.text() for button in page._ambiguity_buttons)
    assert all("builtin.parser" not in button.text() for button in page._ambiguity_buttons)
    assert [button.text().split(" — ", 1)[0] for button in page._ambiguity_buttons] == [
        "TR_F",
        "TR_P",
        "TR_T",
    ]
    assert all(button.toolTip() for button in page._ambiguity_buttons)
    page._ambiguity_buttons[1].click()
    app.processEvents()
    assert sum(button.isChecked() for button in page._ambiguity_buttons) == 1
    assert page.selected_parser_id() is not None
    assert page.parse_button.isEnabled()
    assert page.parser_combo.currentText() in page.ambiguity_selected.text()
    assert app.style().pixelMetric(
        QStyle.PixelMetric.PM_ExclusiveIndicatorWidth
    ) == 18
    recommended_id = page.recommendation_table.item(0, 0).data(
        Qt.ItemDataRole.UserRole
    )
    page._recommendation_activate(0, 0)
    assert page.selected_parser_id() == recommended_id
    assert next(
        button
        for button in page._ambiguity_buttons
        if button.property("parserPluginId") == recommended_id
    ).isChecked()
    window.close()
    app.processEvents()


def test_source_removal_invalidates_derived_state_and_last_source_clears_ui(
    tmp_path: Path,
) -> None:
    app = _application()
    source_a = tmp_path / "source_a.txt"
    source_b = tmp_path / "source_b.txt"
    source_a.write_text("0,0\n1,5\n2,0\n", encoding="utf-8")
    source_b.write_text("0,0\n1,4\n2,0\n", encoding="utf-8")
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.import_page.set_source_entries([(source_a, 0.0), (source_b, 0.0)])
    window.import_page.set_parser_id("builtin.parser.tr_f")
    window.import_page.set_parser_config(
        {"delimiter": ",", "time_unit": "s", "invalid_row_policy": "skip"}
    )
    window._source_parse()
    _task_wait(window)
    reference = ChannelReference("source_1", "stream_1", "thrust_raw")
    bindings = window.session.project_data.primary_channels
    window._primary_bindings_changed(
        PrimaryChannelBindings(
            thrust=reference,
            chamber_pressure=bindings.chamber_pressure,
            temperature_channels=bindings.temperature_channels,
        )
    )
    window._regions_store(
        {"pre": None, "active_test": [0.5, 1.5], "post": None}
    )
    dataset = window.session.calibrated_streams["stream_1"]
    window.session.processing_result = ProcessingResult(dataset, (), {})
    window.session.analysis_result = AnalysisResult({"peak_value": 5.0}, (), {})
    window.session.export_settings = {"selected_exporter_ids": ["x"]}
    window.session.candidates = [
        BurnCandidate(0.5, 1.5, 5.0, 1.0, 5.0, 5.0, 2)
    ]

    window.import_page.source_list.setCurrentRow(0)
    window.import_page.remove_source_button.click()
    app.processEvents()
    assert set(window.session.project_data.sources) == {"source_2"}
    assert set(window.session.project_data.streams) == {"stream_2"}
    assert set(window.session.calibrated_streams) == {"stream_2"}
    assert window.session.project_data.primary_channels.thrust is None
    assert window.session.processing_result is None
    assert window.session.analysis_result is None
    assert not window.session.regions
    assert not window.session.candidates
    assert not window.session.export_settings
    assert window.session.active_stream_id == "stream_2"
    assert window.session.source_path == source_b.resolve()
    assert window.session.quality_report is not None
    assert window.session.quality_report.sample_count == 3
    assert window.import_page.summary_values["sample_count"].text() == "3"

    window.import_page.source_list.setCurrentRow(0)
    window.import_page.remove_source_button.click()
    app.processEvents()
    assert not window.session.project_data.sources
    assert not window.session.project_data.streams
    assert window.session.quality_report is None
    assert window.import_page.source_edit.text() == ""
    assert window.setup_page.channel_combo.count() == 0
    assert not window.process_page.analysis_plot._series
    assert not window.chamber_pressure_page.analysis_plot._series
    assert not window.temperature_page.analysis_plot._series
    assert all(
        not checkbox.isEnabled()
        for checkbox in window.export_dialog.exporter_checks.values()
    )
    window.close()
    app.processEvents()


def test_removing_pending_source_preserves_parsed_project_data(
    tmp_path: Path,
) -> None:
    app = _application()
    parsed = tmp_path / "parsed.txt"
    pending = tmp_path / "pending.txt"
    parsed.write_text("0,0\n1,2\n2,0\n", encoding="utf-8")
    pending.write_text("0,0\n1,3\n2,0\n", encoding="utf-8")
    window = _window(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        tmp_path,
    )
    window.import_page.set_source_path(parsed)
    window.import_page.set_parser_id("builtin.parser.tr_f")
    window._source_parse()
    _task_wait(window)
    original_project_data = window.session.project_data
    original_raw = window.session.raw_dataset
    window.import_page.add_source_paths([pending])
    window.import_page.remove_source_button.click()
    app.processEvents()
    assert window.session.project_data is original_project_data
    assert window.session.raw_dataset is original_raw
    assert window.import_page.source_paths() == (parsed,)
    window.close()
    app.processEvents()
