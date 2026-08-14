from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.app.session import AnalysisSession, ChannelCalibrationState
from underline_retldc.app.settings import (
    THEME_DARK,
    THEME_LIGHT,
    SettingsService,
    Theme_Normalize,
)
from underline_retldc.app.version import PRODUCT_NAME, __version__
from underline_retldc.core.calibration import (
    Calibration_Load,
    Calibration_Save,
    CalibrationDocument,
    CalibrationSelectionSource,
)
from underline_retldc.core.data_quality import Dataset_QualityInspect
from underline_retldc.core.defaults import FACTORY_DEFAULTS
from underline_retldc.core.parser_selection import (
    ParserSelection_Decide,
    ParserSelectionResult,
)
from underline_retldc.core.pipeline import (
    Calibration_Apply,
    Calibration_ApplyIdentityDefaults,
    Calibration_OutputChannelId,
    Processing_Passthrough,
)
from underline_retldc.core.primary_channels import (
    PrimaryChannels_AutoBind,
    PrimaryChannels_Candidates,
    PrimaryChannels_Validate,
)
from underline_retldc.core.project import (
    ChannelProjectState,
    PluginReference,
    Project_DefaultExportDirectory,
    Project_Load,
    Project_Save,
    Project_SourceHash,
    Project_SourceResolve,
    ProjectDocument,
    ProjectSourceHashMismatchError,
    ProjectSourceResolveResult,
    ProjectSourceState,
    ProjectStreamState,
)
from underline_retldc.core.project_data import (
    ChannelReference,
    PrimaryChannelBindings,
    ProjectData,
    Source,
    Stream,
)
from underline_retldc.core.region_detection import Activity_DetectSegments
from underline_retldc.core.regions import RegionSelection
from underline_retldc.core.registry import PluginLoadResult, PluginRegistry
from underline_retldc.core.segmentation import (
    Segmentation_RegionsAroundCandidate,
    Segmentation_SelectReference,
)
from underline_retldc.core.tabular import (
    Tabular_MappingSuggest,
    TabularPreset,
    TabularPreset_Load,
    TabularPreset_Save,
)
from underline_retldc.core.task import TaskHandle, TaskManager, TaskResult
from underline_retldc.core.units import Quantity_Dimension
from underline_retldc.core.workspace_capabilities import WorkspaceCapabilities_Default
from underline_retldc.gui.pages.analyze_page import AnalyzePage
from underline_retldc.gui.pages.export_page import ExportDialog
from underline_retldc.gui.pages.import_page import ImportPage
from underline_retldc.gui.pages.plugins_page import PluginsPage
from underline_retldc.gui.pages.process_page import ProcessPage
from underline_retldc.gui.pages.settings_page import SettingsPage
from underline_retldc.gui.pages.setup_page import SetupPage
from underline_retldc.gui.pages.workspace_pages import (
    ChamberPressureWorkspacePage,
    DataExplorerWorkspacePage,
    ProjectWorkspacePage,
    TemperatureWorkspacePage,
    ThrustAnalysisWorkspacePage,
    WorkspaceSeries,
)
from underline_retldc.gui.theme import Theme_Apply, Theme_DarkBarApply
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugin_api.common import (
    AnalysisResult,
    ParseResult,
    PluginType,
    ProbeContext,
    ProbeResult,
    ProcessingResult,
    TaskContext,
)
from underline_retldc.plugin_api.parser import TabularParserPlugin
from underline_retldc.plugin_api.processor import (
    PROCESSOR_ROLE_MOTOR_WEIGHT_COMPENSATION,
)
from underline_retldc.plugins.installer import (
    Plugin_UserDirectory,
    PluginInstaller_InstallDirectory,
)
from underline_retldc.plugins.loader import PluginDiscoveryRoot, PluginLoader

LOGGER = logging.getLogger(__name__)
FILE_DIALOG_OPTIONS = QFileDialog.Option.DontUseNativeDialog
THRUST_ANALYZER_ID = "builtin.analyzer.thrust"
DEFAULT_PARSER_ID = "builtin.parser.tr_f"
DEFAULT_CALIBRATION_ID = "builtin.calibration.identity"
DEFAULT_WEIGHT_PROCESSOR_ID = "builtin.processor.vertical_linear_baseline"


class MainWindow(QMainWindow):
    def __init__(
        self,
        translations: TranslationService,
        settings: SettingsService,
        *,
        project_root: Path | None = None,
        bundled_plugin_directory: Path | None = None,
        user_plugin_directory: Path | None = None,
        initial_theme: str | None = None,
    ) -> None:
        super().__init__()
        application = QApplication.instance()
        self._theme = Theme_Normalize(initial_theme or settings.theme())
        if application is not None:
            Theme_Apply(application, self._theme)
        self.translations = translations
        self.settings = settings
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.development_plugin_directory = (
            Path(bundled_plugin_directory)
            if bundled_plugin_directory is not None
            else self.project_root / "plugins"
        )
        self.user_plugin_directory = (
            Path(user_plugin_directory)
            if user_plugin_directory is not None
            else Plugin_UserDirectory()
        )
        self.registry = PluginRegistry()
        self.plugin_loader = PluginLoader(self.registry)
        self._plugins_initialized = False
        self.session = AnalysisSession()
        self.task_manager = TaskManager(max_workers=2)
        self._active_task: TaskHandle[Any] | None = None
        self._active_success: Callable[[Any], None] | None = None
        self._recommendations: list[tuple[Any, ProbeResult]] = []
        self._recommendation_source: Path | None = None
        self._recomputed_project_data = ProjectData()
        self._recomputed_calibrated_streams: dict[str, Any] = {}

        self.workspace_capabilities = WorkspaceCapabilities_Default()
        self.import_page = ImportPage(translations, self.workspace_capabilities)
        self.setup_page = SetupPage(translations)
        self.process_page = ProcessPage(translations)
        self.analyze_page = AnalyzePage(translations)
        self.project_page = ProjectWorkspacePage(
            translations, self.import_page, self.setup_page
        )
        self.thrust_analysis_page = ThrustAnalysisWorkspacePage(
            self.process_page, self.analyze_page
        )
        self.chamber_pressure_page = ChamberPressureWorkspacePage(translations)
        self.temperature_page = TemperatureWorkspacePage(translations)
        self.data_explorer_page = DataExplorerWorkspacePage(translations)
        self.analysis_page = self.thrust_analysis_page
        self.export_dialog = ExportDialog(translations, self)
        self.export_page = self.export_dialog
        self.plugins_page = PluginsPage(translations)
        self.settings_page = SettingsPage(
            translations,
            self._theme,
            self.settings.display_units(),
            self.settings.unit_display_mode(),
            self.settings.tabular_auto_mapping(),
            self.settings.tabular_auto_prefill(),
        )
        self.workspaces = (
            ("project", "page.project", self.project_page),
            ("thrust_analysis", "page.thrust_analysis", self.thrust_analysis_page),
            (
                "chamber_pressure",
                "page.chamber_pressure",
                self.chamber_pressure_page,
            ),
            ("temperature", "page.temperature", self.temperature_page),
            ("data_explorer", "page.data_explorer", self.data_explorer_page),
        )
        self.pages = tuple(page for _workspace_id, _translation_key, page in self.workspaces)
        self.plugins_dialog = QDialog(self)
        self.plugins_dialog.setModal(True)
        self.plugins_dialog.resize(1050, 620)
        plugins_layout = QVBoxLayout(self.plugins_dialog)
        plugins_layout.addWidget(self.plugins_page)
        self.settings_dialog = QDialog(self)
        self.settings_dialog.setModal(True)
        self.settings_dialog.resize(520, 320)
        settings_layout = QVBoxLayout(self.settings_dialog)
        settings_layout.addWidget(self.settings_page)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFixedWidth(150)
        self.navigation.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.navigation.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.stack = QStackedWidget()
        for page in self.pages:
            self.stack.addWidget(page)
        self.navigation.currentRowChanged.connect(self._page_selected)

        self.header_title = QLabel()
        self.header_title.setObjectName("headerTitle")
        self.version_label = QLabel()
        self.version_label.setObjectName("headerVersion")
        self.credit_separator = QLabel("·")
        self.credit_separator.setObjectName("headerCredit")
        self.credit_label = QLabel()
        self.credit_label.setObjectName("headerCredit")
        self.language_label = QLabel()
        self.language_label.setObjectName("headerLanguageLabel")
        self.language_combo = StandardComboBox()
        self.language_combo.addItem("简体中文", "zh_CN")
        self.language_combo.addItem("English", "en_US")
        self.language_combo.currentIndexChanged.connect(
            lambda _index: self._locale_select(str(self.language_combo.currentData()))
        )
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeToggleButton")
        self.theme_button.clicked.connect(self._theme_toggle)
        self.header_widget = QWidget()
        self.header_widget.setObjectName("headerBar")
        header = QHBoxLayout(self.header_widget)
        header.setContentsMargins(12, 5, 12, 5)
        header.addWidget(self.header_title, 1)
        header.addWidget(self.version_label)
        header.addWidget(self.credit_separator)
        header.addWidget(self.credit_label)
        header.addSpacing(8)
        header.addWidget(self.language_label)
        header.addWidget(self.language_combo)
        header.addWidget(self.theme_button)

        content = QHBoxLayout()
        content.addWidget(self.navigation)
        content.addWidget(self.stack, 1)
        central_layout = QVBoxLayout()
        central_layout.addWidget(self.header_widget)
        central_layout.addLayout(content, 1)
        central = QWidget()
        central.setObjectName("centralRoot")
        central.setLayout(central_layout)
        self.setCentralWidget(central)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setMaximumWidth(240)
        self.progress_bar.hide()
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self._task_cancel)
        self.cancel_button.hide()
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.statusBar().addPermanentWidget(self.cancel_button)
        self.task_timer = QTimer(self)
        self.task_timer.setInterval(80)
        self.task_timer.timeout.connect(self._task_poll)

        self.menuBar().setObjectName("mainMenuBar")
        Theme_DarkBarApply(self.menuBar())
        self.project_menu = self.menuBar().addMenu("")
        self.new_project_action = QAction(self)
        self.new_project_action.triggered.connect(self._project_new)
        self.open_raw_action = QAction(self)
        self.open_raw_action.triggered.connect(self._source_open_dialog)
        self.open_project_action = QAction(self)
        self.open_project_action.triggered.connect(self._project_open_dialog)
        self.save_project_action = QAction(self)
        self.save_project_action.triggered.connect(self._project_save_dialog)
        self.exit_action = QAction(self)
        self.exit_action.triggered.connect(self.close)
        self.project_menu.addAction(self.new_project_action)
        self.project_menu.addAction(self.open_raw_action)
        self.project_menu.addSeparator()
        self.project_menu.addAction(self.open_project_action)
        self.project_menu.addAction(self.save_project_action)
        self.project_menu.addSeparator()
        self.project_menu.addAction(self.exit_action)

        self.export_action = QAction(self)
        self.export_action.triggered.connect(self._export_dialog_show)
        self.export_menu = self.menuBar().addMenu("")
        self.export_menu.addAction(self.export_action)
        self.tools_menu = self.menuBar().addMenu("")
        self.plugins_action = QAction(self)
        self.plugins_action.triggered.connect(self.plugins_dialog.show)
        self.settings_action = QAction(self)
        self.settings_action.triggered.connect(self.settings_dialog.show)
        self.tools_menu.addAction(self.plugins_action)
        self.tools_menu.addAction(self.settings_action)
        self.toolbar = QToolBar(self)
        self.toolbar.setObjectName("mainToolBar")
        Theme_DarkBarApply(self.toolbar, self._theme)
        self.toolbar.setMovable(False)
        self.toolbar.addAction(self.open_raw_action)
        self.toolbar.addAction(self.save_project_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.export_action)
        self.addToolBar(self.toolbar)

        self._project_title: str | None = None
        self._signals_connect()
        self._plugins_refresh()
        self.process_page.set_theme(self._theme)
        for page in self._measurement_pages():
            page.set_theme(self._theme)
        self.process_page.set_display_preferences(self.settings.display_units())
        self.process_page.set_display_mode(self.settings.unit_display_mode())
        self.analyze_page.set_display_configuration(
            self.settings.display_units(),
            self.settings.unit_display_mode(),
        )
        self.setup_page.set_display_preferences(self.settings.display_units())
        for page in self._measurement_pages():
            page.set_display_preferences(self.settings.display_units())
            page.set_display_mode(self.settings.unit_display_mode())
        self._segmentation_views_sync()
        self.translations.locale_changed.connect(self._retranslate)
        self._locale_widgets_sync(self.translations.locale)
        self._retranslate()
        self.navigation.setCurrentRow(0)
        self.resize(1280, 820)
        self.setMinimumSize(980, 640)

    def _signals_connect(self) -> None:
        self.import_page.browse_requested.connect(self._source_browse)
        self.import_page.detect_requested.connect(self._parser_detect)
        self.import_page.parse_requested.connect(self._source_parse)
        self.import_page.parser_changed.connect(self._parser_selection_changed)
        self.import_page.source_selected.connect(self._source_selection_changed)
        self.import_page.source_removed.connect(self._source_removed)
        tabular_editor = self.import_page.tabular_mapping_editor
        tabular_editor.preview_requested.connect(self._tabular_preview_refresh)
        tabular_editor.preset_selected.connect(self._tabular_preset_select)
        tabular_editor.preset_save_requested.connect(self._tabular_preset_save)
        tabular_editor.preset_delete_requested.connect(self._tabular_preset_delete)
        tabular_editor.preset_import_requested.connect(self._tabular_preset_import)
        tabular_editor.preset_export_requested.connect(self._tabular_preset_export)
        self.setup_page.apply_requested.connect(self._calibration_apply)
        self.setup_page.load_requested.connect(self._calibration_load_dialog)
        self.setup_page.save_requested.connect(self._calibration_save_dialog)
        self.setup_page.channel_changed.connect(self._calibration_channel_changed)
        self.project_page.primary_channels.bindings_changed.connect(
            self._primary_bindings_changed
        )
        self.process_page.detect_requested.connect(self._burn_detect)
        self.process_page.apply_requested.connect(self._processing_apply)
        self.process_page.plugins_requested.connect(self._plugins_dialog_show)
        self.process_page.regions_changed.connect(self._regions_store)
        self.process_page.candidate_selected.connect(
            self._segmentation_candidate_select
        )
        self.process_page.primary_thrust_changed.connect(
            self._primary_thrust_quick_changed
        )
        self.process_page.select_thrust_requested.connect(
            lambda: self._workspace_select("project")
        )
        self.chamber_pressure_page.primary_channel_changed.connect(
            self._primary_pressure_quick_changed
        )
        self.chamber_pressure_page.detect_requested.connect(self._burn_detect)
        self.chamber_pressure_page.regions_changed.connect(self._regions_store)
        self.chamber_pressure_page.candidate_selected.connect(
            self._segmentation_candidate_select
        )
        self.temperature_page.temperature_channels_changed.connect(
            self._primary_temperature_quick_changed
        )
        self.chamber_pressure_page.select_channel_requested.connect(
            lambda: self._workspace_select("project")
        )
        self.temperature_page.select_channel_requested.connect(
            lambda: self._workspace_select("project")
        )
        self.analyze_page.calculate_requested.connect(self._analysis_calculate)
        self.analyze_page.confirmation_changed.connect(self._curve_confirmation_update)
        self.export_dialog.export_requested.connect(self._export_execute)
        self.plugins_page.refresh_requested.connect(self._plugins_refresh)
        self.plugins_page.install_requested.connect(self._plugin_install_dialog)
        self.plugins_page.open_development_requested.connect(
            lambda: self._directory_open(self.development_plugin_directory)
        )
        self.plugins_page.open_user_requested.connect(
            lambda: self._directory_open(self.user_plugin_directory)
        )
        self.settings_page.locale_selected.connect(self._locale_select)
        self.settings_page.theme_selected.connect(self._theme_select)
        self.settings_page.display_unit_selected.connect(self._display_unit_select)
        self.settings_page.unit_display_mode_selected.connect(
            self._unit_display_mode_select
        )
        self.settings_page.tabular_auto_mapping_selected.connect(
            self.settings.set_tabular_auto_mapping
        )
        self.settings_page.tabular_auto_prefill_selected.connect(
            self.settings.set_tabular_auto_prefill
        )

    def _retranslate(self) -> None:
        t = self.translations.translate
        self.setWindowTitle(f"{PRODUCT_NAME} — {__version__}")
        self.header_title.setText(
            f"{PRODUCT_NAME} · {self._project_title or t('project.untitled')}"
        )
        self.version_label.setText(t("app.version", version=__version__))
        self.credit_label.setText(t("app.credit"))
        self.language_label.setText(t("settings.language"))
        self.theme_button.setText(
            t("theme.light_mode" if self._theme == THEME_DARK else "theme.dark_mode")
        )
        current_row = self.navigation.currentRow()
        self.navigation.clear()
        for _workspace_id, translation_key, _page in self.workspaces:
            self.navigation.addItem(t(translation_key))
        self.navigation.setCurrentRow(max(0, current_row))
        for page in self.pages:
            page.retranslate()
        self.plugins_page.retranslate()
        self.settings_page.retranslate()
        self.plugins_page.set_records(self.registry.records)
        self.project_menu.setTitle(t("menu.file"))
        self.new_project_action.setText(t("menu.project.new"))
        self.open_raw_action.setText(t("menu.project.open_raw"))
        self.open_project_action.setText(t("menu.project.open"))
        self.save_project_action.setText(t("menu.project.save"))
        self.exit_action.setText(t("menu.project.exit"))
        self.export_menu.setTitle(t("page.export"))
        self.export_action.setText(t("export.dialog_title"))
        self.tools_menu.setTitle(t("menu.tools"))
        self.plugins_action.setText(t("page.plugins"))
        self.settings_action.setText(t("page.settings"))
        self.plugins_dialog.setWindowTitle(t("page.plugins"))
        self.settings_dialog.setWindowTitle(t("page.settings"))
        self.export_dialog.retranslate()
        self.cancel_button.setText(t("common.cancel"))
        if self._active_task is None:
            self.statusBar().showMessage(t("common.ready"))

    def _theme_toggle(self) -> None:
        self._theme_select(
            THEME_LIGHT if self._theme == THEME_DARK else THEME_DARK
        )

    def _theme_select(self, theme: str) -> None:
        normalized = Theme_Normalize(theme)
        self._theme = normalized
        self.settings.set_theme(normalized)
        application = QApplication.instance()
        if application is not None:
            Theme_Apply(application, normalized)
        Theme_DarkBarApply(self.menuBar(), normalized)
        Theme_DarkBarApply(self.toolbar, normalized)
        self.process_page.set_theme(normalized)
        for page in self._measurement_pages():
            page.set_theme(normalized)
        self.settings_page.set_theme(normalized)
        self._retranslate()

    def _plugins_dialog_show(self) -> None:
        self.plugins_dialog.show()
        self.plugins_dialog.raise_()

    def _display_unit_select(self, quantity: str, unit: str) -> None:
        self.settings.set_display_unit(quantity, unit)
        self.process_page.set_display_preferences(self.settings.display_units())
        self.setup_page.set_display_preferences(self.settings.display_units())
        for page in self._measurement_pages():
            page.set_display_preferences(self.settings.display_units())
        self.analyze_page.set_display_configuration(
            self.settings.display_units(),
            self.settings.unit_display_mode(),
        )

    def _unit_display_mode_select(self, mode: str) -> None:
        self.settings.set_unit_display_mode(mode)
        self.process_page.set_display_mode(mode)
        for page in self._measurement_pages():
            page.set_display_mode(mode)
        self.analyze_page.set_display_configuration(
            self.settings.display_units(),
            mode,
        )
        self.settings_page.set_unit_display_mode(mode)

    def _locale_select(self, locale: str) -> None:
        if not locale:
            return
        self.settings.set_locale(locale)
        self.translations.set_locale(locale)
        self._locale_widgets_sync(locale)

    def _locale_widgets_sync(self, locale: str) -> None:
        index = self.language_combo.findData(locale)
        if index < 0:
            index = self.language_combo.findData("en_US")
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(index)
        self.language_combo.blockSignals(False)
        self.settings_page.set_locale(locale)
        self.settings_page.set_theme(self._theme)
        if hasattr(self, "export_dialog"):
            self.export_dialog.retranslate()

    def _page_selected(self, index: int) -> None:
        if 0 <= index < len(self.pages):
            self.stack.setCurrentIndex(index)

    def _workspace_select(self, workspace_id: str) -> None:
        for index, (candidate_id, _translation_key, _page) in enumerate(self.workspaces):
            if candidate_id == workspace_id:
                self.navigation.setCurrentRow(index)
                return
        raise KeyError(f"Unknown workspace ID {workspace_id!r}")

    def _measurement_pages(self) -> tuple[Any, ...]:
        return (
            self.chamber_pressure_page,
            self.temperature_page,
            self.data_explorer_page,
        )

    def _primary_channels_update(self) -> None:
        self.project_page.primary_channels.set_project_data(
            self.session.project_data,
            self.session.project_data.primary_channels,
        )
        bindings = self.session.project_data.primary_channels
        thrust_choices = tuple(
            (self._channel_reference_label(reference), reference)
            for reference in PrimaryChannels_Candidates(
                self.session.project_data,
                dimension="force",
            )
        )
        self.process_page.set_thrust_choices(thrust_choices, bindings.thrust)
        if bindings.thrust is None:
            self.process_page.set_datasets(None, None, None, input_channel_id=None)
            return
        raw_stream = self.session.project_data.streams[bindings.thrust.stream_id]
        calibrated, input_channel_id = self._calibrated_binding_resolve(
            bindings.thrust
        )
        processed = (
            self.session.processed_dataset
            if bindings.thrust.stream_id == self.session.primary_stream_id
            else None
        )
        self.process_page.set_datasets(
            raw_stream.dataset,
            calibrated,
            processed,
            input_channel_id=input_channel_id,
        )

    def _channel_reference_label(self, reference: ChannelReference) -> str:
        source = self.session.project_data.sources[reference.source_id]
        channel = self.session.project_data.channel(reference)
        return f"{source.path.name} · {channel.name} [{channel.data_unit}]"

    def _calibrated_binding_resolve(
        self,
        reference: ChannelReference,
    ) -> tuple[Any, str]:
        dataset = self.session.calibrated_streams.get(reference.stream_id)
        if dataset is None:
            raise ValueError(
                f"Calibrated Stream {reference.stream_id!r} is not available"
            )
        key = self._channel_reference_key(
            reference.source_id,
            reference.stream_id,
            reference.channel_id,
        )
        state = self.session.stream_channel_calibrations.get(key)
        if state is None and reference.stream_id == self.session.primary_stream_id:
            state = self.session.channel_calibrations.get(reference.channel_id)
        if state is None or state.output_channel_id not in dataset.channels:
            raise ValueError(
                "Primary Channel has no resolved Calibration output: "
                f"{reference.stable_id}"
            )
        return dataset, state.output_channel_id

    def _primary_thrust_quick_changed(self, reference: object) -> None:
        if reference is not None and not isinstance(reference, ChannelReference):
            return
        bindings = self.session.project_data.primary_channels
        self._primary_bindings_changed(
            PrimaryChannelBindings(
                thrust=reference,
                chamber_pressure=bindings.chamber_pressure,
                temperature_channels=bindings.temperature_channels,
            )
        )

    def _primary_pressure_quick_changed(self, reference: object) -> None:
        if reference is not None and not isinstance(reference, ChannelReference):
            return
        bindings = self.session.project_data.primary_channels
        self._primary_bindings_changed(
            PrimaryChannelBindings(
                thrust=bindings.thrust,
                chamber_pressure=reference,
                temperature_channels=bindings.temperature_channels,
            )
        )

    def _primary_temperature_quick_changed(self, references: object) -> None:
        if not isinstance(references, tuple) or any(
            not isinstance(item, ChannelReference) for item in references
        ):
            return
        bindings = self.session.project_data.primary_channels
        self._primary_bindings_changed(
            PrimaryChannelBindings(
                thrust=bindings.thrust,
                chamber_pressure=bindings.chamber_pressure,
                temperature_channels=references,
            )
        )

    def _primary_bindings_changed(
        self,
        bindings: PrimaryChannelBindings,
    ) -> None:
        try:
            PrimaryChannels_Validate(self.session.project_data, bindings)
        except ValueError as exc:
            self._error_show(exc)
            self._primary_channels_update()
            return
        previous = self.session.project_data.primary_channels
        self.session.project_data = self.session.project_data.with_primary_channels(
            bindings
        )
        workflow_input_changed = (
            previous.thrust != bindings.thrust
            or previous.chamber_pressure != bindings.chamber_pressure
        )
        if previous.thrust != bindings.thrust:
            if bindings.thrust is not None:
                stream = self.session.project_data.streams[bindings.thrust.stream_id]
                self.session.primary_stream_id = stream.id
                self.session.active_stream_id = stream.id
                self.session.raw_dataset = stream.dataset
                self.session.calibrated_dataset = self.session.calibrated_streams.get(
                    stream.id
                )
                self.session.channel_calibrations = (
                    self._active_channel_calibrations()
                )
            self.session.reset_after_calibration()
            self.analyze_page.clear_result()
        elif workflow_input_changed:
            self.session.candidates.clear()
            self.session.regions.clear()
            self.session.segmentation_reference = None
            self.session.segmentation_reference_priority = None
            self.session.segmentation_manually_modified = False
            self.session.processing_result = None
            self.session.analysis_result = None
            self.analyze_page.clear_result()
        self._primary_channels_update()
        self._measurement_workspaces_update()
        self._segmentation_views_sync()
        self._export_availability_update()

    def _measurement_workspaces_update(self) -> None:
        series: list[WorkspaceSeries] = []
        for reference in self.session.project_data.channel_references():
            raw_channel = self.session.project_data.channel(reference)
            try:
                dataset, channel_id = self._calibrated_binding_resolve(reference)
            except ValueError:
                dataset = self.session.project_data.streams[reference.stream_id].dataset
                channel_id = reference.channel_id
            channel = dataset.channel(channel_id)
            source = self.session.project_data.sources[reference.source_id]
            series.append(
                WorkspaceSeries(
                    reference=reference,
                    dataset=dataset,
                    channel_id=channel_id,
                    label=f"{source.path.name} · {raw_channel.name} [{channel.data_unit}]",
                    auxiliary=(
                        raw_channel.semantic_role == "auxiliary"
                        or raw_channel.metadata.get("workspace_category") == "other"
                    ),
                )
            )
        bindings = self.session.project_data.primary_channels
        pressure_series = tuple(
            item
            for item in series
            if not item.auxiliary
            and Quantity_Dimension(
                item.dataset.channel(item.channel_id).quantity
            )
            == "pressure"
        )
        temperature_series = tuple(
            item
            for item in series
            if not item.auxiliary
            and Quantity_Dimension(
                item.dataset.channel(item.channel_id).quantity
            )
            == "temperature"
        )
        explorer_selection = self.data_explorer_page.selected_references()
        self.chamber_pressure_page.set_series(
            pressure_series,
            selected=bindings.chamber_pressure,
        )
        self.temperature_page.set_series(
            temperature_series,
            selected=bindings.temperature_channels,
        )
        self.data_explorer_page.set_series(
            series,
            selected=explorer_selection or None,
        )
        for page in self._measurement_pages():
            page.set_regions(self.session.regions)

    @staticmethod
    def _channel_reference_key(
        source_id: str, stream_id: str, channel_id: str
    ) -> str:
        return ChannelReference(source_id, stream_id, channel_id).stable_id

    def _active_stream(self) -> Stream | None:
        stream_id = self.session.active_stream_id or self.session.primary_stream_id
        if stream_id is None:
            return None
        return self.session.project_data.streams.get(stream_id)

    def _active_channel_calibrations(self) -> dict[str, ChannelCalibrationState]:
        stream = self._active_stream()
        if stream is None:
            return self.session.channel_calibrations
        states: dict[str, ChannelCalibrationState] = {}
        for channel_id in stream.dataset.channels:
            key = self._channel_reference_key(stream.source_id, stream.id, channel_id)
            state = self.session.stream_channel_calibrations.get(key)
            if state is not None:
                states[channel_id] = state
        return states

    @staticmethod
    def _project_channel_states_for_stream(
        document: ProjectDocument,
        source_id: str,
        stream_id: str,
        *,
        include_legacy: bool = False,
    ) -> tuple[ChannelProjectState, ...]:
        selected: dict[str, ChannelProjectState] = {}
        for state in document.channels.values():
            is_exact = (
                state.stream_id == stream_id
                and state.source_id in (None, source_id)
            )
            is_legacy = (
                include_legacy
                and state.stream_id is None
                and state.source_id is None
            )
            if is_exact or (is_legacy and state.channel_id not in selected):
                selected[state.channel_id] = state
        return tuple(selected.values())

    def _completed_analysis_ids(self) -> tuple[str, ...]:
        if self.session.analysis_result is None or self.session.analyzer_id is None:
            return ()
        return (self.session.analyzer_id,)

    def _binding_has_valid_data(
        self,
        reference: ChannelReference | None,
        *,
        dimension: str,
    ) -> bool:
        if reference is None:
            return False
        try:
            dataset, channel_id = self._calibrated_binding_resolve(reference)
            channel = dataset.channel(channel_id)
        except (KeyError, ValueError):
            return False
        finite = np.isfinite(dataset.project_time) & np.isfinite(channel.values)
        return (
            Quantity_Dimension(channel.quantity) == dimension
            and int(np.count_nonzero(finite)) >= 2
        )

    def _export_availability_update(self) -> None:
        self.export_dialog.set_completed_analysis_ids(self._completed_analysis_ids())
        capabilities: set[str] = set()
        bindings = self.session.project_data.primary_channels
        active = self.session.regions.get(
            "active_test",
            self.session.regions.get("burn"),
        )
        if active is not None and len(active) == 2 and float(active[0]) < float(active[1]):
            capabilities.add("segmentation_ready")
        if self.session.analysis_result is not None:
            capabilities.add("project_summary_ready")
        if (
            self.session.processing_result is not None
            and self.session.analysis_result is not None
            and bindings.thrust is not None
            and "segmentation_ready" in capabilities
        ):
            capabilities.add("thrust_ready")
        if self._binding_has_valid_data(
            bindings.chamber_pressure,
            dimension="pressure",
        ):
            capabilities.add("chamber_pressure_ready")
        if any(
            self._binding_has_valid_data(reference, dimension="temperature")
            for reference in bindings.temperature_channels
        ):
            capabilities.add("temperature_ready")
        if (
            self.session.analysis_result is not None
            and bool(
                self.session.analysis_result.metadata.get(
                    "physical_force_available", False
                )
            )
        ):
            capabilities.add("physical_force")
        self.export_dialog.set_completed_capability_ids(tuple(sorted(capabilities)))

    def _task_start(
        self,
        name: str,
        operation: Callable[[TaskContext], Any],
        success: Callable[[Any], None],
    ) -> None:
        if self._active_task is not None and not self._active_task.done:
            QMessageBox.information(self, PRODUCT_NAME, self._active_task.name)
            return
        self._active_success = success
        self._active_task = self.task_manager.submit(name, operation)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.cancel_button.show()
        self.statusBar().showMessage(name)
        self.task_timer.start()

    def _task_poll(self) -> None:
        handle = self._active_task
        if handle is None:
            self.task_timer.stop()
            return
        self.progress_bar.setValue(round(handle.progress * 1000))
        if handle.message:
            self.statusBar().showMessage(handle.message)
        if not handle.done:
            return
        self.task_timer.stop()
        self.progress_bar.hide()
        self.cancel_button.hide()
        callback = self._active_success
        self._active_task = None
        self._active_success = None
        if handle.state is TaskResult.SUCCESS:
            try:
                if callback is not None:
                    callback(handle.result)
            except BaseException as exc:
                self._error_show(exc)
            return
        if handle.state is TaskResult.CANCELLED:
            self.statusBar().showMessage(self.translations.translate("common.cancel"), 4000)
            return
        exception = handle.exception or RuntimeError("Task failed")
        LOGGER.error(
            "Background task %s failed",
            handle.name,
            exc_info=(type(exception), exception, exception.__traceback__),
        )
        self._error_show(exception)

    def _task_cancel(self) -> None:
        if self._active_task is not None:
            self._active_task.cancel()

    def _error_show(self, error: BaseException) -> None:
        message = str(error)
        if isinstance(error, ProjectSourceHashMismatchError):
            message = self.translations.translate(
                "project.source_hash_mismatch",
                expected=error.expected_hash,
                actual=error.actual_hash,
            )
        QMessageBox.critical(
            self,
            self.translations.translate("common.error"),
            message,
        )

    def _dialog_start_directory(self) -> str:
        return str(self.settings.last_directory())

    def _last_directory_store(self, path: Path) -> None:
        self.settings.set_last_directory(path if path.is_dir() else path.parent)

    def _project_new(self) -> None:
        self.session = AnalysisSession()
        self._project_title = None
        self._recommendations.clear()
        self._recommendation_source = None
        self.import_page.set_source_entries(())
        self.import_page.clear_results()
        self.process_page.clear_state()
        self.analyze_page.clear_result()
        self._measurement_workspaces_update()
        self._segmentation_views_sync()
        self._primary_channels_update()
        self._export_availability_update()
        self.setup_page.set_motor_metadata({})
        self.export_dialog.directory_edit.clear()
        self.export_dialog.reset_default_selection()
        self.export_dialog.set_motor_metadata({})
        self.export_dialog.set_output_locale(self.translations.locale)
        self.import_page.set_parser_id(None)
        self._parser_selection_changed(None)
        identity_index = self.setup_page.calibration_combo.findData(
            DEFAULT_CALIBRATION_ID
        )
        if identity_index >= 0:
            self.setup_page.calibration_combo.setCurrentIndex(identity_index)
        processor_index = self.process_page.processor_combo.findData(
            DEFAULT_WEIGHT_PROCESSOR_ID
        )
        self.process_page.processor_combo.setCurrentIndex(max(0, processor_index))
        self.navigation.setCurrentRow(0)
        self._retranslate()

    def _source_open_dialog(self) -> None:
        sources, _filter = QFileDialog.getOpenFileNames(
            self,
            self.translations.translate("dialog.select_source"),
            self._dialog_start_directory(),
            "Test data (*.txt *.csv *.log *.xlsx);;All files (*)",
            options=FILE_DIALOG_OPTIONS,
        )
        if sources:
            paths = [Path(source) for source in sources]
            self._project_new()
            self.import_page.add_source_paths(paths)
            self._last_directory_store(paths[0])
            if FACTORY_DEFAULTS.parser_auto_probe:
                self._parser_detect()

    def _source_browse(self) -> None:
        sources, _filter = QFileDialog.getOpenFileNames(
            self,
            self.translations.translate("dialog.select_source"),
            self._dialog_start_directory(),
            "Test data (*.txt *.csv *.log *.xlsx);;All files (*)",
            options=FILE_DIALOG_OPTIONS,
        )
        if sources:
            paths = [Path(source) for source in sources]
            self.import_page.add_source_paths(paths)
            self._last_directory_store(paths[0])
            if FACTORY_DEFAULTS.parser_auto_probe:
                self._parser_detect()

    def _source_selection_changed(self, path_text: str) -> None:
        if not self.session.project_data.streams:
            return
        try:
            selected_path = Path(path_text).resolve()
        except OSError:
            return
        stream = next(
            (
                candidate
                for candidate in self.session.project_data.streams.values()
                if self.session.project_data.sources[
                    candidate.source_id
                ].path.resolve()
                == selected_path
            ),
            None,
        )
        if stream is None:
            return
        self.session.active_stream_id = stream.id
        source = self.session.project_data.sources[stream.source_id]
        self.session.source_path = source.path
        self.session.source_hash = source.sha256
        self.session.parser_id = source.parser_id
        self.session.parser_config = dict(source.parser_config)
        self.session.raw_dataset = stream.dataset
        self.session.calibrated_dataset = self.session.calibrated_streams.get(stream.id)
        self.session.channel_calibrations = self._active_channel_calibrations()
        if source.parser_id is not None:
            self.import_page.set_parser_id(source.parser_id)
            self.import_page.set_parser_config(dict(source.parser_config))
        report = Dataset_QualityInspect(stream.dataset)
        self.session.quality_report = report
        self.import_page.set_summary(report)
        self.import_page.set_diagnostics(stream.dataset.diagnostics)
        preferred = next(
            (
                channel.id
                for channel in stream.dataset.channels.values()
                if channel.semantic_role == "thrust"
            ),
            next(iter(stream.dataset.channels), None),
        )
        self.setup_page.set_channels(
            list(stream.dataset.channels.values()), preferred_id=preferred
        )
        if preferred is not None:
            state = self._active_channel_calibrations().get(preferred)
            if state is not None:
                self.setup_page.set_calibration_config(
                    state.plugin_id, dict(state.config)
                )
        if self.import_page.uses_tabular_mapping():
            QTimer.singleShot(0, lambda: self._tabular_preview_refresh(False))

    @staticmethod
    def _path_matches(left: Path, right: Path) -> bool:
        try:
            return left.resolve() == right.resolve()
        except OSError:
            return left == right

    def _source_removed(self, path_text: str) -> None:
        removed_path = Path(path_text)
        removed_source_ids = {
            source_id
            for source_id, source in self.session.project_data.sources.items()
            if self._path_matches(source.path, removed_path)
        }
        if not removed_source_ids:
            if (
                self._recommendation_source is not None
                and self._path_matches(self._recommendation_source, removed_path)
            ):
                self._recommendations.clear()
                self._recommendation_source = None
                self.import_page.clear_results()
                self.import_page.tabular_mapping_editor.set_parser("", "", "")
            return

        removed_stream_ids = {
            stream_id
            for stream_id, stream in self.session.project_data.streams.items()
            if stream.source_id in removed_source_ids
        }
        sources = {
            source_id: source
            for source_id, source in self.session.project_data.sources.items()
            if source_id not in removed_source_ids
        }
        streams = {
            stream_id: stream
            for stream_id, stream in self.session.project_data.streams.items()
            if stream_id not in removed_stream_ids
        }
        previous_bindings = self.session.project_data.primary_channels

        def retained(reference: ChannelReference | None) -> ChannelReference | None:
            if reference is None or reference.stream_id in removed_stream_ids:
                return None
            return reference

        bindings = PrimaryChannelBindings(
            thrust=retained(previous_bindings.thrust),
            chamber_pressure=retained(previous_bindings.chamber_pressure),
            temperature_channels=tuple(
                reference
                for reference in previous_bindings.temperature_channels
                if reference.stream_id not in removed_stream_ids
            ),
        )
        self.session.project_data = ProjectData(sources, streams, bindings)
        self.session.calibrated_streams = {
            stream_id: dataset
            for stream_id, dataset in self.session.calibrated_streams.items()
            if stream_id not in removed_stream_ids
        }
        self.session.stream_channel_calibrations = {
            key: state
            for key, state in self.session.stream_channel_calibrations.items()
            if key.split("/", 2)[1] not in removed_stream_ids
        }

        self.session.candidates.clear()
        self.session.regions.clear()
        self.session.segmentation_reference = None
        self.session.segmentation_reference_priority = None
        self.session.segmentation_manually_modified = False
        self.session.processor_id = None
        self.session.processor_config.clear()
        self.session.processing_result = None
        self.session.analyzer_id = None
        self.session.analyzer_config.clear()
        self.session.analysis_result = None
        self.session.curve_confirmed = False
        self.session.export_settings.clear()
        self.session.quality_report = None
        self.analyze_page.clear_result()

        active_stream_id = self.session.active_stream_id
        if active_stream_id in removed_stream_ids:
            active_stream_id = None
        if active_stream_id is None and bindings.thrust is not None:
            active_stream_id = bindings.thrust.stream_id
        if active_stream_id is None and streams:
            active_stream_id = next(iter(streams))
        self.session.active_stream_id = active_stream_id
        self.session.primary_stream_id = (
            bindings.thrust.stream_id
            if bindings.thrust is not None
            else active_stream_id
        )

        if active_stream_id is None:
            self.session.source_path = None
            self.session.source_hash = None
            self.session.parser_id = None
            self.session.parser_config.clear()
            self.session.raw_dataset = None
            self.session.calibrated_dataset = None
            self.session.channel_calibrations.clear()
            self.session.calibration_id = None
            self.session.calibration_config.clear()
            self.import_page.clear_results()
            self.import_page.set_parser_schema(
                {"type": "object", "properties": {}}
            )
            self.import_page.tabular_mapping_editor.set_parser("", "", "")
            self.setup_page.set_channels([], preferred_id=None)
        else:
            active_stream = streams[active_stream_id]
            active_source = sources[active_stream.source_id]
            self.session.source_path = active_source.path
            self.session.source_hash = active_source.sha256
            self.session.parser_id = active_source.parser_id
            self.session.parser_config = dict(active_source.parser_config)
            self.session.raw_dataset = active_stream.dataset
            self.session.calibrated_dataset = self.session.calibrated_streams.get(
                active_stream_id
            )
            self.session.channel_calibrations = self._active_channel_calibrations()

        self._recommendations.clear()
        self._recommendation_source = None
        self.import_page.clear_results()
        self.process_page.clear_state()
        self._primary_channels_update()
        self._measurement_workspaces_update()
        self._segmentation_views_sync()
        self._export_availability_update()
        if active_stream_id is not None:
            self._source_selection_changed(str(sources[streams[active_stream_id].source_id].path))

    def _parser_selection_changed(self, plugin_id: str | None) -> None:
        if plugin_id is None:
            self.import_page.set_parser_schema({"type": "object", "properties": {}})
            return
        try:
            plugin = self.registry.get(plugin_id)
            schema = plugin.config_schema()
            properties = schema.get("properties", {})
            config = {
                key: value["default"]
                for key, value in properties.items()
                if isinstance(value, dict) and "default" in value
            }
            self.import_page.set_parser_schema(
                schema,
                config,
                parser_id=plugin.descriptor.plugin_id,
                parser_version=plugin.descriptor.version,
            )
            if isinstance(plugin, TabularParserPlugin):
                self._tabular_presets_refresh()
                QTimer.singleShot(0, self._tabular_auto_preview)
        except (KeyError, TypeError, ValueError) as exc:
            self._error_show(exc)

    def _tabular_user_preset_directory(self) -> Path:
        return self.user_plugin_directory.parent / "presets" / "tabular"

    def _tabular_presets_refresh(self, selected_path: str | None = None) -> None:
        editor = self.import_page.tabular_mapping_editor
        parser_id = editor.parser_id
        parser_version = editor.parser_version
        entries: list[tuple[str, str, bool]] = []
        roots = (
            (self._tabular_user_preset_directory(), False),
            (self.project_root / "presets" / "tabular", True),
        )
        visited_roots: set[Path] = set()
        for root, builtin in roots:
            resolved_root = root.resolve()
            if resolved_root in visited_roots:
                continue
            visited_roots.add(resolved_root)
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.json"), key=lambda item: item.name.casefold()):
                try:
                    preset = TabularPreset_Load(path)
                except ValueError as exc:
                    LOGGER.warning("Ignoring invalid Tabular Preset %s: %s", path, exc)
                    continue
                if (
                    preset.parser_id != parser_id
                    or preset.parser_version != parser_version
                ):
                    continue
                entries.append((preset.name, str(path), builtin))
        editor.set_presets(entries, selected_path=selected_path)

    def _tabular_auto_preview(self) -> None:
        if (
            not self.import_page.uses_tabular_mapping()
            or not self.settings.tabular_auto_mapping()
        ):
            return
        config = self.import_page.tabular_mapping_editor.config()
        prefill = self.settings.tabular_auto_prefill() and not bool(
            config.get("columns")
        )
        self._tabular_preview_refresh(prefill)

    def _tabular_preview_refresh(self, force_suggestion: bool = False) -> None:
        if not self.import_page.uses_tabular_mapping():
            return
        try:
            source = self.import_page.source_path()
            plugin_id = self.import_page.selected_parser_id()
            if plugin_id is None:
                raise ValueError("Select a Generic Tabular Parser")
            plugin = self.registry.get(plugin_id)
            if not isinstance(plugin, TabularParserPlugin):
                raise TypeError(f"Parser {plugin_id!r} does not provide table previews")
            config = self.import_page.tabular_mapping_editor.config()
        except (KeyError, OSError, TypeError, ValueError) as exc:
            self._error_show(exc)
            return

        def operation(context: TaskContext) -> Any:
            context.raise_if_cancelled()
            preview = plugin.preview(source, config, maximum_rows=50)
            context.raise_if_cancelled()
            return preview

        def success(preview: Any) -> None:
            effective_config = (
                Tabular_MappingSuggest(
                    preview,
                    config,
                    self.workspace_capabilities,
                )
                if force_suggestion
                else config
            )
            self.import_page.tabular_mapping_editor.set_preview(
                preview,
                config=effective_config,
            )

        self._task_start(
            self.translations.translate("tabular.preview"),
            operation,
            success,
        )

    def _tabular_preset_select(self, path_text: str) -> None:
        try:
            preset = TabularPreset_Load(Path(path_text))
            editor = self.import_page.tabular_mapping_editor
            if (
                preset.parser_id != editor.parser_id
                or preset.parser_version != editor.parser_version
            ):
                raise ValueError(
                    "The selected preset targets a different Parser ID or version"
                )
            editor.set_config(preset.config)
            self._tabular_preview_refresh(False)
        except (OSError, ValueError) as exc:
            self._error_show(exc)

    @staticmethod
    def _tabular_preset_filename(name: str) -> str:
        safe = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in name.strip()
        ).strip("._")
        return f"{safe or 'tabular_preset'}.json"

    def _tabular_current_preset(self, name: str) -> TabularPreset:
        editor = self.import_page.tabular_mapping_editor
        return TabularPreset(
            name=name,
            parser_id=editor.parser_id,
            parser_version=editor.parser_version,
            config=editor.config(),
        )

    def _tabular_preset_save(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            self.translations.translate("tabular.preset_save"),
            self.translations.translate("tabular.preset_name"),
        )
        if not accepted or not name.strip():
            return
        try:
            preset = self._tabular_current_preset(name.strip())
            destination = (
                self._tabular_user_preset_directory()
                / self._tabular_preset_filename(name)
            )
            if destination.exists() and QMessageBox.question(
                self,
                self.translations.translate("tabular.preset_save"),
                self.translations.translate("tabular.preset_replace"),
            ) is not QMessageBox.StandardButton.Yes:
                return
            TabularPreset_Save(preset, destination)
            self._tabular_presets_refresh(str(destination))
        except (OSError, TypeError, ValueError) as exc:
            self._error_show(exc)

    def _tabular_preset_delete(self, path_text: str) -> None:
        try:
            destination = Path(path_text).resolve()
            user_root = self._tabular_user_preset_directory().resolve()
            if destination.parent != user_root or destination.suffix.casefold() != ".json":
                raise ValueError("Only user Tabular Presets can be deleted")
            if QMessageBox.question(
                self,
                self.translations.translate("tabular.preset_delete"),
                self.translations.translate("tabular.preset_delete_confirm"),
            ) is not QMessageBox.StandardButton.Yes:
                return
            destination.unlink()
            self._tabular_presets_refresh()
        except (OSError, ValueError) as exc:
            self._error_show(exc)

    def _tabular_preset_import(self) -> None:
        source_text, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self.translations.translate("tabular.preset_import"),
            self._dialog_start_directory(),
            "Tabular Preset (*.json);;All files (*)",
            options=FILE_DIALOG_OPTIONS,
        )
        if not source_text:
            return
        try:
            source = Path(source_text)
            preset = TabularPreset_Load(source)
            editor = self.import_page.tabular_mapping_editor
            if (
                preset.parser_id != editor.parser_id
                or preset.parser_version != editor.parser_version
            ):
                raise ValueError(
                    "The imported preset targets a different Parser ID or version"
                )
            destination = (
                self._tabular_user_preset_directory()
                / self._tabular_preset_filename(source.stem)
            )
            if destination.exists() and QMessageBox.question(
                self,
                self.translations.translate("tabular.preset_import"),
                self.translations.translate("tabular.preset_replace"),
            ) is not QMessageBox.StandardButton.Yes:
                return
            TabularPreset_Save(preset, destination)
            self._last_directory_store(source)
            self._tabular_presets_refresh(str(destination))
            editor.set_config(preset.config)
            self._tabular_preview_refresh(False)
        except (OSError, ValueError) as exc:
            self._error_show(exc)

    def _tabular_preset_export(self) -> None:
        editor = self.import_page.tabular_mapping_editor
        selected = editor.preset_combo.currentData()
        try:
            if isinstance(selected, dict) and selected.get("path"):
                preset = TabularPreset_Load(Path(str(selected["path"])))
            else:
                name, accepted = QInputDialog.getText(
                    self,
                    self.translations.translate("tabular.preset_export"),
                    self.translations.translate("tabular.preset_name"),
                )
                if not accepted or not name.strip():
                    return
                preset = self._tabular_current_preset(name.strip())
            destination_text, _selected_filter = QFileDialog.getSaveFileName(
                self,
                self.translations.translate("tabular.preset_export"),
                str(self.settings.last_directory() / self._tabular_preset_filename(preset.name)),
                "Tabular Preset (*.json)",
                options=FILE_DIALOG_OPTIONS,
            )
            if not destination_text:
                return
            destination = Path(destination_text)
            if destination.suffix.casefold() != ".json":
                destination = destination.with_suffix(".json")
            TabularPreset_Save(preset, destination)
            self._last_directory_store(destination)
        except (OSError, ValueError) as exc:
            self._error_show(exc)

    def _parser_detect(self) -> None:
        try:
            source = self.import_page.source_path()
        except (ValueError, OSError) as exc:
            self._error_show(exc)
            return
        parsers = self.registry.plugins(PluginType.PARSER)

        def operation(context: TaskContext) -> list[tuple[Any, ProbeResult]]:
            results: list[tuple[Any, ProbeResult]] = []
            for index, parser in enumerate(parsers):
                context.raise_if_cancelled()
                results.append((parser, parser.probe(source, ProbeContext())))
                context.report_progress((index + 1) / max(len(parsers), 1), "Probing parsers")
            return sorted(results, key=lambda item: item[1].confidence, reverse=True)

        def success(results: list[tuple[Any, ProbeResult]]) -> None:
            self._recommendations = results
            self._recommendation_source = source
            self.import_page.set_recommendations(results)
            decision = ParserSelection_Decide(
                results,
                threshold=FACTORY_DEFAULTS.parser_auto_select_threshold,
                ambiguity_margin=FACTORY_DEFAULTS.parser_auto_select_margin,
            )
            if decision.result is ParserSelectionResult.SELECTED:
                assert decision.parser is not None
                self.import_page.clear_parser_ambiguity()
                detected_id = decision.parser.descriptor.plugin_id
                unchanged = self.import_page.selected_parser_id() == detected_id
                self.import_page.set_parser_id(detected_id)
                if unchanged and isinstance(decision.parser, TabularParserPlugin):
                    QTimer.singleShot(0, self._tabular_auto_preview)
            elif decision.result is ParserSelectionResult.AMBIGUOUS:
                self.import_page.set_parser_id(None)
                self.import_page.set_parser_ambiguity(decision.candidates)
            else:
                self.import_page.clear_parser_ambiguity()
                self.import_page.set_parser_id(None)

        self._task_start(self.translations.translate("import.detect"), operation, success)

    def _source_parse(self) -> None:
        try:
            source_entries = self.import_page.source_entries()
            if not source_entries:
                raise ValueError("Select at least one source file")
            parser_config = self.import_page.parser_config()
            selected_id = self.import_page.selected_parser_id()
        except (ValueError, OSError) as exc:
            self._error_show(exc)
            return
        parsers = self.registry.plugins(PluginType.PARSER)

        def operation(context: TaskContext) -> list[tuple[Any, ...]]:
            results: list[tuple[Any, ...]] = []
            for index, (source, time_offset_s) in enumerate(source_entries):
                context.raise_if_cancelled()
                recommendations = [
                    (parser, parser.probe(source, ProbeContext())) for parser in parsers
                ]
                recommendations.sort(
                    key=lambda item: item[1].confidence, reverse=True
                )
                parser_id = selected_id
                if parser_id is None:
                    decision = ParserSelection_Decide(
                        recommendations,
                        threshold=FACTORY_DEFAULTS.parser_auto_select_threshold,
                        ambiguity_margin=FACTORY_DEFAULTS.parser_auto_select_margin,
                    )
                    if decision.result is ParserSelectionResult.AMBIGUOUS:
                        names = ", ".join(
                            item[0].descriptor.name for item in decision.candidates
                        )
                        raise ValueError(
                            f"Multiple compatible Parsers were detected for {source.name}: "
                            f"{names}. Select one before importing."
                        )
                    if decision.result is ParserSelectionResult.UNRECOGNIZED:
                        raise ValueError(
                            f"No Parser recognized {source.name}; select one manually"
                        )
                    assert decision.parser is not None
                    parser_id = decision.parser.descriptor.plugin_id
                parser = self.registry.get(parser_id)
                properties = parser.config_schema().get("properties", {})
                defaults = {
                    key: value["default"]
                    for key, value in properties.items()
                    if isinstance(value, dict) and "default" in value
                }
                effective_config = {**defaults, **parser_config}
                parse_result = parser.parse(source, effective_config, context)
                results.append(
                    (
                        source.resolve(),
                        float(time_offset_s),
                        parser_id,
                        effective_config,
                        parse_result,
                        recommendations,
                    )
                )
                context.report_progress(
                    (index + 1) / len(source_entries),
                    f"Parsed {index + 1}/{len(source_entries)} sources",
                )
            return results

        def success(payload: list[tuple[Any, ...]]) -> None:
            self.session.reset_after_parse()
            sources: dict[str, Source] = {}
            streams: dict[str, Stream] = {}
            calibrated_streams: dict[str, Any] = {}
            outputs_by_stream: dict[str, dict[str, str]] = {}
            stream_calibration_states: dict[str, ChannelCalibrationState] = {}
            identity = self.registry.get(DEFAULT_CALIBRATION_ID)
            for index, item in enumerate(payload):
                path, offset, parser_id, effective_config, result, _recommendations = item
                source_id = f"source_{index + 1}"
                stream_id = f"stream_{index + 1}"
                source_record = Source(
                    source_id,
                    path,
                    parser_id=parser_id,
                    parser_version=self.registry.get(parser_id).descriptor.version,
                    parser_config=effective_config,
                )
                stream_record = Stream(
                    stream_id,
                    source_id,
                    result.dataset,
                    offset,
                    name=path.name,
                )
                calibrated, outputs = Calibration_ApplyIdentityDefaults(
                    stream_record.dataset, identity
                )
                sources[source_id] = source_record
                streams[stream_id] = stream_record
                calibrated_streams[stream_id] = calibrated
                outputs_by_stream[stream_id] = outputs
                for channel_id, output_id in outputs.items():
                    channel = stream_record.dataset.channel(channel_id)
                    state = ChannelCalibrationState(
                        input_channel_id=channel_id,
                        output_channel_id=output_id,
                        plugin_id=DEFAULT_CALIBRATION_ID,
                        config={
                            "input_channel_id": channel_id,
                            "output_channel_id": output_id,
                            "quantity": channel.quantity,
                            "unit": channel.data_unit,
                            "parameters": {},
                            "data_quantity": channel.quantity,
                            "data_unit": channel.data_unit,
                            "display_unit": channel.effective_display_unit(),
                            "semantic_role": channel.semantic_role,
                        },
                    )
                    key = self._channel_reference_key(
                        source_id, stream_id, channel_id
                    )
                    stream_calibration_states[key] = state
            project_data = ProjectData(sources, streams)
            project_data = project_data.with_primary_channels(
                PrimaryChannels_AutoBind(project_data)
            )
            bindings = project_data.primary_channels
            primary_reference = (
                bindings.thrust
                or bindings.chamber_pressure
                or next(iter(bindings.temperature_channels), None)
            )
            primary_stream_id = (
                primary_reference.stream_id
                if primary_reference is not None
                else next(iter(streams))
            )
            primary_index = int(primary_stream_id.removeprefix("stream_")) - 1
            (
                source,
                _offset,
                parser_id,
                effective_config,
                result,
                recommendations,
            ) = payload[primary_index]
            primary_raw = project_data.streams[primary_stream_id].dataset
            primary_calibrated = calibrated_streams[primary_stream_id]
            outputs = outputs_by_stream[primary_stream_id]
            self._recommendations = recommendations
            self._recommendation_source = source
            report = Dataset_QualityInspect(primary_raw)
            self.session.source_path = source.resolve()
            self.session.parser_id = parser_id
            self.session.parser_config = dict(effective_config)
            self.session.project_data = project_data
            self.session.primary_stream_id = primary_stream_id
            self.session.active_stream_id = primary_stream_id
            self.session.calibrated_streams = calibrated_streams
            self.session.stream_channel_calibrations = stream_calibration_states
            self.session.raw_dataset = primary_raw
            self.session.quality_report = report
            self.session.calibrated_dataset = primary_calibrated
            self.session.channel_calibrations = {
                channel_id: stream_calibration_states[
                    self._channel_reference_key(
                        project_data.streams[primary_stream_id].source_id,
                        primary_stream_id,
                        channel_id,
                    )
                ]
                for channel_id in outputs
            }
            primary_channel_id = (
                primary_reference.channel_id
                if primary_reference is not None
                and primary_reference.stream_id == primary_stream_id
                else next(iter(primary_raw.channels))
            )
            primary_channel = primary_raw.channel(primary_channel_id)
            primary_state = self.session.channel_calibrations[primary_channel.id]
            self.session.calibration_id = primary_state.plugin_id
            self.session.calibration_config = dict(primary_state.config)
            for stream in streams.values():
                source_record = sources[stream.source_id]
                self.import_page.set_source_details(
                    source_record.path,
                    parser_id=(
                        f"{source_record.parser_id}@{source_record.parser_version}"
                        if source_record.parser_id and source_record.parser_version
                        else str(source_record.parser_id or "—")
                    ),
                    stream_name=str(stream.name),
                    channel_count=len(stream.dataset.channels),
                    status=self.translations.translate("import.status_parsed"),
                )
            self.import_page.set_recommendations(recommendations)
            self.import_page.set_parser_id(parser_id)
            self.import_page.set_parser_config(effective_config)
            self.import_page.set_summary(report)
            self.import_page.set_diagnostics(primary_raw.diagnostics)
            self.setup_page.set_channels(
                list(primary_raw.channels.values()), preferred_id=primary_channel.id
            )
            self.setup_page.set_calibration_config(
                primary_state.plugin_id, dict(primary_state.config)
            )
            self._primary_channels_update()
            self._measurement_workspaces_update()
            self.analyze_page.clear_result()
            self._export_availability_update()
            self.statusBar().showMessage(
                self.translations.translate(
                    "status.loaded_samples",
                    count=sum(item[4].dataset.sample_count for item in payload),
                ),
                5000,
            )

        self._task_start(self.translations.translate("status.parsing"), operation, success)

    def _calibration_apply(self) -> None:
        active_stream = self._active_stream()
        source_dataset = (
            active_stream.dataset
            if active_stream is not None
            else self.session.raw_dataset
        )
        if source_dataset is None:
            self._error_show(ValueError("Import a source file before calibration"))
            return
        active_stream_id = active_stream.id if active_stream is not None else None
        active_source_id = (
            active_stream.source_id if active_stream is not None else None
        )
        existing_states = self._active_channel_calibrations()
        try:
            plugin_id = self.setup_page.calibration_id()
            config = self.setup_page.calibration_config()
            metadata = self.setup_page.motor_metadata()
            if plugin_id is None:
                raise ValueError("Select a calibration model")
            model = self.registry.get(plugin_id)
        except (KeyError, ValueError) as exc:
            self._error_show(exc)
            return
        try:
            interpretation = self.setup_page.channel_interpretation()
            raw_dataset = source_dataset.with_channel_interpretation(
                str(interpretation["channel_id"]),
                quantity=str(interpretation["quantity"]),
                data_unit=str(interpretation["data_unit"]),
                display_unit=str(interpretation["display_unit"]),
                semantic_role=(
                    str(interpretation["semantic_role"])
                    if interpretation["semantic_role"] is not None
                    else None
                ),
            )
        except (KeyError, ValueError) as exc:
            self._error_show(exc)
            return

        def operation(
            context: TaskContext,
        ) -> tuple[Any, dict[str, ChannelCalibrationState]]:
            context.raise_if_cancelled()
            dataset = raw_dataset
            states: dict[str, ChannelCalibrationState] = {}
            for source in raw_dataset.channels.values():
                if source.role != "raw":
                    continue
                existing = existing_states.get(source.id)
                if source.id == config["input_channel_id"]:
                    active_plugin_id = plugin_id
                    active_model = model
                    active_config = dict(config)
                    selection_source = CalibrationSelectionSource.PROJECT
                elif existing is not None:
                    active_plugin_id = existing.plugin_id
                    active_model = self.registry.get(active_plugin_id)
                    active_config = dict(existing.config)
                    active_config.update(
                        {
                            "data_quantity": source.quantity,
                            "data_unit": source.data_unit,
                            "display_unit": source.effective_display_unit(),
                            "semantic_role": source.semantic_role,
                        }
                    )
                    if active_plugin_id == DEFAULT_CALIBRATION_ID:
                        active_config.update(
                            {
                                "quantity": source.quantity,
                                "unit": source.data_unit,
                            }
                        )
                    selection_source = existing.source
                else:
                    active_plugin_id = DEFAULT_CALIBRATION_ID
                    active_model = self.registry.get(active_plugin_id)
                    active_config = {
                        "input_channel_id": source.id,
                        "output_channel_id": Calibration_OutputChannelId(source),
                        "quantity": source.quantity,
                        "unit": source.data_unit,
                        "parameters": {},
                    }
                    selection_source = CalibrationSelectionSource.FACTORY_DEFAULT
                output_channel_id = str(
                    active_config.get(
                        "output_channel_id", Calibration_OutputChannelId(source)
                    )
                )
                active_config["input_channel_id"] = source.id
                active_config["output_channel_id"] = output_channel_id
                dataset = Calibration_Apply(
                    dataset,
                    active_model,
                    input_channel_id=source.id,
                    output_channel_id=output_channel_id,
                    quantity=str(active_config.get("quantity", source.quantity)),
                    unit=str(active_config.get("unit", source.data_unit)),
                    parameters=dict(active_config.get("parameters", {})),
                )
                states[source.id] = ChannelCalibrationState(
                    source.id,
                    output_channel_id,
                    active_plugin_id,
                    active_config,
                    selection_source,
                )
            context.report_progress(1.0, "Calibration complete")
            return dataset, states

        def success(payload: tuple[Any, dict[str, ChannelCalibrationState]]) -> None:
            dataset, states = payload
            self.session.reset_after_calibration()
            if active_stream_id is not None and active_source_id is not None:
                self.session.calibrated_streams[active_stream_id] = dataset
                for channel_id, state in states.items():
                    key = self._channel_reference_key(
                        active_source_id, active_stream_id, channel_id
                    )
                    self.session.stream_channel_calibrations[key] = state
                streams = dict(self.session.project_data.streams)
                previous = streams.get(active_stream_id)
                if previous is not None:
                    streams[previous.id] = Stream(
                        previous.id,
                        previous.source_id,
                        raw_dataset,
                        previous.time_offset_s,
                        previous.name,
                    )
                    self.session.project_data = ProjectData(
                        self.session.project_data.sources,
                        streams,
                        self.session.project_data.primary_channels,
                    )
            is_primary = (
                active_stream_id is None
                or active_stream_id == self.session.primary_stream_id
            )
            if is_primary:
                self.session.raw_dataset = raw_dataset
                self.session.calibration_id = plugin_id
                self.session.calibration_config = dict(config)
                self.session.channel_calibrations = states
                self.session.calibrated_dataset = dataset
            self.session.motor_metadata = metadata
            self.setup_page.set_channels(
                list(raw_dataset.channels.values()),
                preferred_id=str(config["input_channel_id"]),
            )
            self.setup_page.set_calibration_config(plugin_id, dict(config))
            self._primary_channels_update()
            self._measurement_workspaces_update()
            self.analyze_page.clear_result()
            self._export_availability_update()
            self.statusBar().showMessage(
                self.translations.translate("status.calibration_applied"), 5000
            )

        self._task_start(self.translations.translate("setup.apply_calibration"), operation, success)

    def _calibration_channel_changed(self, channel_id: str) -> None:
        state = self._active_channel_calibrations().get(channel_id)
        if state is None:
            return
        try:
            self.setup_page.set_calibration_config(state.plugin_id, dict(state.config))
        except ValueError as exc:
            LOGGER.warning("Unable to restore Channel calibration %s: %s", channel_id, exc)

    def _calibration_load_dialog(self) -> None:
        source, _filter = QFileDialog.getOpenFileName(
            self,
            self.translations.translate("dialog.select_calibration"),
            self._dialog_start_directory(),
            "Calibration JSON (*.json);;All files (*)",
            options=FILE_DIALOG_OPTIONS,
        )
        if not source:
            return
        try:
            document = Calibration_Load(Path(source))
            plugin = self.registry.get(document.model_id)
            if plugin.descriptor.version != document.model_version:
                raise ValueError("Calibration model version is not available")
            self.setup_page.set_calibration_document(document)
            self._last_directory_store(Path(source))
        except (KeyError, ValueError) as exc:
            self._error_show(exc)

    def _calibration_save_dialog(self) -> None:
        try:
            plugin_id = self.setup_page.calibration_id()
            config = self.setup_page.calibration_config()
            if plugin_id is None:
                raise ValueError("Select a calibration model")
            descriptor = self.registry.get(plugin_id).descriptor
        except (KeyError, ValueError) as exc:
            self._error_show(exc)
            return
        destination, _filter = QFileDialog.getSaveFileName(
            self,
            self.translations.translate("dialog.save_calibration"),
            self._dialog_start_directory(),
            "Calibration JSON (*.json)",
            options=FILE_DIALOG_OPTIONS,
        )
        if not destination:
            return
        path = Path(destination)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        document = CalibrationDocument(
            name=str(self.setup_page.motor_metadata().get("motor_designation", "Calibration")),
            quantity=config["quantity"],
            input_unit="raw",
            output_unit=config["unit"],
            model_id=plugin_id,
            model_version=descriptor.version,
            parameters=config["parameters"],
        )
        try:
            Calibration_Save(document, path)
            self._last_directory_store(path)
        except (OSError, ValueError) as exc:
            self._error_show(exc)

    def _burn_detect(self) -> None:
        selected_reference = Segmentation_SelectReference(self.session.project_data)
        if selected_reference is None:
            self._error_show(
                ValueError(
                    "No valid bound chamber-pressure or thrust signal was found; "
                    "select the Primary Channels or set the interval manually"
                )
            )
            return
        try:
            reference_dataset, channel_id = self._calibrated_binding_resolve(
                selected_reference.reference
            )
        except ValueError as exc:
            self._error_show(exc)
            return
        priority = selected_reference.priority
        sign = (
            1
            if priority == "chamber_pressure"
            else self.process_page.detection_sign()
        )
        channel = reference_dataset.channel(channel_id)
        task_name = self.translations.translate("process.detect_candidates")

        def operation(context: TaskContext):
            context.raise_if_cancelled()
            result = Activity_DetectSegments(
                reference_dataset.project_time, channel.values, sign=sign
            )
            context.report_progress(1.0, task_name)
            return result

        def success(candidates) -> None:
            self.session.candidates = list(candidates)
            self.session.segmentation_reference = selected_reference.reference
            self.session.segmentation_reference_priority = priority
            self.session.segmentation_manually_modified = False
            self.session.analyzer_config["segmentation_reference_channel_id"] = channel_id
            self.session.analyzer_config["segmentation_reference_priority"] = priority
            self.process_page.set_candidates(list(candidates))
            self.chamber_pressure_page.set_candidates(list(candidates))
            if candidates:
                self._segmentation_candidate_apply(0)
            else:
                self._segmentation_views_sync()

        self._task_start(task_name, operation, success)

    @staticmethod
    def _regions_normalize(
        regions: Mapping[str, Any],
    ) -> dict[str, list[float] | None]:
        active = regions.get("active_test", regions.get("burn"))
        selection = RegionSelection.from_dict(
            {
                "pre": regions.get("pre"),
                "burn": active,
                "post": regions.get("post"),
            }
        )
        payload = selection.to_dict()
        return {
            "pre": payload["pre"],
            "active_test": payload["burn"],
            "post": payload["post"],
        }

    def _segmentation_reference_name(self) -> str:
        reference = self.session.segmentation_reference
        if reference is None:
            return ""
        try:
            return self._channel_reference_label(reference)
        except KeyError:
            return reference.stable_id

    def _segmentation_views_sync(self, *, selected_index: int = 0) -> None:
        candidates = list(self.session.candidates)
        self.process_page.set_candidates(
            candidates,
            selected_index=selected_index,
        )
        self.chamber_pressure_page.set_candidates(
            candidates,
            selected_index=selected_index,
        )
        reference_name = self._segmentation_reference_name()
        manually_modified = self.session.segmentation_manually_modified
        detection_enabled = (
            Segmentation_SelectReference(self.session.project_data) is not None
        )
        self.process_page.interval_editor.set_detection_enabled(detection_enabled)
        self.chamber_pressure_page.set_detection_enabled(detection_enabled)
        self.process_page.set_segmentation_reference(
            reference_name,
            manually_modified=manually_modified,
        )
        self.chamber_pressure_page.set_segmentation_reference(
            reference_name,
            manually_modified=manually_modified,
        )
        self.process_page.set_regions(self.session.regions)
        for page in self._measurement_pages():
            page.set_regions(self.session.regions)

    def _segmentation_candidate_select(self, index: int) -> None:
        self._segmentation_candidate_apply(index)

    def _segmentation_candidate_apply(self, index: int) -> None:
        if index < 0 or index >= len(self.session.candidates):
            return
        reference = self.session.segmentation_reference
        if reference is None:
            return
        try:
            dataset, _channel_id = self._calibrated_binding_resolve(reference)
            selection = Segmentation_RegionsAroundCandidate(
                dataset,
                self.session.candidates[index],
            )
            payload = selection.to_dict()
            self._regions_store(
                {
                    "pre": payload["pre"],
                    "active_test": payload["burn"],
                    "post": payload["post"],
                },
                manually_modified=False,
                selected_index=index,
            )
        except (KeyError, ValueError) as exc:
            self._error_show(exc)

    def _regions_store(
        self,
        regions: object = None,
        *,
        manually_modified: bool = True,
        selected_index: int | None = None,
    ) -> None:
        try:
            source = (
                regions
                if isinstance(regions, Mapping)
                else self.process_page.regions()
            )
            normalized = self._regions_normalize(source)
        except (TypeError, ValueError):
            return
        changed = normalized != self.session.regions
        if selected_index is None:
            current_candidate = self.process_page.candidate_combo.currentData()
            selected_index = (
                int(current_candidate)
                if current_candidate is not None
                else 0
            )
        self.session.regions = normalized
        self.session.segmentation_manually_modified = bool(manually_modified)
        if changed:
            self.session.processing_result = None
            self.session.analyzer_id = None
            self.session.analyzer_config.clear()
            self.session.analysis_result = None
            self.session.curve_confirmed = False
            self.analyze_page.clear_result()
            self.process_page.set_processing_metadata(None)
            self._primary_channels_update()
        self._segmentation_views_sync(selected_index=selected_index)
        self._export_availability_update()

    def _processing_apply(self) -> None:
        binding = self.session.project_data.primary_channels.thrust
        if binding is None:
            self._error_show(ValueError("Select the Primary Thrust Channel before processing"))
            return
        try:
            dataset, input_channel_id = self._calibrated_binding_resolve(binding)
            config = self.process_page.processing_config()
            motor_metadata = self.setup_page.motor_metadata()
            plugin_id = self.process_page.processor_id()
            processor = self.registry.get(plugin_id) if plugin_id is not None else None
        except (KeyError, ValueError) as exc:
            self._error_show(exc)
            return

        def operation(context: TaskContext) -> ProcessingResult:
            if processor is None:
                context.raise_if_cancelled()
                result = Processing_Passthrough(
                    dataset,
                    input_channel_id=input_channel_id,
                )
                context.report_progress(1.0, "Processing pass-through complete")
                return result
            return processor.process(dataset, config, context)

        def success(result: ProcessingResult) -> None:
            self.session.reset_after_processing()
            self.session.processor_id = plugin_id
            self.session.processor_config = dict(config)
            self.session.processing_result = result
            self.session.motor_metadata = motor_metadata
            self._primary_channels_update()
            self.process_page.set_processing_metadata(result.metadata)
            self._measurement_workspaces_update()
            self.analyze_page.clear_result()
            self._export_availability_update()
            self.statusBar().showMessage(
                self.translations.translate("status.processing_applied"), 5000
            )

        self._task_start(self.translations.translate("status.processing"), operation, success)

    def _analysis_calculate(self) -> None:
        processing = self.session.processing_result
        if processing is None:
            self._error_show(ValueError("Apply processing before analysis"))
            return
        try:
            regions = self._regions_normalize(self.session.regions)
            metadata = self.setup_page.motor_metadata()
            plugin_id = THRUST_ANALYZER_ID
            analyzer = self.registry.get(plugin_id)
            config: dict[str, Any] = {
                "channel_id": "thrust_processed",
                "ignition": regions["active_test"][0],
                "burnout": regions["active_test"][1],
                "propellant_mass_kg": metadata.get("propellant_mass_kg"),
                "equivalent_mass_change_kg": processing.metadata.get(
                    "equivalent_mass_change_kg"
                ),
            }
        except (KeyError, ValueError) as exc:
            self._error_show(exc)
            return

        def operation(context: TaskContext) -> AnalysisResult:
            return analyzer.analyze(processing.dataset, config, context)

        def success(result: AnalysisResult) -> None:
            self.session.analyzer_id = plugin_id
            self.session.analyzer_config = config
            self.session.analysis_result = result
            self.session.motor_metadata = metadata
            self.session.curve_confirmed = False
            self.analyze_page.set_result(result, confirmed=False)
            self._export_availability_update()
            self.statusBar().showMessage(
                self.translations.translate("status.analysis_complete"), 5000
            )

        self._task_start(self.translations.translate("status.analyzing"), operation, success)

    def _curve_confirmation_update(self, confirmed: bool) -> None:
        self.session.curve_confirmed = confirmed

    def _plugin_reference_create(
        self, plugin_id: str | None, config: dict[str, Any]
    ) -> PluginReference | None:
        if plugin_id is None:
            return None
        descriptor = self.registry.get(plugin_id).descriptor
        return PluginReference(
            descriptor.plugin_id,
            descriptor.version,
            descriptor.api_version,
            dict(config),
        )

    def _source_parser_reference_create(self, source: Source) -> PluginReference | None:
        reference = self._plugin_reference_create(
            source.parser_id,
            dict(source.parser_config),
        )
        if reference is not None and source.parser_version:
            return replace(reference, version=source.parser_version)
        return reference

    def _project_document_create(self, source_hash: str | None = None) -> ProjectDocument:
        source_path = self.session.source_path
        if source_path is None:
            source_text = self.import_page.source_edit.text().strip()
            source_path = Path(source_text).resolve() if source_text else None

        parser_id = self.session.parser_id or self.import_page.selected_parser_id()
        parser_config = (
            self.session.parser_config
            if self.session.parser_id == parser_id and self.session.parser_config
            else self.import_page.parser_config()
        )
        selected_setup_channel = self.setup_page.selected_channel()
        calibration_id = self.session.calibration_id
        calibration_config = dict(self.session.calibration_config)
        if selected_setup_channel is not None:
            calibration_id = calibration_id or self.setup_page.calibration_id()
            if not (
                self.session.calibration_id == calibration_id
                and self.session.calibration_config
            ):
                calibration_config = self.setup_page.calibration_config()
        diagnostics = tuple(
            self.session.raw_dataset.diagnostics if self.session.raw_dataset else ()
        )
        if self.session.processing_result is not None:
            diagnostics += self.session.processing_result.diagnostics
        if self.session.analysis_result is not None:
            diagnostics += self.session.analysis_result.diagnostics

        processors: tuple[PluginReference, ...] = ()
        if self.session.processing_result is not None:
            selected_processor_id = self.session.processor_id
            selected_processor_config = dict(self.session.processor_config)
        elif self.process_page.input_channel_id is None:
            selected_processor_id = None
            selected_processor_config = {}
        else:
            selected_processor_id = self.process_page.processor_id()
            selected_processor_config = self.process_page.processing_config()
            if not self.session.regions:
                selected_processor_config.pop("regions", None)
        processor_reference = self._plugin_reference_create(
            selected_processor_id, selected_processor_config
        )
        if processor_reference is not None:
            processors = (processor_reference,)
        export_directory = self.export_dialog.directory_edit.text().strip()
        export_settings = {
            **self.session.export_settings,
            "directory": export_directory or None,
            "selected_exporter_ids": list(
                self.export_dialog.selected_exporter_ids()
            ),
            "curve_confirmed": self.session.curve_confirmed,
            "annotate_metrics": self.export_dialog.annotate_metrics(),
            "output_locale": self.export_dialog.output_locale(),
        }
        if self.session.project_data.sources:
            source_states = tuple(
                ProjectSourceState(
                    source_id=source.id,
                    path=str(source.path),
                    sha256=(
                        source_hash
                        if source_path is not None
                        and source.path == source_path
                        and source_hash is not None
                        else source.sha256
                    ),
                    parser=self._source_parser_reference_create(source),
                )
                for source in self.session.project_data.sources.values()
            )
            stream_states = tuple(
                ProjectStreamState(
                    stream_id=stream.id,
                    source_id=stream.source_id,
                    time_offset_s=stream.time_offset_s,
                    name=stream.name,
                )
                for stream in self.session.project_data.streams.values()
            )
        else:
            source_entries = self.import_page.source_entries()
            source_states = tuple(
                ProjectSourceState(
                    source_id=f"source_{index + 1}",
                    path=str(path.resolve()),
                    sha256=source_hash if index == 0 else None,
                    parser=self._plugin_reference_create(
                        parser_id, dict(parser_config)
                    ),
                )
                for index, (path, _offset) in enumerate(source_entries)
            )
            stream_states = tuple(
                ProjectStreamState(
                    stream_id=f"stream_{index + 1}",
                    source_id=f"source_{index + 1}",
                    time_offset_s=offset,
                    name=path.name,
                )
                for index, (path, offset) in enumerate(source_entries)
            )
        channel_states: dict[str, ChannelProjectState] = {}
        if self.session.project_data.streams:
            multiple_streams = len(self.session.project_data.streams) > 1
            for stream in self.session.project_data.streams.values():
                for channel in stream.dataset.channels.values():
                    if channel.role != "raw":
                        continue
                    reference_key = self._channel_reference_key(
                        stream.source_id, stream.id, channel.id
                    )
                    state = self.session.stream_channel_calibrations.get(
                        reference_key
                    )
                    if state is None and stream.id == self.session.primary_stream_id:
                        state = self.session.channel_calibrations.get(channel.id)
                    project_state = ChannelProjectState(
                        channel_id=channel.id,
                        quantity=channel.quantity,
                        data_unit=channel.data_unit,
                        unit_source=channel.unit_source.value,
                        display_unit=channel.display_unit,
                        semantic_role=channel.semantic_role,
                        calibration=(
                            self._plugin_reference_create(
                                state.plugin_id, dict(state.config)
                            )
                            if state is not None
                            else None
                        ),
                        output_channel_id=(
                            state.output_channel_id if state is not None else None
                        ),
                        source_id=stream.source_id,
                        stream_id=stream.id,
                    )
                    key = reference_key if multiple_streams else channel.id
                    channel_states[key] = project_state
        elif self.session.raw_dataset is not None:
            for channel in self.session.raw_dataset.channels.values():
                if channel.role != "raw":
                    continue
                state = self.session.channel_calibrations.get(channel.id)
                channel_states[channel.id] = ChannelProjectState(
                    channel_id=channel.id,
                    quantity=channel.quantity,
                    data_unit=channel.data_unit,
                    unit_source=channel.unit_source.value,
                    display_unit=channel.display_unit,
                    semantic_role=channel.semantic_role,
                    calibration=(
                        self._plugin_reference_create(
                            state.plugin_id, dict(state.config)
                        )
                        if state is not None
                        else None
                    ),
                    output_channel_id=(
                        state.output_channel_id if state is not None else None
                    ),
                )
        return ProjectDocument(
            source_path=str(source_path) if source_path is not None else None,
            source_hash=source_hash or self.session.source_hash,
            sources=source_states,
            streams=stream_states,
            parser=self._plugin_reference_create(parser_id, dict(parser_config)),
            calibration=self._plugin_reference_create(
                calibration_id, dict(calibration_config)
            ),
            processors=processors,
            regions=self.session.regions,
            channels=channel_states,
            primary_channels=self.session.project_data.primary_channels,
            processing_metadata=(
                dict(self.session.processing_result.metadata)
                if self.session.processing_result is not None
                else {}
            ),
            analyzer=self._plugin_reference_create(
                self.session.analyzer_id, self.session.analyzer_config
            ),
            motor_metadata=self.setup_page.motor_metadata(),
            export_settings=export_settings,
            workflow_state={
                "parsed": self.session.raw_dataset is not None,
                "calibrated": self.session.calibrated_dataset is not None,
                "processed": self.session.processing_result is not None,
                "analyzed": self.session.analysis_result is not None,
            },
            locale=self.translations.locale,
            diagnostics=diagnostics,
        )

    def _project_save_dialog(self) -> None:
        default_path = self.session.project_path
        if default_path is None:
            default_path = self.settings.last_directory() / "Untitled_Project.retldc.json"
        destination, _filter = QFileDialog.getSaveFileName(
            self,
            self.translations.translate("dialog.save_project"),
            str(default_path),
            "Underline Project (*.retldc.json);;JSON (*.json)",
            options=FILE_DIALOG_OPTIONS,
        )
        if not destination:
            return
        path = Path(destination)
        if not path.name.lower().endswith(".retldc.json"):
            path = path.with_name(f"{path.stem}.retldc.json")
        was_untitled = self.session.project_path is None
        try:
            document_template = self._project_document_create()
            if was_untitled or not document_template.export_settings.get("directory"):
                export_settings = dict(document_template.export_settings)
                export_settings["directory"] = str(Project_DefaultExportDirectory(path))
                document_template = replace(
                    document_template, export_settings=export_settings
                )
        except (KeyError, ValueError) as exc:
            self._error_show(exc)
            return

        def operation(context: TaskContext) -> ProjectDocument:
            context.raise_if_cancelled()
            source_hash = document_template.source_hash
            source_states: list[ProjectSourceState] = []
            for index, source_state in enumerate(document_template.sources):
                configured_source = Path(source_state.path)
                actual_hash = source_state.sha256
                if configured_source.is_file():
                    actual_hash = Project_SourceHash(configured_source)
                source_states.append(replace(source_state, sha256=actual_hash))
                context.report_progress(
                    0.7 * (index + 1) / max(len(document_template.sources), 1),
                    "Source hashes calculated",
                )
            if source_states:
                primary_state = next(
                    (
                        item
                        for item in source_states
                        if document_template.source_path is not None
                        and Path(item.path) == Path(document_template.source_path)
                    ),
                    source_states[0],
                )
                source_hash = primary_state.sha256
            elif document_template.source_path:
                configured_source = Path(document_template.source_path)
                if configured_source.is_file():
                    source_hash = Project_SourceHash(configured_source)
            document = replace(
                document_template,
                source_hash=source_hash,
                sources=tuple(source_states),
            )
            Project_Save(document, path)
            context.report_progress(1.0, "Project saved")
            return document

        def success(document: ProjectDocument) -> None:
            self.session.project_path = path.resolve()
            self.session.source_hash = document.source_hash
            self.session.export_settings = dict(document.export_settings)
            self._project_title = path.name
            export_directory = document.export_settings.get("directory")
            if export_directory:
                self.export_dialog.set_output_directory(Path(export_directory))
            self._last_directory_store(path)
            self._retranslate()
            self.statusBar().showMessage(
                self.translations.translate("status.project_saved"), 5000
            )

        self._task_start(self.translations.translate("export.save_project"), operation, success)

    def _project_open_dialog(self) -> None:
        source, _filter = QFileDialog.getOpenFileName(
            self,
            self.translations.translate("dialog.open_project"),
            self._dialog_start_directory(),
            "Underline Project (*.json);;All files (*)",
            options=FILE_DIALOG_OPTIONS,
        )
        if not source:
            return
        project_path = Path(source).resolve()
        try:
            document = Project_Load(project_path)
            raw_source: Path | None = None
            if document.source_path is not None:
                raw_source = Path(document.source_path)
                if not raw_source.is_absolute():
                    raw_source = project_path.parent / raw_source
            if raw_source is not None and not raw_source.is_file():
                relocated, _filter = QFileDialog.getOpenFileName(
                    self,
                    self.translations.translate("dialog.relocate_source"),
                    str(project_path.parent),
                    "Test logs (*.txt *.csv *.log);;All files (*)",
                    options=FILE_DIALOG_OPTIONS,
                )
                if not relocated:
                    return
                raw_source = Path(relocated).resolve()
        except (OSError, ValueError) as exc:
            self._error_show(exc)
            return

        def operation(context: TaskContext):
            return self._project_recompute(document, context, raw_source=raw_source)

        def success(payload) -> None:
            document, raw_source, parse_result, calibrated, processing_result, analysis = payload
            project_data = self._recomputed_project_data
            bindings = project_data.primary_channels
            primary_reference = (
                bindings.thrust
                or bindings.chamber_pressure
                or next(iter(bindings.temperature_channels), None)
            )
            primary_stream_id = (
                primary_reference.stream_id
                if primary_reference is not None
                else next(
                    (
                        stream.id
                        for stream in project_data.streams.values()
                        if raw_source is not None
                        and project_data.sources[stream.source_id].path.resolve()
                        == raw_source.resolve()
                    ),
                    next(iter(project_data.streams), None),
                )
            )
            calibrated_streams = dict(self._recomputed_calibrated_streams)
            if primary_stream_id is not None and calibrated is not None:
                calibrated_streams[primary_stream_id] = calibrated
            self.session = AnalysisSession(
                project_path=project_path,
                source_path=raw_source.resolve() if raw_source is not None else None,
                source_hash=document.source_hash,
                parser_id=document.parser.id if document.parser else None,
                parser_config=dict(document.parser.config) if document.parser else {},
                raw_dataset=(
                    project_data.streams[primary_stream_id].dataset
                    if primary_stream_id is not None
                    else (parse_result.dataset if parse_result else None)
                ),
                project_data=project_data,
                primary_stream_id=primary_stream_id,
                active_stream_id=primary_stream_id,
                calibrated_streams=calibrated_streams,
                quality_report=(
                    Dataset_QualityInspect(parse_result.dataset) if parse_result else None
                ),
                calibration_id=document.calibration.id if document.calibration else None,
                calibration_config=(
                    dict(document.calibration.config) if document.calibration else {}
                ),
                calibrated_dataset=(
                    calibrated_streams.get(primary_stream_id)
                    if primary_stream_id is not None
                    else calibrated
                ),
                processor_id=document.processors[0].id if document.processors else None,
                processor_config=(
                    dict(document.processors[0].config) if document.processors else {}
                ),
                processing_result=processing_result,
                regions={
                    key: list(value) if value is not None else None
                    for key, value in document.regions.items()
                },
                analyzer_id=document.analyzer.id if document.analyzer else None,
                analyzer_config=(
                    dict(document.analyzer.config) if document.analyzer else {}
                ),
                analysis_result=analysis,
                motor_metadata=dict(document.motor_metadata),
                export_settings=dict(document.export_settings),
                curve_confirmed=bool(document.export_settings.get("curve_confirmed", False)),
            )
            if document.regions:
                selected_segmentation = Segmentation_SelectReference(project_data)
                if selected_segmentation is not None:
                    self.session.segmentation_reference = (
                        selected_segmentation.reference
                    )
                    self.session.segmentation_reference_priority = (
                        selected_segmentation.priority
                    )
                self.session.segmentation_manually_modified = True
            primary_source_id = (
                project_data.streams[primary_stream_id].source_id
                if primary_stream_id is not None
                else None
            )
            (
                self.session.stream_channel_calibrations,
                self.session.channel_calibrations,
            ) = self._project_calibration_states_restore(
                document, project_data, primary_stream_id
            )
            self._recommendations.clear()
            self._recommendation_source = None
            self.import_page.clear_results()
            if project_data.streams:
                self.import_page.set_source_entries(
                    [
                        (
                            project_data.sources[stream.source_id].path,
                            stream.time_offset_s,
                        )
                        for stream in project_data.streams.values()
                    ]
                )
                for stream in project_data.streams.values():
                    source_record = project_data.sources[stream.source_id]
                    self.import_page.set_source_details(
                        source_record.path,
                        parser_id=(
                            f"{source_record.parser_id}@{source_record.parser_version}"
                            if source_record.parser_id and source_record.parser_version
                            else str(source_record.parser_id or "—")
                        ),
                        stream_name=str(stream.name),
                        channel_count=len(stream.dataset.channels),
                        status=self.translations.translate("import.status_parsed"),
                    )
            elif raw_source is not None:
                self.import_page.set_source_path(raw_source)
            else:
                self.import_page.source_edit.clear()
            if document.parser is not None:
                self.import_page.set_parser_id(document.parser.id)
                self.import_page.set_parser_config(dict(document.parser.config))
            if self.session.quality_report is not None and parse_result is not None:
                self.import_page.set_summary(self.session.quality_report)
                self.import_page.set_diagnostics(parse_result.dataset.diagnostics)
            if document.calibration is not None:
                self.setup_page.set_calibration_config(
                    document.calibration.id, dict(document.calibration.config)
                )
            if parse_result is not None:
                selected_channel_id = next(
                    (
                        state.channel_id
                        for state in document.channels.values()
                        if state.stream_id in (None, primary_stream_id)
                        and state.source_id in (None, primary_source_id)
                        if state.semantic_role == "thrust"
                    ),
                    next(iter(parse_result.dataset.channels), None),
                )
                self.setup_page.set_channels(
                    list(parse_result.dataset.channels.values()),
                    preferred_id=selected_channel_id,
                )
                if selected_channel_id is not None:
                    channel_state = self.session.channel_calibrations.get(
                        selected_channel_id
                    )
                    if channel_state is not None:
                        self.setup_page.set_calibration_config(
                            channel_state.plugin_id, dict(channel_state.config)
                        )
            self.setup_page.set_motor_metadata(dict(document.motor_metadata))
            self.process_page.clear_state()
            self._primary_channels_update()
            self.process_page.set_processing_metadata(document.processing_metadata)
            processor_id = document.processors[0].id if document.processors else None
            processor_config = (
                dict(document.processors[0].config) if document.processors else {}
            )
            self.process_page.set_processing_config(processor_id, processor_config)
            if document.regions:
                self.process_page.set_regions(
                    {
                        key: list(value) if value is not None else None
                        for key, value in document.regions.items()
                    }
                )
            if analysis is not None:
                self.analyze_page.set_result(
                    analysis, confirmed=self.session.curve_confirmed
                )
            else:
                self.analyze_page.clear_result()
            self._measurement_workspaces_update()
            self._segmentation_views_sync()
            self._primary_channels_update()
            self._export_availability_update()
            self.export_dialog.set_motor_metadata(dict(document.motor_metadata))
            selected_exporters = document.export_settings.get("selected_exporter_ids")
            if isinstance(selected_exporters, list):
                self.export_dialog.set_selected_exporter_ids(selected_exporters)
            export_directory = document.export_settings.get("directory")
            self.export_dialog.set_output_directory(
                Path(export_directory)
                if export_directory
                else Project_DefaultExportDirectory(project_path)
            )
            self.export_dialog.annotate_metrics_check.setChecked(
                bool(document.export_settings.get("annotate_metrics", True))
            )
            self.export_dialog.set_output_locale(
                str(document.export_settings.get("output_locale", document.locale))
            )
            self._locale_select(document.locale)
            self._last_directory_store(project_path)
            self._project_title = project_path.name
            self._retranslate()
            self._workspace_select("project")
            self.statusBar().showMessage(
                self.translations.translate("status.project_loaded"), 5000
            )

        self._task_start(self.translations.translate("export.open_project"), operation, success)

    def _project_calibrations_apply(
        self,
        dataset: Any,
        channel_states: tuple[ChannelProjectState, ...],
        *,
        legacy_reference: PluginReference | None = None,
    ) -> Any:
        """Restore every raw Channel's independent calibration without using its Unit."""
        states_by_channel = {state.channel_id: state for state in channel_states}
        identity = self.registry.get(DEFAULT_CALIBRATION_ID)
        legacy_config = (
            dict(legacy_reference.config) if legacy_reference is not None else {}
        )
        legacy_input_channel_id = str(legacy_config.get("input_channel_id", ""))
        legacy_applied = legacy_reference is None
        calibrated = dataset
        for source in tuple(dataset.channels.values()):
            if source.role != "raw":
                continue
            state = states_by_channel.get(source.id)
            reference = state.calibration if state is not None else None
            if (
                reference is None
                and state is None
                and legacy_reference is not None
                and source.id == legacy_input_channel_id
            ):
                reference = legacy_reference
                legacy_applied = True
            if reference is None:
                model = identity
                config: dict[str, Any] = {}
            else:
                model = self._plugin_reference_resolve(reference)
                config = dict(reference.config)
            is_identity = model.descriptor.plugin_id == DEFAULT_CALIBRATION_ID
            output_channel_id = str(
                (
                    state.output_channel_id
                    if state is not None and state.output_channel_id
                    else config.get("output_channel_id")
                )
                or Calibration_OutputChannelId(source)
            )
            calibrated = Calibration_Apply(
                calibrated,
                model,
                input_channel_id=source.id,
                output_channel_id=output_channel_id,
                quantity=(
                    source.quantity
                    if is_identity
                    else str(config.get("quantity", source.quantity))
                ),
                unit=(
                    source.data_unit
                    if is_identity
                    else str(config.get("unit", source.data_unit))
                ),
                parameters=dict(config.get("parameters", {})),
            )
        if not legacy_applied:
            raise ValueError(
                "Project calibration input Channel "
                f"{legacy_input_channel_id!r} is missing from parsed source"
            )
        return calibrated

    def _project_calibration_states_restore(
        self,
        document: ProjectDocument,
        project_data: ProjectData,
        primary_stream_id: str | None,
    ) -> tuple[
        dict[str, ChannelCalibrationState],
        dict[str, ChannelCalibrationState],
    ]:
        """Restore explicit per-Channel selections, including legacy and Identity defaults."""
        stream_states: dict[str, ChannelCalibrationState] = {}
        primary_states: dict[str, ChannelCalibrationState] = {}
        legacy_config = (
            dict(document.calibration.config)
            if document.calibration is not None
            else {}
        )
        legacy_input_channel_id = str(legacy_config.get("input_channel_id", ""))
        for stream in project_data.streams.values():
            is_primary = stream.id == primary_stream_id
            channel_states = self._project_channel_states_for_stream(
                document,
                stream.source_id,
                stream.id,
                include_legacy=is_primary,
            )
            states_by_channel = {state.channel_id: state for state in channel_states}
            for source in stream.dataset.channels.values():
                if source.role != "raw":
                    continue
                project_state = states_by_channel.get(source.id)
                reference = (
                    project_state.calibration if project_state is not None else None
                )
                if (
                    reference is None
                    and project_state is None
                    and is_primary
                    and document.calibration is not None
                    and source.id == legacy_input_channel_id
                ):
                    reference = document.calibration
                if reference is None:
                    plugin_id = DEFAULT_CALIBRATION_ID
                    config: dict[str, Any] = {}
                    selection_source = CalibrationSelectionSource.FACTORY_DEFAULT
                else:
                    plugin_id = reference.id
                    config = dict(reference.config)
                    selection_source = CalibrationSelectionSource.PROJECT
                output_channel_id = str(
                    (
                        project_state.output_channel_id
                        if project_state is not None
                        and project_state.output_channel_id
                        else config.get("output_channel_id")
                    )
                    or Calibration_OutputChannelId(source)
                )
                config.update(
                    {
                        "input_channel_id": source.id,
                        "output_channel_id": output_channel_id,
                        "data_quantity": source.quantity,
                        "data_unit": source.data_unit,
                        "display_unit": source.effective_display_unit(),
                        "semantic_role": source.semantic_role,
                    }
                )
                if plugin_id == DEFAULT_CALIBRATION_ID:
                    config.update(
                        {
                            "quantity": source.quantity,
                            "unit": source.data_unit,
                            "parameters": {},
                        }
                    )
                else:
                    config.setdefault("quantity", source.quantity)
                    config.setdefault("unit", source.data_unit)
                    config.setdefault("parameters", {})
                calibration_state = ChannelCalibrationState(
                    source.id,
                    output_channel_id,
                    plugin_id,
                    config,
                    selection_source,
                )
                key = self._channel_reference_key(
                    stream.source_id, stream.id, source.id
                )
                stream_states[key] = calibration_state
                if is_primary:
                    primary_states[source.id] = calibration_state
        return stream_states, primary_states

    def _project_recompute(
        self,
        document: ProjectDocument,
        context: TaskContext,
        *,
        raw_source: Path | None = None,
    ):
        self._project_references_validate(document)
        self._recomputed_project_data = ProjectData()
        self._recomputed_calibrated_streams = {}
        source_validated = False
        if raw_source is None:
            resolution = Project_SourceResolve(document)
            if resolution.result is ProjectSourceResolveResult.NOT_CONFIGURED:
                return document, None, None, None, None, None
            if resolution.result is ProjectSourceResolveResult.MISSING:
                raise FileNotFoundError(f"Project source is missing: {resolution.path}")
            if resolution.result is ProjectSourceResolveResult.HASH_MISMATCH:
                raise ProjectSourceHashMismatchError(
                    document.source_hash or "N/A", resolution.actual_hash or "N/A"
                )
            raw_source = resolution.path
            source_validated = document.source_hash is not None
        if raw_source is None:
            return document, None, None, None, None, None
        if document.source_hash and not source_validated:
            actual_hash = Project_SourceHash(raw_source)
            if actual_hash != document.source_hash:
                raise ProjectSourceHashMismatchError(document.source_hash, actual_hash)
        if document.parser is None:
            return document, raw_source, None, None, None, None
        workflow_state = dict(document.workflow_state)
        if not workflow_state:
            workflow_state = {
                "parsed": document.parser is not None,
                "calibrated": document.calibration is not None,
                "processed": bool(document.processors),
                "analyzed": document.analyzer is not None,
            }
        if not workflow_state.get("parsed", False):
            return document, raw_source, None, None, None, None
        parser = self._plugin_reference_resolve(document.parser)
        parse_result = parser.parse(raw_source, document.parser.config, context)
        primary_source_id = "source_1"
        primary_stream_id = "stream_1"
        if document.sources and document.streams:
            primary_source_state = next(
                (
                    item
                    for item in document.sources
                    if Path(item.path) == Path(document.source_path or raw_source)
                ),
                document.sources[0],
            )
            primary_stream_state = next(
                (
                    item
                    for item in document.streams
                    if item.source_id == primary_source_state.source_id
                ),
                None,
            )
            if primary_stream_state is not None:
                primary_source_id = primary_source_state.source_id
                primary_stream_id = primary_stream_state.stream_id
                primary_stream = Stream(
                    primary_stream_state.stream_id,
                    primary_source_state.source_id,
                    parse_result.dataset,
                    primary_stream_state.time_offset_s,
                    primary_stream_state.name,
                )
                parse_result = ParseResult(
                    primary_stream.dataset, primary_stream.dataset.diagnostics
                )
        primary_channel_states = self._project_channel_states_for_stream(
            document,
            primary_source_id,
            primary_stream_id,
            include_legacy=True,
        )
        if primary_channel_states:
            raw_dataset = parse_result.dataset
            for channel_state in primary_channel_states:
                channel_id = channel_state.channel_id
                if channel_id not in raw_dataset.channels:
                    raise ValueError(
                        f"Project Channel {channel_id!r} is missing from parsed source"
                    )
                raw_dataset = raw_dataset.with_channel_interpretation(
                    channel_id,
                    quantity=channel_state.quantity,
                    data_unit=channel_state.data_unit,
                    display_unit=channel_state.display_unit,
                    semantic_role=channel_state.semantic_role,
                    unit_source=channel_state.unit_source,
                )
            parse_result = ParseResult(raw_dataset, raw_dataset.diagnostics)
        self._project_streams_recompute(
            document,
            context,
            primary_source=raw_source,
            primary_dataset=parse_result.dataset,
            apply_identity=workflow_state.get("calibrated", False),
        )
        if not workflow_state.get("calibrated", False):
            return document, raw_source, parse_result, None, None, None
        thrust_reference = self._recomputed_project_data.primary_channels.thrust
        if thrust_reference is not None:
            calibrated = self._recomputed_calibrated_streams[
                thrust_reference.stream_id
            ]
            input_candidates = tuple(
                channel.id
                for channel in calibrated.channels.values()
                if channel.role == "calibrated"
                and channel.metadata.get("source_channel_id")
                == thrust_reference.channel_id
            )
            if len(input_candidates) != 1:
                raise ValueError(
                    "Primary Thrust Calibration output could not be resolved from "
                    f"{thrust_reference.stable_id}"
                )
            thrust_input_channel_id = input_candidates[0]
        else:
            calibrated = self._project_calibrations_apply(
                parse_result.dataset,
                primary_channel_states,
                legacy_reference=(
                    document.calibration if not primary_channel_states else None
                ),
            )
            thrust_input_channel_id = None
        processor = None
        processor_reference = None
        if document.processors:
            processor_reference = document.processors[0]
            processor = self._plugin_reference_resolve(processor_reference)
        processing_result = None
        if workflow_state.get("processed", False):
            if thrust_input_channel_id is None:
                raise ValueError(
                    "Processed Project has no Primary Thrust Channel binding"
                )
            if processor is None or processor_reference is None:
                processing_result = Processing_Passthrough(
                    calibrated,
                    input_channel_id=thrust_input_channel_id,
                )
            else:
                processor_config = dict(processor_reference.config)
                schema_properties = processor.config_schema().get("properties", {})
                if isinstance(schema_properties, Mapping):
                    normalized_regions = self._regions_normalize(document.regions)
                    injected = {
                        "thrust_analysis.input_channel": thrust_input_channel_id,
                        "thrust_analysis.regions": {
                            "pre": normalized_regions.get("pre"),
                            "burn": normalized_regions.get("active_test"),
                            "post": normalized_regions.get("post"),
                        },
                    }
                    for field_name, field_schema in schema_properties.items():
                        if not isinstance(field_schema, Mapping):
                            continue
                        source = field_schema.get("x-ui-source")
                        if source in injected:
                            processor_config[str(field_name)] = injected[str(source)]
                processing_result = processor.process(
                    calibrated, processor_config, context
                )
        if (
            processing_result is None
            or document.analyzer is None
            or not workflow_state.get("analyzed", False)
        ):
            return document, raw_source, parse_result, calibrated, processing_result, None
        analyzer = self._plugin_reference_resolve(document.analyzer)
        analysis = analyzer.analyze(
            processing_result.dataset, document.analyzer.config, context
        )
        return (
            document,
            raw_source,
            parse_result,
            calibrated,
            processing_result,
            analysis,
        )

    def _project_references_validate(self, document: ProjectDocument) -> None:
        references = [
            document.parser,
            document.calibration,
            *(source.parser for source in document.sources),
            *document.processors,
            document.analyzer,
            *(
                state.calibration
                for state in document.channels.values()
                if state.calibration is not None
            ),
        ]
        for reference in references:
            if reference is not None:
                self._plugin_reference_resolve(reference)

    def _project_streams_recompute(
        self,
        document: ProjectDocument,
        context: TaskContext,
        *,
        primary_source: Path,
        primary_dataset: Any,
        apply_identity: bool,
    ) -> None:
        source_states = document.sources or (
            ProjectSourceState(
                "source_1",
                str(primary_source),
                document.source_hash,
                document.parser,
            ),
        )
        stream_states = document.streams or tuple(
            ProjectStreamState(
                f"stream_{index + 1}",
                source.source_id,
                0.0,
                Path(source.path).name,
            )
            for index, source in enumerate(source_states)
        )
        sources: dict[str, Source] = {}
        streams: dict[str, Stream] = {}
        calibrated_streams: dict[str, Any] = {}
        primary_resolved = primary_source.resolve()
        for index, source_state in enumerate(source_states):
            configured_path = Path(source_state.path)
            is_primary = (
                configured_path.resolve() == primary_resolved
                or (
                    document.source_path is not None
                    and Path(document.source_path) == configured_path
                    and index == 0
                )
            )
            actual_path = primary_resolved if is_primary else configured_path.resolve()
            if not actual_path.is_file():
                raise FileNotFoundError(f"Project Source is missing: {actual_path}")
            if source_state.sha256 is not None:
                actual_hash = Project_SourceHash(actual_path)
                if actual_hash != source_state.sha256:
                    raise ProjectSourceHashMismatchError(
                        source_state.sha256, actual_hash
                    )
            parser_reference = source_state.parser or document.parser
            if parser_reference is None:
                raise ValueError(
                    f"Project Source {source_state.source_id!r} has no Parser"
                )
            if is_primary:
                dataset = primary_dataset
            else:
                parser = self._plugin_reference_resolve(parser_reference)
                dataset = parser.parse(
                    actual_path, parser_reference.config, context
                ).dataset
            source_record = Source(
                source_state.source_id,
                actual_path,
                sha256=source_state.sha256,
                parser_id=parser_reference.id,
                parser_version=parser_reference.version,
                parser_config=parser_reference.config,
            )
            sources[source_record.id] = source_record
            related_streams = tuple(
                item for item in stream_states if item.source_id == source_record.id
            )
            if not related_streams:
                related_streams = (
                    ProjectStreamState(
                        f"stream_{index + 1}",
                        source_record.id,
                        0.0,
                        actual_path.name,
                    ),
                )
            for stream_state in related_streams:
                channel_states = self._project_channel_states_for_stream(
                    document,
                    source_record.id,
                    stream_state.stream_id,
                    include_legacy=is_primary,
                )
                interpreted_dataset = dataset
                for channel_state in channel_states:
                    if channel_state.channel_id not in interpreted_dataset.channels:
                        raise ValueError(
                            "Project Channel "
                            f"{channel_state.persistent_key!r} is missing from parsed source"
                        )
                    interpreted_dataset = interpreted_dataset.with_channel_interpretation(
                        channel_state.channel_id,
                        quantity=channel_state.quantity,
                        data_unit=channel_state.data_unit,
                        display_unit=channel_state.display_unit,
                        semantic_role=channel_state.semantic_role,
                        unit_source=channel_state.unit_source,
                    )
                stream = Stream(
                    stream_state.stream_id,
                    source_record.id,
                    interpreted_dataset,
                    stream_state.time_offset_s,
                    stream_state.name,
                )
                streams[stream.id] = stream
                if apply_identity:
                    calibrated_streams[stream.id] = self._project_calibrations_apply(
                        stream.dataset,
                        channel_states,
                        legacy_reference=(
                            document.calibration
                            if is_primary and not channel_states
                            else None
                        ),
                    )
        project_data = ProjectData(sources, streams)
        bindings = (
            document.primary_channels
            if document.primary_channels_explicit
            else PrimaryChannels_AutoBind(project_data)
        )
        PrimaryChannels_Validate(project_data, bindings)
        self._recomputed_project_data = project_data.with_primary_channels(bindings)
        self._recomputed_calibrated_streams = calibrated_streams

    def _plugin_reference_resolve(self, reference: PluginReference):
        try:
            plugin = self.registry.get(reference.id)
        except KeyError as exc:
            raise ValueError(
                self.translations.translate(
                    "project.plugin_missing",
                    plugin_id=reference.id,
                    version=reference.version,
                )
            ) from exc
        descriptor = plugin.descriptor
        if descriptor.api_version != reference.api_version:
            raise ValueError(
                f"Plugin API mismatch for {reference.id}: project {reference.api_version}, "
                f"installed {descriptor.api_version}"
            )
        if descriptor.version != reference.version:
            raise ValueError(
                f"Plugin version mismatch for {reference.id}: project {reference.version}, "
                f"installed {descriptor.version}"
            )
        return plugin

    def _export_dialog_show(self) -> None:
        self._export_availability_update()
        directory_text = self.export_dialog.directory_edit.text().strip()
        if not directory_text:
            self.export_dialog.set_output_directory(
                Project_DefaultExportDirectory(
                    self.session.project_path,
                    source_path=self.session.source_path,
                    fallback_directory=self.settings.last_directory(),
                )
            )
        self.export_dialog.set_motor_metadata(self.setup_page.motor_metadata())
        self.export_dialog.show()
        self.export_dialog.raise_()

    def _export_input_resolve(
        self,
        plugin_id: str,
    ) -> tuple[Any, AnalysisResult | None]:
        group_id = self.export_dialog.export_group_id(plugin_id)
        bindings = self.session.project_data.primary_channels
        if group_id == "chamber_pressure":
            if bindings.chamber_pressure is None:
                raise ValueError("Select the Primary Chamber Pressure Channel")
            dataset, _channel_id = self._calibrated_binding_resolve(
                bindings.chamber_pressure
            )
            return dataset, None
        if group_id == "temperature":
            if not bindings.temperature_channels:
                raise ValueError("Select at least one Primary Temperature Channel")
            dataset, _channel_id = self._calibrated_binding_resolve(
                bindings.temperature_channels[0]
            )
            return dataset, None
        dataset = self.session.processed_dataset
        analysis = self.session.analysis_result
        if dataset is None or analysis is None:
            raise ValueError(
                self.translations.translate("export.complete_thrust_analysis")
            )
        return dataset, analysis

    def _export_execute(self) -> None:
        try:
            destination = self.export_dialog.output_directory()
            selected = self.export_dialog.selected_exporter_ids()
            if not selected:
                raise ValueError("Select at least one export format")
            missing_requirements = {
                analysis_id
                for plugin_id in selected
                for analysis_id in self.export_dialog.missing_analysis_ids(plugin_id)
            }
            if missing_requirements:
                raise ValueError(
                    self.translations.translate("export.complete_thrust_analysis")
                )
            export_inputs = {
                plugin_id: self._export_input_resolve(plugin_id)
                for plugin_id in selected
            }
            motor_metadata = self.export_dialog.motor_metadata()
            active = self.session.regions.get(
                "active_test",
                self.session.regions.get("burn"),
            )
            ignition = float(active[0]) if active is not None else None
            burnout = float(active[1]) if active is not None else None
        except (KeyError, ValueError) as exc:
            self._error_show(exc)
            return

        output_locale = self.export_dialog.output_locale()
        filenames = {
            plugin_id: self.export_dialog.export_filename(plugin_id)
            for plugin_id in selected
        }

        def provenance_item(
            plugin_id: str | None, config: dict[str, Any]
        ) -> dict[str, Any] | None:
            if plugin_id is None:
                return None
            descriptor = self.registry.get(plugin_id).descriptor
            return {
                "id": descriptor.plugin_id,
                "version": descriptor.version,
                "api_version": descriptor.api_version,
                "config": dict(config),
            }

        common_config = {
            "channel_id": "thrust_processed",
            "ignition": ignition,
            "burnout": burnout,
            "motor_metadata": motor_metadata,
            "source_hash": self.session.source_hash,
            "processing_metadata": (
                dict(self.session.processing_result.metadata)
                if self.session.processing_result is not None
                else {}
            ),
            "project_name": (
                self.session.project_path.name
                if self.session.project_path is not None
                else None
            ),
            "provenance": {
                "parser": provenance_item(
                    self.session.parser_id, self.session.parser_config
                ),
                "calibration": provenance_item(
                    self.session.calibration_id, self.session.calibration_config
                ),
                "processor": provenance_item(
                    self.session.processor_id, self.session.processor_config
                ),
                "analyzer": provenance_item(
                    self.session.analyzer_id, self.session.analyzer_config
                ),
                "regions": self.session.regions,
            },
            "curve_confirmed": self.session.curve_confirmed,
            "annotate_metrics": self.export_dialog.annotate_metrics(),
            "output_locale": output_locale,
        }
        try:
            configs: dict[str, dict[str, Any]] = {}
            for plugin_id in selected:
                exporter = self.registry.get(plugin_id)
                properties = exporter.config_schema().get("properties", {})
                if not isinstance(properties, Mapping):
                    raise ValueError(
                        f"Exporter {plugin_id!r} schema properties must be an object"
                    )
                defaults = {
                    str(key): value["default"]
                    for key, value in properties.items()
                    if isinstance(value, Mapping) and "default" in value
                }
                configs[plugin_id] = {
                    **defaults,
                    **common_config,
                    **motor_metadata,
                }
        except (KeyError, TypeError, ValueError) as exc:
            self._error_show(exc)
            return
        try:
            validation_errors = []
            for plugin_id in selected:
                exporter = self.registry.get(plugin_id)
                dataset, analysis = export_inputs[plugin_id]
                validation_errors.extend(
                    self.translations.translate(
                        f"diagnostic.{diagnostic.code}",
                        diagnostic.message,
                        message=diagnostic.message,
                    )
                    for diagnostic in exporter.validate(
                        dataset,
                        analysis,
                        configs.get(plugin_id, common_config),
                    )
                    if diagnostic.severity.value == "ERROR"
                )
            if validation_errors:
                raise ValueError("\n".join(validation_errors))
        except (KeyError, ValueError) as exc:
            self._error_show(exc)
            return

        def operation(context: TaskContext):
            results = []
            for index, plugin_id in enumerate(selected):
                context.raise_if_cancelled()
                exporter = self.registry.get(plugin_id)
                dataset, analysis = export_inputs[plugin_id]
                result = exporter.export(
                    destination / filenames[plugin_id],
                    dataset,
                    analysis,
                    configs.get(plugin_id, common_config),
                    context,
                )
                results.append(result)
                context.report_progress(
                    (index + 1) / len(selected), f"Exported {filenames[plugin_id]}"
                )
            return results

        def success(_results) -> None:
            self.session.export_settings = {
                "directory": str(destination),
                "selected_exporter_ids": list(selected),
                "curve_confirmed": self.session.curve_confirmed,
                "annotate_metrics": self.export_dialog.annotate_metrics(),
                "output_locale": output_locale,
            }
            self._last_directory_store(destination)
            self.export_dialog.accept()
            QMessageBox.information(
                self,
                self.translations.translate("common.success"),
                self.translations.translate(
                    "export.completed", count=len(selected), directory=str(destination)
                ),
            )

        self._task_start(
            self.translations.translate("status.exporting"),
            operation,
            success,
        )

    def _plugins_refresh(self) -> None:
        selected_parser = self.import_page.selected_parser_id()
        selected_calibration = self.setup_page.calibration_id()
        selected_processor = self.process_page.processor_id()
        self.registry = PluginRegistry()
        self.plugin_loader = PluginLoader(self.registry)
        self.plugin_loader.discover(
            (
                PluginDiscoveryRoot(
                    self.development_plugin_directory, "bundled"
                ),
                PluginDiscoveryRoot(self.user_plugin_directory, "user"),
            )
        )
        for record in self.registry.records:
            if record.result is PluginLoadResult.LOADED:
                translation_directory = Path(record.source) / "i18n"
                if translation_directory.is_dir():
                    self.translations.load_plugin_directory(translation_directory)
        parsers = self.registry.plugins(PluginType.PARSER)
        parser_ids = {item.descriptor.plugin_id for item in parsers}
        if not self._plugins_initialized:
            selected_parser = None
        elif selected_parser is not None and selected_parser not in parser_ids:
            selected_parser = (
                DEFAULT_PARSER_ID
                if DEFAULT_PARSER_ID in parser_ids
                else (parsers[0].descriptor.plugin_id if parsers else None)
            )
        self.import_page.set_parsers(parsers, preferred_id=selected_parser)
        calibrations = self.registry.plugins(PluginType.CALIBRATION)
        calibration_ids = {item.descriptor.plugin_id for item in calibrations}
        if selected_calibration not in calibration_ids:
            selected_calibration = (
                DEFAULT_CALIBRATION_ID
                if DEFAULT_CALIBRATION_ID in calibration_ids
                else (calibrations[0].descriptor.plugin_id if calibrations else None)
            )
        self.setup_page.set_calibrations(
            calibrations, preferred_id=selected_calibration
        )
        compatible_processors = []
        for processor in self.registry.plugins(PluginType.PROCESSOR):
            try:
                role = processor.requirements().get("processor_role")
            except (AttributeError, TypeError, ValueError) as exc:
                LOGGER.warning(
                    "Ignoring Processor %s with invalid requirements: %s",
                    processor.descriptor.plugin_id,
                    exc,
                )
                continue
            if role == PROCESSOR_ROLE_MOTOR_WEIGHT_COMPENSATION:
                compatible_processors.append(processor)
        processor_ids = {
            item.descriptor.plugin_id for item in compatible_processors
        }
        if not self._plugins_initialized:
            selected_processor = (
                DEFAULT_WEIGHT_PROCESSOR_ID
                if DEFAULT_WEIGHT_PROCESSOR_ID in processor_ids
                else None
            )
        elif selected_processor not in processor_ids:
            selected_processor = None
        self.process_page.set_processors(
            tuple(compatible_processors), preferred_id=selected_processor
        )
        self.export_dialog.set_exporters(
            self.registry.plugins(PluginType.EXPORTER)
        )
        self.plugins_page.set_records(self.registry.records)
        if selected_parser is not None:
            self._parser_selection_changed(selected_parser)
        self._plugins_initialized = True

    def _plugin_install_dialog(self) -> None:
        source = QFileDialog.getExistingDirectory(
            self,
            self.translations.translate("plugins.install"),
            self._dialog_start_directory(),
            options=FILE_DIALOG_OPTIONS,
        )
        if not source:
            return
        answer = QMessageBox.warning(
            self,
            self.translations.translate("page.plugins"),
            self.translations.translate("plugins.warning"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            destination = PluginInstaller_InstallDirectory(
                Path(source), self.user_plugin_directory
            )
            self._last_directory_store(Path(source))
            self._plugins_refresh()
            self.statusBar().showMessage(str(destination), 5000)
        except (OSError, ValueError) as exc:
            self._error_show(exc)

    @staticmethod
    def _directory_open(directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory.resolve())))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.task_timer.stop()
        self.task_manager.shutdown(wait=False, cancel_pending=True)
        super().closeEvent(event)
