from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.data_quality import DataQualityReport
from underline_retldc.core.diagnostics import Diagnostic
from underline_retldc.gui.schema_form import SchemaForm
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugin_api.common import ProbeResult


class ImportPage(QWidget):
    browse_requested = Signal()
    detect_requested = Signal()
    parse_requested = Signal()
    parser_changed = Signal(object)

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self._parsers: tuple[Any, ...] = ()

        self.source_label = QLabel()
        self.source_edit = QLineEdit()
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.browse_requested)

        self.parser_label = QLabel()
        self.parser_combo = StandardComboBox()
        self.parser_combo.currentIndexChanged.connect(
            lambda _index: self.parser_changed.emit(self.parser_combo.currentData())
        )
        self.detect_button = QPushButton()
        self.detect_button.clicked.connect(self.detect_requested)
        self.parse_button = QPushButton()
        self.parse_button.setObjectName("primaryButton")
        self.parse_button.clicked.connect(self.parse_requested)

        source_row = QHBoxLayout()
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(self.browse_button)
        parser_row = QHBoxLayout()
        parser_row.addWidget(self.parser_combo, 1)
        parser_row.addWidget(self.detect_button)
        parser_row.addWidget(self.parse_button)

        self.configuration_group = QGroupBox()
        self.configuration_form = SchemaForm(translations)
        configuration_layout = QVBoxLayout(self.configuration_group)
        configuration_layout.addWidget(self.configuration_form)

        self.recommendation_group = QGroupBox()
        self.recommendation_table = QTableWidget(0, 2)
        self.recommendation_table.verticalHeader().setVisible(False)
        self.recommendation_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recommendation_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.recommendation_table.setMinimumWidth(300)
        self.recommendation_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.recommendation_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        recommendation_layout = QVBoxLayout(self.recommendation_group)
        recommendation_layout.addWidget(self.recommendation_table)

        self.summary_group = QGroupBox()
        self.summary_values = {key: QLabel("—") for key in (
            "sample_count",
            "duration",
            "median_dt",
            "nominal_rate",
            "timing_warnings",
        )}
        self.summary_labels = {key: QLabel() for key in self.summary_values}
        summary_layout = QFormLayout(self.summary_group)
        for key in self.summary_values:
            summary_layout.addRow(self.summary_labels[key], self.summary_values[key])

        self.diagnostics_group = QGroupBox()
        self.diagnostics_list = QListWidget()
        diagnostics_layout = QVBoxLayout(self.diagnostics_group)
        diagnostics_layout.addWidget(self.diagnostics_list)

        form = QFormLayout()
        form.addRow(self.source_label, source_row)
        form.addRow(self.parser_label, parser_row)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.configuration_group)
        middle = QHBoxLayout()
        middle.addWidget(self.recommendation_group, 1)
        middle.addWidget(self.summary_group, 1)
        layout.addLayout(middle)
        layout.addWidget(self.diagnostics_group, 1)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.source_label.setText(t("import.source_file"))
        self.browse_button.setText(t("common.browse"))
        self.parser_label.setText(t("import.parser"))
        self.detect_button.setText(t("import.detect"))
        self.parse_button.setText(t("import.parse"))
        self.configuration_group.setTitle(t("import.configuration"))
        self.recommendation_group.setTitle(t("import.recommended"))
        self.summary_group.setTitle(t("import.summary"))
        self.diagnostics_group.setTitle(t("import.diagnostics"))
        self.recommendation_table.setHorizontalHeaderLabels(
            [t("import.parser"), t("common.confidence")]
        )
        labels = {
            "sample_count": "import.sample_count",
            "duration": "import.duration",
            "median_dt": "import.median_dt",
            "nominal_rate": "import.nominal_rate",
            "timing_warnings": "import.timing_warnings",
        }
        for key, translation_key in labels.items():
            self.summary_labels[key].setText(t(translation_key))
        self.configuration_form.retranslate()
        self._populate_parsers(self.selected_parser_id())

    def set_parsers(
        self, parsers: tuple[Any, ...], *, preferred_id: str | None = None
    ) -> None:
        selected = preferred_id if preferred_id is not None else self.selected_parser_id()
        self._parsers = parsers
        self._populate_parsers(selected)

    def _populate_parsers(self, selected: str | None) -> None:
        self.parser_combo.blockSignals(True)
        self.parser_combo.clear()
        self.parser_combo.addItem(self._translations.translate("import.auto_detect"), None)
        for parser in self._parsers:
            descriptor = parser.descriptor
            name = self._translations.translate(
                descriptor.translation_key or "", descriptor.name
            )
            self.parser_combo.addItem(name, descriptor.plugin_id)
        index = self.parser_combo.findData(selected)
        self.parser_combo.setCurrentIndex(max(0, index))
        self.parser_combo.blockSignals(False)

    def selected_parser_id(self) -> str | None:
        return self.parser_combo.currentData()

    def set_parser_id(self, plugin_id: str | None) -> None:
        index = self.parser_combo.findData(plugin_id)
        self.parser_combo.setCurrentIndex(max(0, index))

    def source_path(self) -> Path:
        value = self.source_edit.text().strip()
        if not value:
            raise ValueError("Select a source file")
        return Path(value)

    def set_source_path(self, source: Path) -> None:
        self.source_edit.setText(str(source))

    def parser_config(self) -> dict[str, Any]:
        return self.configuration_form.values()

    def set_parser_config(self, config: dict[str, Any]) -> None:
        self.configuration_form.set_values(config)

    def set_parser_schema(
        self, schema: dict[str, Any], config: dict[str, Any] | None = None
    ) -> None:
        self.configuration_form.set_schema(schema, config)

    def set_recommendations(self, recommendations: list[tuple[Any, ProbeResult]]) -> None:
        self.recommendation_table.setRowCount(len(recommendations))
        for row, (plugin, probe) in enumerate(recommendations):
            descriptor = plugin.descriptor
            name = self._translations.translate(
                descriptor.translation_key or "", descriptor.name
            )
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, descriptor.plugin_id)
            confidence_item = QTableWidgetItem(f"{probe.confidence:.3f}")
            confidence_item.setToolTip(probe.reason)
            self.recommendation_table.setItem(row, 0, name_item)
            self.recommendation_table.setItem(row, 1, confidence_item)

    def set_summary(self, report: DataQualityReport) -> None:
        warning_count = sum(
            1 for item in report.diagnostics if item.severity.value == "WARNING"
        )
        self.summary_values["sample_count"].setText(str(report.sample_count))
        self.summary_values["duration"].setText(
            "—" if report.duration is None else f"{report.duration:.6g} s"
        )
        self.summary_values["median_dt"].setText(
            "—" if report.median_dt is None else f"{report.median_dt:.6g} s"
        )
        self.summary_values["nominal_rate"].setText(
            "—" if report.nominal_rate_hz is None else f"{report.nominal_rate_hz:.6g} Hz"
        )
        self.summary_values["timing_warnings"].setText(str(warning_count))

    def set_diagnostics(self, diagnostics: tuple[Diagnostic, ...] | list[Diagnostic]) -> None:
        self.diagnostics_list.clear()
        for diagnostic in diagnostics:
            location = f" line {diagnostic.line}" if diagnostic.line is not None else ""
            message = self._translations.translate(
                f"diagnostic.{diagnostic.code}",
                diagnostic.message,
                message=diagnostic.message,
            )
            self.diagnostics_list.addItem(
                f"[{diagnostic.severity.value}] {diagnostic.code}{location}: {message}"
            )

    def clear_results(self) -> None:
        self.recommendation_table.setRowCount(0)
        for value in self.summary_values.values():
            value.setText("—")
        self.diagnostics_list.clear()
