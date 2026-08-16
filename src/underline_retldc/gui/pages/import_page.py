from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.data_quality import DataQualityReport
from underline_retldc.core.diagnostics import Diagnostic
from underline_retldc.core.workspace_capabilities import (
    WorkspaceChannelCapabilityRegistry,
)
from underline_retldc.gui.schema_form import SchemaForm
from underline_retldc.gui.tabular_mapping_editor import TabularMappingEditor
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugin_api.common import ProbeResult


class ImportPage(QWidget):
    browse_requested = Signal()
    detect_requested = Signal()
    parse_requested = Signal()
    parser_changed = Signal(object)
    source_selected = Signal(str)
    source_removed = Signal(str)

    def __init__(
        self,
        translations: TranslationService,
        capability_registry: WorkspaceChannelCapabilityRegistry | None = None,
    ) -> None:
        super().__init__()
        self._translations = translations
        self._parsers: tuple[Any, ...] = ()
        self._ambiguity_candidates: tuple[tuple[Any, ProbeResult], ...] = ()

        self.source_label = QLabel()
        self.source_edit = QLineEdit()
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.browse_requested)
        self.remove_source_button = QPushButton()
        self.source_list = QListWidget()
        self.source_list.setMaximumHeight(96)
        self.source_list.currentRowChanged.connect(self._source_selected)
        self.remove_source_button.clicked.connect(self._source_remove)
        self.time_offset_label = QLabel()
        self.time_offset_edit = QDoubleSpinBox()
        self.time_offset_edit.setDecimals(9)
        self.time_offset_edit.setRange(-1.0e12, 1.0e12)
        self.time_offset_edit.valueChanged.connect(self._time_offset_store)
        self._source_offsets: dict[str, float] = {}

        self.parser_label = QLabel()
        self.parser_combo = StandardComboBox()
        self.parser_combo.currentIndexChanged.connect(self._parser_combo_changed)
        self.detect_button = QPushButton()
        self.detect_button.clicked.connect(self.detect_requested)
        self.parse_button = QPushButton()
        self.parse_button.setObjectName("primaryButton")
        self.parse_button.clicked.connect(self.parse_requested)

        source_row = QHBoxLayout()
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(self.browse_button)
        source_row.addWidget(self.remove_source_button)
        offset_row = QHBoxLayout()
        offset_row.addWidget(self.time_offset_edit)
        offset_row.addStretch(1)
        parser_row = QHBoxLayout()
        parser_row.addWidget(self.parser_combo, 1)
        parser_row.addWidget(self.detect_button)
        parser_row.addWidget(self.parse_button)

        self.configuration_group = QGroupBox()
        self.configuration_form = SchemaForm(translations)
        self.tabular_mapping_editor = TabularMappingEditor(
            translations,
            capability_registry,
        )
        self.tabular_mapping_editor.hide()
        configuration_layout = QVBoxLayout(self.configuration_group)
        configuration_layout.addWidget(self.configuration_form)
        configuration_layout.addWidget(self.tabular_mapping_editor)

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
        self.recommendation_table.cellDoubleClicked.connect(
            self._recommendation_activate
        )
        recommendation_layout = QVBoxLayout(self.recommendation_group)
        recommendation_layout.addWidget(self.recommendation_table)

        self.ambiguity_group = QGroupBox()
        self.ambiguity_layout = QVBoxLayout(self.ambiguity_group)
        self.ambiguity_hint = QLabel()
        self.ambiguity_hint.setWordWrap(True)
        self.ambiguity_layout.addWidget(self.ambiguity_hint)
        self.ambiguity_selected = QLabel()
        self.ambiguity_selected.setWordWrap(True)
        self.ambiguity_layout.addWidget(self.ambiguity_selected)
        self.ambiguity_button_group = QButtonGroup(self)
        self.ambiguity_button_group.setExclusive(True)
        self._ambiguity_buttons: list[QRadioButton] = []
        self.ambiguity_group.hide()

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
        form.addRow("", self.source_list)
        form.addRow(self.time_offset_label, offset_row)
        form.addRow(self.parser_label, parser_row)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.configuration_group)
        layout.addWidget(self.ambiguity_group)
        middle = QHBoxLayout()
        middle.addWidget(self.recommendation_group, 1)
        middle.addWidget(self.summary_group, 1)
        layout.addLayout(middle)
        layout.addWidget(self.diagnostics_group, 1)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.source_label.setText(t("import.source_file"))
        self.browse_button.setText(t("import.add_sources"))
        self.remove_source_button.setText(t("import.remove_source"))
        self.time_offset_label.setText(t("import.time_offset"))
        self.parser_label.setText(t("import.parser"))
        self.detect_button.setText(t("import.detect"))
        self.parse_button.setText(t("import.parse"))
        self.configuration_group.setTitle(t("import.configuration"))
        self.recommendation_group.setTitle(t("import.recommended"))
        self.summary_group.setTitle(t("import.summary"))
        self.diagnostics_group.setTitle(t("import.diagnostics"))
        self.ambiguity_group.setTitle(t("parser.ambiguous_title"))
        self.ambiguity_hint.setText(t("parser.ambiguous_hint"))
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
        self.tabular_mapping_editor.retranslate()
        if self.uses_tabular_mapping():
            self.parse_button.setText(t("tabular.import"))
        self._populate_parsers(self.selected_parser_id())
        self._ambiguity_rebuild()

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
        if plugin_id is None:
            return
        for button in self._ambiguity_buttons:
            if button.property("parserPluginId") == plugin_id:
                button.setChecked(True)
                break

    def _parser_combo_changed(self, _index: int) -> None:
        plugin_id = self.selected_parser_id()
        if self._ambiguity_buttons:
            selected_button = next(
                (
                    button
                    for button in self._ambiguity_buttons
                    if button.property("parserPluginId") == plugin_id
                ),
                None,
            )
            if selected_button is not None:
                selected_button.setChecked(True)
            else:
                self.ambiguity_button_group.setExclusive(False)
                for button in self._ambiguity_buttons:
                    button.setChecked(False)
                self.ambiguity_button_group.setExclusive(True)
                self.parse_button.setEnabled(plugin_id is not None)
                self.ambiguity_selected.setText(
                    self._translations.translate(
                        "parser.ambiguous_selected",
                        parser=(
                            self.parser_combo.currentText()
                            if plugin_id is not None
                            else self._translations.translate("primary_channels.none")
                        ),
                    )
                )
        self.parser_changed.emit(plugin_id)

    def source_path(self) -> Path:
        entries = self.source_entries()
        value = self.source_edit.text().strip()
        if not value and entries:
            value = str(entries[0][0])
        if not value:
            raise ValueError("Select a source file")
        return Path(value)

    def set_source_path(self, source: Path) -> None:
        self.set_source_entries(((Path(source), 0.0),))

    def source_paths(self) -> tuple[Path, ...]:
        return tuple(path for path, _offset in self.source_entries())

    def source_entries(self) -> tuple[tuple[Path, float], ...]:
        if self.source_list.count() == 0:
            value = self.source_edit.text().strip()
            return ((Path(value), 0.0),) if value else ()
        return tuple(
            (
                Path(self.source_list.item(index).data(Qt.ItemDataRole.UserRole)),
                float(
                    self._source_offsets.get(
                        str(self.source_list.item(index).data(Qt.ItemDataRole.UserRole)),
                        0.0,
                    )
                ),
            )
            for index in range(self.source_list.count())
        )

    def set_source_entries(
        self, entries: tuple[tuple[Path, float], ...] | list[tuple[Path, float]]
    ) -> None:
        self.source_list.blockSignals(True)
        self.source_list.clear()
        self._source_offsets.clear()
        for path, offset in entries:
            resolved_text = str(Path(path))
            item = QListWidgetItem(Path(path).name)
            item.setToolTip(resolved_text)
            item.setData(Qt.ItemDataRole.UserRole, resolved_text)
            self.source_list.addItem(item)
            self._source_offsets[resolved_text] = float(offset)
        self.source_list.blockSignals(False)
        if self.source_list.count():
            self.source_list.setCurrentRow(0)
            self._source_selected(0)
        else:
            self.source_edit.clear()
            self.time_offset_edit.setValue(0.0)

    def add_source_paths(self, sources: tuple[Path, ...] | list[Path]) -> None:
        entries = list(self.source_entries())
        existing = {str(path.resolve()) for path, _offset in entries}
        for source in sources:
            path = Path(source)
            resolved = str(path.resolve())
            if resolved not in existing:
                entries.append((path, 0.0))
                existing.add(resolved)
        self.set_source_entries(entries)
        if self.source_list.count():
            self.source_list.setCurrentRow(self.source_list.count() - 1)

    def set_source_details(
        self,
        source: Path,
        *,
        parser_id: str,
        stream_name: str,
        channel_count: int,
        status: str,
    ) -> None:
        target = Path(source).resolve()
        for index in range(self.source_list.count()):
            item = self.source_list.item(index)
            item_path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
            try:
                matches = item_path.resolve() == target
            except OSError:
                matches = item_path == Path(source)
            if not matches:
                continue
            item.setText(
                self._translations.translate(
                    "import.source_details",
                    file=item_path.name,
                    parser=parser_id,
                    stream=stream_name,
                    channels=channel_count,
                    status=status,
                )
            )
            return

    def _source_selected(self, row: int) -> None:
        if row < 0 or row >= self.source_list.count():
            return
        path_text = str(self.source_list.item(row).data(Qt.ItemDataRole.UserRole))
        self.source_edit.setText(path_text)
        self.time_offset_edit.blockSignals(True)
        self.time_offset_edit.setValue(self._source_offsets.get(path_text, 0.0))
        self.time_offset_edit.blockSignals(False)
        self.source_selected.emit(path_text)

    def _time_offset_store(self, value: float) -> None:
        row = self.source_list.currentRow()
        if row < 0:
            return
        path_text = str(self.source_list.item(row).data(Qt.ItemDataRole.UserRole))
        self._source_offsets[path_text] = float(value)

    def _source_remove(self) -> None:
        row = self.source_list.currentRow()
        if row < 0:
            return
        item = self.source_list.takeItem(row)
        path_text = str(item.data(Qt.ItemDataRole.UserRole))
        self._source_offsets.pop(path_text, None)
        self.source_removed.emit(path_text)
        if self.source_list.count() == 0:
            self.source_edit.clear()
            self.time_offset_edit.setValue(0.0)
        else:
            self.source_list.setCurrentRow(
                min(row, self.source_list.count() - 1)
            )

    def parser_config(self) -> dict[str, Any]:
        if not self.tabular_mapping_editor.isHidden():
            return self.tabular_mapping_editor.config()
        return self.configuration_form.values()

    def set_parser_config(self, config: dict[str, Any]) -> None:
        if not self.tabular_mapping_editor.isHidden():
            self.tabular_mapping_editor.set_config(config)
            return
        self.configuration_form.set_values(config)

    def set_parser_schema(
        self,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
        *,
        parser_id: str = "",
        parser_version: str = "",
    ) -> None:
        tabular_capability = schema.get("x-underline-retldc-tabular")
        if isinstance(tabular_capability, dict):
            reader_kind = str(tabular_capability.get("reader", ""))
            self.configuration_form.hide()
            self.tabular_mapping_editor.show()
            self.tabular_mapping_editor.set_parser(
                parser_id,
                parser_version,
                reader_kind,
            )
            self.tabular_mapping_editor.set_config(config or {})
            self.parse_button.setText(self._translations.translate("tabular.import"))
            return
        self.tabular_mapping_editor.hide()
        self.configuration_form.show()
        self.configuration_form.set_schema(schema, config)
        self.parse_button.setText(self._translations.translate("import.parse"))

    def uses_tabular_mapping(self) -> bool:
        return not self.tabular_mapping_editor.isHidden()

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
        QTimer.singleShot(0, self._recommendation_table_layout_refresh)

    def _recommendation_table_layout_refresh(self) -> None:
        header = self.recommendation_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.recommendation_table.updateGeometry()
        self.recommendation_table.viewport().update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._recommendation_table_layout_refresh)

    def _recommendation_activate(self, row: int, _column: int) -> None:
        item = self.recommendation_table.item(row, 0)
        if item is None:
            return
        plugin_id = item.data(Qt.ItemDataRole.UserRole)
        if plugin_id:
            self.set_parser_id(str(plugin_id))

    def set_parser_ambiguity(
        self,
        candidates: list[tuple[Any, ProbeResult]] | tuple[tuple[Any, ProbeResult], ...],
    ) -> None:
        self._ambiguity_candidates = tuple(candidates)
        self._ambiguity_rebuild()

    def _ambiguity_rebuild(self) -> None:
        selected_id = self.selected_parser_id()
        for button in self._ambiguity_buttons:
            self.ambiguity_button_group.removeButton(button)
            self.ambiguity_layout.removeWidget(button)
            button.deleteLater()
        self._ambiguity_buttons.clear()
        for plugin, probe in self._ambiguity_candidates:
            descriptor = plugin.descriptor
            name = self._translations.translate(
                descriptor.translation_key or "",
                descriptor.name,
            )
            button = QRadioButton(
                f"{name}\n"
                + self._translations.translate(
                    "parser.ambiguous_confidence",
                    confidence=f"{probe.confidence:.2f}",
                )
            )
            button.setProperty("parserPluginId", descriptor.plugin_id)
            button.setToolTip(probe.reason)
            button.setChecked(descriptor.plugin_id == selected_id)
            button.toggled.connect(
                lambda checked, plugin_id=descriptor.plugin_id: self._ambiguity_select(
                    checked,
                    plugin_id,
                )
            )
            self.ambiguity_button_group.addButton(button)
            self.ambiguity_layout.addWidget(button)
            self._ambiguity_buttons.append(button)
        self.ambiguity_group.setVisible(bool(self._ambiguity_buttons))
        if self._ambiguity_buttons:
            selected_button = self.ambiguity_button_group.checkedButton()
            self.parse_button.setEnabled(selected_button is not None)
            self.ambiguity_selected.setText(
                self._translations.translate(
                    "parser.ambiguous_selected",
                    parser=(
                        self.parser_combo.currentText()
                        if selected_button is not None and selected_id is not None
                        else self._translations.translate("primary_channels.none")
                    ),
                )
            )
        else:
            self.ambiguity_selected.clear()
            self.parse_button.setEnabled(True)

    def _ambiguity_select(self, checked: bool, plugin_id: str) -> None:
        if checked:
            self.set_parser_id(plugin_id)
            self.parse_button.setEnabled(True)
            self.ambiguity_selected.setText(
                self._translations.translate(
                    "parser.ambiguous_selected",
                    parser=self.parser_combo.currentText(),
                )
            )

    def clear_parser_ambiguity(self) -> None:
        self._ambiguity_candidates = ()
        self._ambiguity_rebuild()

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
        self.clear_parser_ambiguity()
