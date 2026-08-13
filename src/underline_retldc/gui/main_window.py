from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
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

from underline_retldc.app.session import AnalysisSession
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
)
from underline_retldc.core.data_quality import Dataset_QualityInspect
from underline_retldc.core.pipeline import Calibration_Apply, Processing_Passthrough
from underline_retldc.core.project import (
    PluginReference,
    Project_DefaultExportDirectory,
    Project_Load,
    Project_Save,
    Project_SourceHash,
    Project_SourceResolve,
    ProjectDocument,
    ProjectSourceHashMismatchError,
    ProjectSourceResolveResult,
)
from underline_retldc.core.region_detection import Burn_DetectCandidates
from underline_retldc.core.registry import PluginLoadResult, PluginRegistry
from underline_retldc.core.task import TaskHandle, TaskManager, TaskResult
from underline_retldc.gui.pages.analyze_page import AnalyzePage
from underline_retldc.gui.pages.export_page import ExportDialog
from underline_retldc.gui.pages.import_page import ImportPage
from underline_retldc.gui.pages.plugins_page import PluginsPage
from underline_retldc.gui.pages.process_page import ProcessPage
from underline_retldc.gui.pages.settings_page import SettingsPage
from underline_retldc.gui.pages.setup_page import SetupPage
from underline_retldc.gui.pages.workspace_pages import (
    ProjectWorkspacePage,
    ThrustAnalysisWorkspacePage,
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

        self.import_page = ImportPage(translations)
        self.setup_page = SetupPage(translations)
        self.process_page = ProcessPage(translations)
        self.analyze_page = AnalyzePage(translations)
        self.project_page = ProjectWorkspacePage(
            translations, self.import_page, self.setup_page
        )
        self.thrust_analysis_page = ThrustAnalysisWorkspacePage(
            self.process_page, self.analyze_page
        )
        self.analysis_page = self.thrust_analysis_page
        self.export_dialog = ExportDialog(translations, self)
        self.export_page = self.export_dialog
        self.plugins_page = PluginsPage(translations)
        self.settings_page = SettingsPage(translations, self._theme)
        self.workspaces = (
            ("project", "page.project", self.project_page),
            ("thrust_analysis", "page.thrust_analysis", self.thrust_analysis_page),
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
        self.navigation.setFixedWidth(170)
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
        self.setup_page.apply_requested.connect(self._calibration_apply)
        self.setup_page.load_requested.connect(self._calibration_load_dialog)
        self.setup_page.save_requested.connect(self._calibration_save_dialog)
        self.process_page.detect_requested.connect(self._burn_detect)
        self.process_page.apply_requested.connect(self._processing_apply)
        self.process_page.plugins_requested.connect(self._plugins_dialog_show)
        self.process_page.regions_changed.connect(self._regions_store)
        self.analyze_page.calculate_requested.connect(self._analysis_calculate)
        self.analyze_page.confirmation_changed.connect(self._curve_confirmation_update)
        self.project_page.analysis_requested.connect(
            lambda: self._workspace_select("thrust_analysis")
        )
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

    def _retranslate(self) -> None:
        t = self.translations.translate
        self.setWindowTitle(f"{PRODUCT_NAME} — {__version__}")
        self.header_title.setText(
            f"{t('app.title')}  ·  {self._project_title or t('project.untitled')}"
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
        self.settings_page.set_theme(normalized)
        self._retranslate()

    def _plugins_dialog_show(self) -> None:
        self.plugins_dialog.show()
        self.plugins_dialog.raise_()

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

    def _completed_analysis_ids(self) -> tuple[str, ...]:
        if self.session.analysis_result is None or self.session.analyzer_id is None:
            return ()
        return (self.session.analyzer_id,)

    def _export_availability_update(self) -> None:
        self.export_dialog.set_completed_analysis_ids(self._completed_analysis_ids())

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
        self.import_page.source_edit.clear()
        self.import_page.clear_results()
        self.process_page.clear_state()
        self.analyze_page.clear_result()
        self._export_availability_update()
        self.setup_page.set_motor_metadata({})
        self.export_dialog.directory_edit.clear()
        self.export_dialog.set_motor_metadata({})
        self.export_dialog.set_output_locale(self.translations.locale)
        self.import_page.set_parser_id(DEFAULT_PARSER_ID)
        self._parser_selection_changed(DEFAULT_PARSER_ID)
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
        source, _filter = QFileDialog.getOpenFileName(
            self,
            self.translations.translate("dialog.select_source"),
            self._dialog_start_directory(),
            "Test logs (*.txt *.csv *.log);;All files (*)",
            options=FILE_DIALOG_OPTIONS,
        )
        if source:
            path = Path(source)
            self._project_new()
            self.import_page.set_source_path(path)
            self._last_directory_store(path)

    def _source_browse(self) -> None:
        self._source_open_dialog()

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
            self.import_page.set_parser_schema(schema, config)
        except (KeyError, TypeError, ValueError) as exc:
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
            if results and results[0][1].confidence > 0:
                self.import_page.set_parser_id(results[0][0].descriptor.plugin_id)

        self._task_start(self.translations.translate("import.detect"), operation, success)

    def _source_parse(self) -> None:
        try:
            source = self.import_page.source_path()
            parser_config = self.import_page.parser_config()
            selected_id = self.import_page.selected_parser_id()
        except (ValueError, OSError) as exc:
            self._error_show(exc)
            return
        parsers = self.registry.plugins(PluginType.PARSER)

        def operation(
            context: TaskContext,
        ) -> tuple[str, dict[str, Any], ParseResult, list[tuple[Any, ProbeResult]]]:
            recommendations = self._recommendations
            if selected_id is None and (
                self._recommendation_source != source or not recommendations
            ):
                recommendations = [
                    (parser, parser.probe(source, ProbeContext())) for parser in parsers
                ]
                recommendations.sort(key=lambda item: item[1].confidence, reverse=True)
            parser_id = selected_id
            if parser_id is None:
                if not recommendations or recommendations[0][1].confidence <= 0:
                    raise ValueError("No Parser recognized this source; select one manually")
                parser_id = recommendations[0][0].descriptor.plugin_id
            parser = self.registry.get(parser_id)
            properties = parser.config_schema().get("properties", {})
            defaults = {
                key: value["default"]
                for key, value in properties.items()
                if isinstance(value, dict) and "default" in value
            }
            effective_config = {**defaults, **parser_config}
            return (
                parser_id,
                effective_config,
                parser.parse(source, effective_config, context),
                recommendations,
            )

        def success(
            payload: tuple[
                str, dict[str, Any], ParseResult, list[tuple[Any, ProbeResult]]
            ],
        ) -> None:
            parser_id, effective_config, result, recommendations = payload
            self._recommendations = recommendations
            self._recommendation_source = source
            report = Dataset_QualityInspect(result.dataset)
            self.session.source_path = source.resolve()
            self.session.parser_id = parser_id
            self.session.parser_config = dict(effective_config)
            self.session.raw_dataset = result.dataset
            self.session.quality_report = report
            self.session.reset_after_parse()
            self.import_page.set_recommendations(recommendations)
            self.import_page.set_parser_id(parser_id)
            self.import_page.set_parser_config(effective_config)
            self.import_page.set_summary(report)
            self.import_page.set_diagnostics(result.dataset.diagnostics)
            self.process_page.set_datasets(result.dataset, None, None)
            self.analyze_page.clear_result()
            self._export_availability_update()
            self.statusBar().showMessage(
                self.translations.translate(
                    "status.loaded_samples", count=result.dataset.sample_count
                ),
                5000,
            )

        self._task_start(self.translations.translate("status.parsing"), operation, success)

    def _calibration_apply(self) -> None:
        if self.session.raw_dataset is None:
            self._error_show(ValueError("Import a source file before calibration"))
            return
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
        raw_dataset = self.session.raw_dataset

        def operation(context: TaskContext):
            context.raise_if_cancelled()
            dataset = Calibration_Apply(
                raw_dataset,
                model,
                input_channel_id=config["input_channel_id"],
                output_channel_id=config["output_channel_id"],
                quantity=config["quantity"],
                unit=config["unit"],
                parameters=config["parameters"],
            )
            context.report_progress(1.0, "Calibration complete")
            return dataset

        def success(dataset) -> None:
            self.session.reset_after_calibration()
            self.session.calibration_id = plugin_id
            self.session.calibration_config = dict(config)
            self.session.calibrated_dataset = dataset
            self.session.motor_metadata = metadata
            self.process_page.set_datasets(self.session.raw_dataset, dataset, None)
            self.analyze_page.clear_result()
            self._export_availability_update()
            self.statusBar().showMessage(
                self.translations.translate("status.calibration_applied"), 5000
            )

        self._task_start(self.translations.translate("setup.apply_calibration"), operation, success)

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
        dataset = self.session.calibrated_dataset
        if dataset is None:
            self._error_show(ValueError("Apply calibration before burn detection"))
            return
        sign = self.process_page.detection_sign()
        channel = dataset.channel("force_calibrated")

        def operation(context: TaskContext):
            context.raise_if_cancelled()
            result = Burn_DetectCandidates(dataset.time, channel.values, sign=sign)
            context.report_progress(1.0, "Burn candidates detected")
            return result

        def success(candidates) -> None:
            self.session.candidates = list(candidates)
            self.process_page.set_candidates(list(candidates))
            self._regions_store()

        self._task_start(
            self.translations.translate("process.detect_candidates"), operation, success
        )

    def _regions_store(self) -> None:
        try:
            self.session.regions = self.process_page.regions()
        except ValueError:
            return

    def _processing_apply(self) -> None:
        dataset = self.session.calibrated_dataset
        if dataset is None:
            self._error_show(ValueError("Apply calibration before processing"))
            return
        try:
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
                result = Processing_Passthrough(dataset)
                context.report_progress(1.0, "Processing pass-through complete")
                return result
            return processor.process(dataset, config, context)

        def success(result: ProcessingResult) -> None:
            self.session.reset_after_processing()
            self.session.processor_id = plugin_id
            self.session.processor_config = dict(config)
            self.session.processing_result = result
            self.session.regions = self.process_page.regions()
            self.session.motor_metadata = motor_metadata
            self.process_page.set_datasets(
                self.session.raw_dataset,
                self.session.calibrated_dataset,
                result.dataset,
            )
            self.analyze_page.clear_result()
            self._export_availability_update()
            self.statusBar().showMessage(
                self.translations.translate("status.processing_applied"), 5000
            )
            self._workspace_select("thrust_analysis")

        self._task_start(self.translations.translate("status.processing"), operation, success)

    def _analysis_calculate(self) -> None:
        processing = self.session.processing_result
        if processing is None:
            self._error_show(ValueError("Apply processing before analysis"))
            return
        try:
            regions = self.process_page.regions()
            metadata = self.setup_page.motor_metadata()
            plugin_id = THRUST_ANALYZER_ID
            analyzer = self.registry.get(plugin_id)
            config: dict[str, Any] = {
                "channel_id": "thrust_processed",
                "ignition": regions["burn"][0],
                "burnout": regions["burn"][1],
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
            self.session.regions = regions
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
        calibration_id = self.session.calibration_id or self.setup_page.calibration_id()
        calibration_config = (
            self.session.calibration_config
            if self.session.calibration_id == calibration_id
            and self.session.calibration_config
            else self.setup_page.calibration_config()
        )
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
        return ProjectDocument(
            source_path=str(source_path) if source_path is not None else None,
            source_hash=source_hash or self.session.source_hash,
            parser=self._plugin_reference_create(parser_id, dict(parser_config)),
            calibration=self._plugin_reference_create(
                calibration_id, dict(calibration_config)
            ),
            processors=processors,
            regions=self.session.regions,
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
            if document_template.source_path:
                configured_source = Path(document_template.source_path)
                if configured_source.is_file():
                    source_hash = Project_SourceHash(configured_source)
                    context.report_progress(0.6, "Source hash calculated")
            document = replace(document_template, source_hash=source_hash)
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
            self.session = AnalysisSession(
                project_path=project_path,
                source_path=raw_source.resolve() if raw_source is not None else None,
                source_hash=document.source_hash,
                parser_id=document.parser.id if document.parser else None,
                parser_config=dict(document.parser.config) if document.parser else {},
                raw_dataset=parse_result.dataset if parse_result else None,
                quality_report=(
                    Dataset_QualityInspect(parse_result.dataset) if parse_result else None
                ),
                calibration_id=document.calibration.id if document.calibration else None,
                calibration_config=(
                    dict(document.calibration.config) if document.calibration else {}
                ),
                calibrated_dataset=calibrated,
                processor_id=document.processors[0].id if document.processors else None,
                processor_config=(
                    dict(document.processors[0].config) if document.processors else {}
                ),
                processing_result=processing_result,
                regions={key: list(value) for key, value in document.regions.items()},
                analyzer_id=document.analyzer.id if document.analyzer else None,
                analyzer_config=(
                    dict(document.analyzer.config) if document.analyzer else {}
                ),
                analysis_result=analysis,
                motor_metadata=dict(document.motor_metadata),
                export_settings=dict(document.export_settings),
                curve_confirmed=bool(document.export_settings.get("curve_confirmed", False)),
            )
            self._recommendations.clear()
            self._recommendation_source = None
            self.import_page.clear_results()
            if raw_source is not None:
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
            self.setup_page.set_motor_metadata(dict(document.motor_metadata))
            self.process_page.clear_state()
            self.process_page.set_datasets(
                parse_result.dataset if parse_result else None,
                calibrated,
                processing_result.dataset if processing_result else None,
            )
            processor_id = document.processors[0].id if document.processors else None
            processor_config = (
                dict(document.processors[0].config) if document.processors else {}
            )
            self.process_page.set_processing_config(processor_id, processor_config)
            if document.regions:
                self.process_page.set_regions(
                    {key: list(value) for key, value in document.regions.items()}
                )
            if analysis is not None:
                self.analyze_page.set_result(
                    analysis, confirmed=self.session.curve_confirmed
                )
            else:
                self.analyze_page.clear_result()
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
            self._workspace_select(
                "thrust_analysis" if processing_result is not None else "project"
            )
            self.statusBar().showMessage(
                self.translations.translate("status.project_loaded"), 5000
            )

        self._task_start(self.translations.translate("export.open_project"), operation, success)

    def _project_recompute(
        self,
        document: ProjectDocument,
        context: TaskContext,
        *,
        raw_source: Path | None = None,
    ):
        self._project_references_validate(document)
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
        state = dict(document.workflow_state)
        if not state:
            state = {
                "parsed": document.parser is not None,
                "calibrated": document.calibration is not None,
                "processed": bool(document.processors),
                "analyzed": document.analyzer is not None,
            }
        if not state.get("parsed", False):
            return document, raw_source, None, None, None, None
        parser = self._plugin_reference_resolve(document.parser)
        parse_result = parser.parse(raw_source, document.parser.config, context)
        if document.calibration is None or not state.get("calibrated", False):
            return document, raw_source, parse_result, None, None, None
        calibration = self._plugin_reference_resolve(document.calibration)
        calibration_config = dict(document.calibration.config)
        calibrated = Calibration_Apply(
            parse_result.dataset,
            calibration,
            input_channel_id=calibration_config["input_channel_id"],
            output_channel_id=calibration_config["output_channel_id"],
            quantity=calibration_config["quantity"],
            unit=calibration_config["unit"],
            parameters=calibration_config["parameters"],
        )
        processor = None
        processor_reference = None
        if document.processors:
            processor_reference = document.processors[0]
            processor = self._plugin_reference_resolve(processor_reference)
        processing_result = None
        if state.get("processed", False):
            if processor is None or processor_reference is None:
                processing_result = Processing_Passthrough(calibrated)
            else:
                processing_result = processor.process(
                    calibrated, processor_reference.config, context
                )
        if (
            processing_result is None
            or document.analyzer is None
            or not state.get("analyzed", False)
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
            *document.processors,
            document.analyzer,
        ]
        for reference in references:
            if reference is not None:
                self._plugin_reference_resolve(reference)

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

    def _export_execute(self) -> None:
        try:
            destination = self.export_dialog.output_directory()
            selected = self.export_dialog.selected_exporter_ids()
            if not selected:
                if THRUST_ANALYZER_ID not in self._completed_analysis_ids():
                    raise ValueError(
                        self.translations.translate("export.complete_thrust_analysis")
                    )
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
            dataset = self.session.processed_dataset
            analysis = self.session.analysis_result
            if dataset is None or analysis is None:
                raise ValueError(
                    self.translations.translate("export.complete_thrust_analysis")
                )
            motor_metadata = self.export_dialog.motor_metadata()
            if not self.session.regions or "burn" not in self.session.regions:
                raise ValueError("Select a burn region before export")
            ignition, burnout = self.session.regions["burn"]
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
        if selected_parser not in parser_ids:
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
