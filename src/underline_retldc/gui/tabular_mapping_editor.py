from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.tabular import (
    Tabular_ColumnLabel,
    TabularColumnUsage,
    TabularPreview,
    TabularTimeMode,
)
from underline_retldc.core.units import Quantity_KnownIds, Unit_KnownSymbols
from underline_retldc.core.workspace_capabilities import (
    WorkspaceCapabilities_Default,
    WorkspaceChannelCapabilityRegistry,
)
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService

_SEMANTIC_ROLES = (
    "",
    "chamber_pressure",
    "injector_pressure",
    "tank_pressure",
    "feed_pressure",
    "thrust",
    "support_force",
    "chamber_wall_temperature",
    "nozzle_temperature",
    "coolant_inlet_temperature",
    "coolant_outlet_temperature",
    "burned_web",
    "burn_area",
    "kn",
    "auxiliary",
    "custom",
)


class TabularMappingEditor(QWidget):
    preview_requested = Signal(bool)
    preset_selected = Signal(str)
    preset_save_requested = Signal()
    preset_delete_requested = Signal(str)
    preset_import_requested = Signal()
    preset_export_requested = Signal()
    mapping_changed = Signal()

    def __init__(
        self,
        translations: TranslationService,
        capability_registry: WorkspaceChannelCapabilityRegistry | None = None,
    ) -> None:
        super().__init__()
        self._translations = translations
        self._reader_kind = ""
        self._parser_id = ""
        self._parser_version = ""
        self._preview: TabularPreview | None = None
        self._config: dict[str, Any] = {}
        self._mapping_rows: list[dict[str, Any]] = []
        self._quick_rows: list[dict[str, Any]] = []
        self._capability_registry = (
            capability_registry or WorkspaceCapabilities_Default()
        )
        self._syncing = False
        self.setMinimumHeight(420)

        self.preset_group = QGroupBox()
        preset_layout = QHBoxLayout(self.preset_group)
        self.preset_combo = StandardComboBox()
        self.preset_combo.currentIndexChanged.connect(self._preset_changed)
        self.preset_save_button = QPushButton()
        self.preset_save_button.clicked.connect(self.preset_save_requested.emit)
        self.preset_delete_button = QPushButton()
        self.preset_delete_button.clicked.connect(self._preset_delete)
        self.preset_import_button = QPushButton()
        self.preset_import_button.clicked.connect(self.preset_import_requested.emit)
        self.preset_export_button = QPushButton()
        self.preset_export_button.clicked.connect(self.preset_export_requested.emit)
        self.auto_mapping_button = QPushButton()
        self.auto_mapping_button.clicked.connect(
            lambda: self.preview_requested.emit(True)
        )
        self.preview_refresh_button = QPushButton()
        self.preview_refresh_button.clicked.connect(
            lambda: self.preview_requested.emit(False)
        )
        preset_layout.addWidget(self.preset_combo, 1)
        for button in (
            self.preset_save_button,
            self.preset_delete_button,
            self.preset_import_button,
            self.preset_export_button,
            self.auto_mapping_button,
            self.preview_refresh_button,
        ):
            preset_layout.addWidget(button)

        self.data_group = QGroupBox()
        data_form = QFormLayout(self.data_group)
        self.sheet_label = QLabel()
        self.sheet_combo = StandardComboBox()
        self.sheet_combo.activated.connect(
            lambda _index: self.preview_requested.emit(False)
        )
        self.delimiter_label = QLabel()
        self.delimiter_combo = StandardComboBox()
        for label, value in (
            ("Auto", "auto"),
            (",", ","),
            (";", ";"),
            ("Tab", "\t"),
            ("Space", " "),
            ("|", "|"),
            ("Custom", "custom"),
        ):
            self.delimiter_combo.addItem(label, value)
        self.delimiter_combo.currentIndexChanged.connect(
            self._delimiter_controls_refresh
        )
        self.custom_delimiter_edit = QLineEdit()
        self.custom_delimiter_edit.setMaximumWidth(80)
        delimiter_row = QHBoxLayout()
        delimiter_row.addWidget(self.delimiter_combo)
        delimiter_row.addWidget(self.custom_delimiter_edit)
        delimiter_row.addStretch(1)
        self.encoding_label = QLabel()
        self.encoding_combo = StandardComboBox()
        for encoding in ("auto", "utf-8-sig", "utf-8", "gb18030", "latin-1"):
            self.encoding_combo.addItem(encoding, encoding)

        self.header_label = QLabel()
        self.header_enabled = QCheckBox()
        self.header_spin = QSpinBox()
        self.header_spin.setRange(1, 1_000_000_000)
        header_row = QHBoxLayout()
        header_row.addWidget(self.header_enabled)
        header_row.addWidget(self.header_spin)
        header_row.addStretch(1)
        self.header_enabled.toggled.connect(self.header_spin.setEnabled)
        self.data_start_label = QLabel()
        self.data_start_spin = QSpinBox()
        self.data_start_spin.setRange(1, 1_000_000_000)
        self.data_end_label = QLabel()
        self.data_end_enabled = QCheckBox()
        self.data_end_spin = QSpinBox()
        self.data_end_spin.setRange(1, 1_000_000_000)
        data_end_row = QHBoxLayout()
        data_end_row.addWidget(self.data_end_enabled)
        data_end_row.addWidget(self.data_end_spin)
        data_end_row.addStretch(1)
        self.data_end_enabled.toggled.connect(self.data_end_spin.setEnabled)
        self.invalid_policy_label = QLabel()
        self.invalid_policy_combo = StandardComboBox()
        self.invalid_policy_combo.addItem("", "preserve")
        self.invalid_policy_combo.addItem("", "error")

        data_form.addRow(self.sheet_label, self.sheet_combo)
        data_form.addRow(self.delimiter_label, delimiter_row)
        data_form.addRow(self.encoding_label, self.encoding_combo)
        data_form.addRow(self.header_label, header_row)
        data_form.addRow(self.data_start_label, self.data_start_spin)
        data_form.addRow(self.data_end_label, data_end_row)
        data_form.addRow(self.invalid_policy_label, self.invalid_policy_combo)

        self.preview_group = QGroupBox()
        preview_layout = QVBoxLayout(self.preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.verticalHeader().setDefaultSectionSize(24)
        preview_layout.addWidget(self.preview_table)

        self.time_group = QGroupBox()
        time_form = QFormLayout(self.time_group)
        self.time_mode_label = QLabel()
        self.time_mode_combo = StandardComboBox()
        for mode in TabularTimeMode:
            self.time_mode_combo.addItem("", mode.value)
        self.time_mode_combo.currentIndexChanged.connect(self._time_controls_refresh)
        self.time_column_label = QLabel()
        self.time_column_combo = StandardComboBox()
        self.time_column_combo.currentIndexChanged.connect(self._time_column_changed)
        self.time_unit_label = QLabel()
        self.time_unit_combo = StandardComboBox()
        for unit in ("s", "ms", "us"):
            self.time_unit_combo.addItem(unit, unit)
        self.sample_rate_label = QLabel()
        self.sample_rate_spin = QDoubleSpinBox()
        self.sample_rate_spin.setDecimals(12)
        self.sample_rate_spin.setRange(1.0e-12, 1.0e12)
        self.sample_rate_spin.setValue(1000.0)
        self.sample_period_label = QLabel()
        self.sample_period_spin = QDoubleSpinBox()
        self.sample_period_spin.setDecimals(12)
        self.sample_period_spin.setRange(1.0e-12, 1.0e12)
        self.sample_period_spin.setValue(0.001)
        time_form.addRow(self.time_mode_label, self.time_mode_combo)
        time_form.addRow(self.time_column_label, self.time_column_combo)
        time_form.addRow(self.time_unit_label, self.time_unit_combo)
        time_form.addRow(self.sample_rate_label, self.sample_rate_spin)
        time_form.addRow(self.sample_period_label, self.sample_period_spin)

        self.mapping_group = QGroupBox()
        mapping_layout = QVBoxLayout(self.mapping_group)
        self.mapping_table = QTableWidget(0, 8)
        self.mapping_table.setAlternatingRowColors(True)
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        header = self.mapping_table.horizontalHeader()
        for column in range(8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        mapping_layout.addWidget(self.mapping_table)

        self.quick_group = QGroupBox()
        quick_layout = QVBoxLayout(self.quick_group)
        self.quick_hint = QLabel()
        self.quick_hint.setWordWrap(True)
        self.quick_table = QTableWidget(0, 4)
        self.quick_table.setAlternatingRowColors(True)
        self.quick_table.verticalHeader().setVisible(False)
        self.quick_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.quick_table.setMinimumHeight(150)
        self.quick_table.setMaximumHeight(340)
        quick_header = self.quick_table.horizontalHeader()
        quick_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        quick_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        quick_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        quick_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.quick_status = QLabel()
        self.quick_status.setWordWrap(True)
        quick_layout.addWidget(self.quick_hint)
        quick_layout.addWidget(self.quick_table)
        quick_layout.addWidget(self.quick_status)

        self.advanced_button = QPushButton()
        self.advanced_button.setCheckable(True)
        self.advanced_button.setChecked(False)
        self.advanced_button.toggled.connect(self._advanced_visibility_update)

        upper = QWidget()
        upper_layout = QVBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.addWidget(self.preset_group)
        upper_layout.addWidget(self.data_group)
        upper_layout.addWidget(self.time_group)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.preview_group)
        splitter.addWidget(self.mapping_group)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([180, 280])

        self.advanced_container = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_container)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(upper)
        advanced_layout.addWidget(splitter, 1)
        self.advanced_container.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.quick_group)
        layout.addWidget(self.advanced_button)
        layout.addWidget(self.advanced_container, 1)
        self._common_signals_connect()
        self.retranslate()
        self._reader_controls_refresh()
        self._time_controls_refresh()

    @property
    def capability_registry(self) -> WorkspaceChannelCapabilityRegistry:
        return self._capability_registry

    def set_capability_registry(
        self, registry: WorkspaceChannelCapabilityRegistry
    ) -> None:
        self._capability_registry = registry
        self._quick_mapping_rebuild()

    def simple_type_ids(self) -> tuple[str, ...]:
        return (
            "time",
            *(item.capability_id for item in self._capability_registry.capabilities),
            "other",
        )

    def set_advanced_expanded(self, expanded: bool) -> None:
        self.advanced_button.setChecked(bool(expanded))

    def _advanced_visibility_update(self, expanded: bool) -> None:
        self.advanced_container.setVisible(bool(expanded))
        self._advanced_button_text_update()

    def _advanced_button_text_update(self) -> None:
        key = (
            "tabular.advanced_hide"
            if self.advanced_button.isChecked()
            else "tabular.advanced_show"
        )
        self.advanced_button.setText(self._translations.translate(key))

    @property
    def parser_id(self) -> str:
        return self._parser_id

    @property
    def parser_version(self) -> str:
        return self._parser_version

    def set_parser(self, parser_id: str, parser_version: str, reader_kind: str) -> None:
        self._parser_id = str(parser_id)
        self._parser_version = str(parser_version)
        self._reader_kind = str(reader_kind)
        self._preview = None
        self._mapping_rows.clear()
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        self.mapping_table.setRowCount(0)
        self.quick_table.setRowCount(0)
        self._quick_rows.clear()
        self._reader_controls_refresh()

    def _common_signals_connect(self) -> None:
        widgets = (
            self.header_enabled,
            self.header_spin,
            self.data_start_spin,
            self.data_end_enabled,
            self.data_end_spin,
            self.invalid_policy_combo,
            self.delimiter_combo,
            self.custom_delimiter_edit,
            self.encoding_combo,
            self.time_mode_combo,
            self.time_column_combo,
            self.time_unit_combo,
            self.sample_rate_spin,
            self.sample_period_spin,
        )
        for widget in widgets:
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._changed)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._changed)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self._changed)
            else:
                widget.currentIndexChanged.connect(self._changed)

    def _changed(self, _value: Any = None) -> None:
        if not self._syncing:
            self.mapping_changed.emit()

    def _reader_controls_refresh(self) -> None:
        is_xlsx = self._reader_kind == "xlsx"
        is_delimited = self._reader_kind == "delimited"
        self.sheet_label.setVisible(is_xlsx)
        self.sheet_combo.setVisible(is_xlsx)
        self.delimiter_label.setVisible(is_delimited)
        self.delimiter_combo.setVisible(is_delimited)
        self.custom_delimiter_edit.setVisible(
            is_delimited and self.delimiter_combo.currentData() == "custom"
        )
        self.encoding_label.setVisible(is_delimited)
        self.encoding_combo.setVisible(is_delimited)

    def _delimiter_controls_refresh(self, _index: int | None = None) -> None:
        self._reader_controls_refresh()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.preset_group.setTitle(t("tabular.presets"))
        self.preset_save_button.setText(t("tabular.preset_save"))
        self.preset_delete_button.setText(t("tabular.preset_delete"))
        self.preset_import_button.setText(t("tabular.preset_import"))
        self.preset_export_button.setText(t("tabular.preset_export"))
        self.auto_mapping_button.setText(t("tabular.auto_mapping"))
        self.preview_refresh_button.setText(t("tabular.preview_refresh"))
        self.data_group.setTitle(t("tabular.data_region"))
        self.sheet_label.setText(t("tabular.sheet"))
        self.delimiter_label.setText(t("tabular.delimiter"))
        self.encoding_label.setText(t("tabular.encoding"))
        self.header_label.setText(t("tabular.header_row"))
        self.header_enabled.setText(t("tabular.header_enabled"))
        self.data_start_label.setText(t("tabular.data_start_row"))
        self.data_end_label.setText(t("tabular.data_end_row"))
        self.data_end_enabled.setText(t("tabular.data_end_enabled"))
        self.invalid_policy_label.setText(t("tabular.invalid_policy"))
        self.invalid_policy_combo.setItemText(0, t("tabular.invalid_preserve"))
        self.invalid_policy_combo.setItemText(1, t("tabular.invalid_error"))
        delimiter_labels = {
            "auto": t("tabular.delimiter.auto"),
            "\t": t("tabular.delimiter.tab"),
            " ": t("tabular.delimiter.space"),
            "custom": t("tabular.delimiter.custom"),
        }
        for index in range(self.delimiter_combo.count()):
            value = str(self.delimiter_combo.itemData(index))
            if value in delimiter_labels:
                self.delimiter_combo.setItemText(index, delimiter_labels[value])
        self.preview_group.setTitle(t("tabular.preview"))
        self.time_group.setTitle(t("tabular.time"))
        self.time_mode_label.setText(t("tabular.time_mode"))
        for index, mode in enumerate(TabularTimeMode):
            self.time_mode_combo.setItemText(
                index, t(f"tabular.time_mode.{mode.value}")
            )
        self.time_column_label.setText(t("tabular.time_column"))
        self.time_unit_label.setText(t("tabular.time_unit"))
        self.sample_rate_label.setText(t("tabular.sample_rate"))
        self.sample_period_label.setText(t("tabular.sample_period"))
        self.mapping_group.setTitle(t("tabular.column_mapping"))
        self.mapping_table.setHorizontalHeaderLabels(
            [
                t("tabular.column"),
                t("tabular.source_header"),
                t("tabular.usage"),
                t("tabular.display_name"),
                t("tabular.channel_id"),
                t("tabular.quantity"),
                t("tabular.semantic_role"),
                t("tabular.unit"),
            ]
        )
        none_index = self.preset_combo.findData(None)
        if none_index >= 0:
            self.preset_combo.setItemText(none_index, t("tabular.preset_none"))
        self.quick_group.setTitle(t("tabular.quick_import"))
        self.quick_hint.setText(t("tabular.quick_hint"))
        self.quick_table.setHorizontalHeaderLabels(
            [
                t("tabular.column"),
                t("tabular.source_header"),
                t("tabular.simple_type"),
                t("tabular.unit"),
            ]
        )
        self._advanced_button_text_update()
        if self._preview is not None:
            self._quick_mapping_rebuild()

    def set_presets(
        self,
        entries: Sequence[tuple[str, str, bool]],
        *,
        selected_path: str | None = None,
    ) -> None:
        self._syncing = True
        self.preset_combo.clear()
        self.preset_combo.addItem(self._translations.translate("tabular.preset_none"), None)
        for name, path, builtin in entries:
            self.preset_combo.addItem(str(name), {"path": str(path), "builtin": bool(builtin)})
        selected_index = 0
        if selected_path:
            for index in range(1, self.preset_combo.count()):
                data = self.preset_combo.itemData(index)
                if isinstance(data, dict) and data.get("path") == selected_path:
                    selected_index = index
                    break
        self.preset_combo.setCurrentIndex(selected_index)
        self._syncing = False
        self._quick_mapping_rebuild()
        self._preset_delete_state_update()

    def _preset_changed(self, _index: int) -> None:
        self._preset_delete_state_update()
        if self._syncing:
            return
        data = self.preset_combo.currentData()
        if isinstance(data, dict) and data.get("path"):
            self.preset_selected.emit(str(data["path"]))

    def _preset_delete_state_update(self) -> None:
        data = self.preset_combo.currentData()
        self.preset_delete_button.setEnabled(
            isinstance(data, dict) and not bool(data.get("builtin", False))
        )

    def _preset_delete(self) -> None:
        data = self.preset_combo.currentData()
        if isinstance(data, dict) and not bool(data.get("builtin", False)):
            self.preset_delete_requested.emit(str(data.get("path", "")))

    def set_config(self, config: Mapping[str, Any]) -> None:
        self._config = _mapping_copy(config)
        self._sync_from_config()

    def set_preview(
        self,
        preview: TabularPreview,
        *,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        self._preview = preview
        if config is not None:
            self._config = _mapping_copy(config)
        else:
            self._config.update(dict(preview.resolved_reader_config))
        self._sync_from_config()
        self._preview_populate()
        self._mapping_rebuild()

    def _sync_from_config(self) -> None:
        config = self._config
        self._syncing = True
        if self._reader_kind == "xlsx":
            sheet_name = str(config.get("sheet_name", ""))
            if self._preview is not None:
                self.sheet_combo.clear()
                for name in self._preview.sheet_names:
                    self.sheet_combo.addItem(name, name)
            _combo_value_set(self.sheet_combo, sheet_name)
        elif self._reader_kind == "delimited":
            delimiter = str(config.get("delimiter", "auto"))
            delimiter_index = self.delimiter_combo.findData(delimiter)
            if delimiter_index < 0:
                delimiter_index = self.delimiter_combo.findData("custom")
                self.custom_delimiter_edit.setText(delimiter)
            self.delimiter_combo.setCurrentIndex(max(0, delimiter_index))
            self.custom_delimiter_edit.setText(
                str(config.get("custom_delimiter", self.custom_delimiter_edit.text()))
            )
            _combo_value_set(self.encoding_combo, str(config.get("encoding", "auto")))
        header = config.get("header_row", 1)
        self.header_enabled.setChecked(header not in (None, "", 0, "0"))
        self.header_spin.setValue(int(header or 1))
        self.header_spin.setEnabled(self.header_enabled.isChecked())
        default_start = self.header_spin.value() + 1 if self.header_enabled.isChecked() else 1
        self.data_start_spin.setValue(int(config.get("data_start_row", default_start)))
        data_end = config.get("data_end_row")
        self.data_end_enabled.setChecked(data_end not in (None, "", 0, "0"))
        self.data_end_spin.setValue(int(data_end or self.data_start_spin.value()))
        self.data_end_spin.setEnabled(self.data_end_enabled.isChecked())
        _combo_value_set(
            self.invalid_policy_combo,
            str(config.get("invalid_row_policy", "preserve")),
        )
        time = config.get("time", {})
        if not isinstance(time, Mapping):
            time = {}
        _combo_value_set(self.time_mode_combo, str(time.get("mode", "none")))
        _combo_value_set(self.time_unit_combo, str(time.get("unit", "s")))
        if time.get("sample_rate_hz") not in (None, ""):
            self.sample_rate_spin.setValue(float(time["sample_rate_hz"]))
        if time.get("sample_period_s") not in (None, ""):
            self.sample_period_spin.setValue(float(time["sample_period_s"]))
        self._time_columns_refresh(time.get("column"))
        self._syncing = False
        self._reader_controls_refresh()
        self._time_controls_refresh()
        if self._preview is not None:
            self._mapping_rebuild()

    def _preview_populate(self) -> None:
        preview = self._preview
        if preview is None:
            return
        self.preview_table.clear()
        self.preview_table.setColumnCount(preview.column_count)
        self.preview_table.setRowCount(len(preview.rows))
        self.preview_table.setHorizontalHeaderLabels(
            [
                f"{Tabular_ColumnLabel(column)}\n{preview.headers[column]}".strip()
                for column in range(preview.column_count)
            ]
        )
        self.preview_table.setVerticalHeaderLabels(
            [str(row_number) for row_number in preview.row_numbers]
        )
        for row, values in enumerate(preview.rows):
            for column, value in enumerate(values):
                self.preview_table.setItem(row, column, QTableWidgetItem(value))
        self.preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _mapping_rebuild(self) -> None:
        preview = self._preview
        if preview is None:
            return
        payloads = self._config.get("columns", [])
        mappings = {
            int(item["column"]): dict(item)
            for item in payloads
            if isinstance(item, Mapping) and "column" in item
        }
        width = max(preview.column_count, max(mappings, default=-1) + 1)
        self._syncing = True
        self.mapping_table.setRowCount(width)
        self._mapping_rows.clear()
        for column in range(width):
            header = preview.headers[column] if column < preview.column_count else ""
            mapping = mappings.get(
                column,
                {
                    "column": column,
                    "usage": "ignore",
                    "expected_header": header or None,
                },
            )
            expected_header = mapping.get("expected_header", mapping.get("header_hint"))
            column_item = QTableWidgetItem(Tabular_ColumnLabel(column))
            column_item.setFlags(column_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            header_item = QTableWidgetItem(header)
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if expected_header and expected_header != header:
                header_item.setText(f"⚠ {header or '—'}")
                header_item.setBackground(QColor("#fff3cd"))
                header_item.setForeground(QColor("#111827"))
                header_item.setToolTip(
                    self._translations.translate(
                        "tabular.header_mismatch_tooltip",
                        expected=str(expected_header),
                        actual=header,
                    )
                )
            elif column >= preview.column_count:
                header_item.setText("⚠ —")
                header_item.setBackground(QColor("#f8d7da"))
                header_item.setForeground(QColor("#111827"))
                header_item.setToolTip(
                    self._translations.translate("tabular.missing_column_tooltip")
                )
            elif column not in mappings and (
                header or any(row[column].strip() for row in preview.rows)
            ):
                header_item.setBackground(QColor("#fff3cd"))
                header_item.setForeground(QColor("#111827"))
                header_item.setToolTip(
                    self._translations.translate("tabular.new_column_tooltip")
                )
            self.mapping_table.setItem(column, 0, column_item)
            self.mapping_table.setItem(column, 1, header_item)

            usage = StandardComboBox()
            for value in TabularColumnUsage:
                usage.addItem(
                    self._translations.translate(f"tabular.usage.{value.value}"),
                    value.value,
                )
            _combo_value_set(usage, str(mapping.get("usage", "ignore")))
            display_name = QLineEdit(str(mapping.get("display_name", header)))
            channel_id = QLineEdit(
                str(mapping.get("channel_id", f"column_{Tabular_ColumnLabel(column).lower()}"))
            )
            quantity = StandardComboBox()
            quantity.setEditable(True)
            for value in Quantity_KnownIds():
                quantity.addItem(value, value)
            _combo_text_set(quantity, str(mapping.get("quantity", "custom")))
            role = StandardComboBox()
            role.setEditable(True)
            for value in _SEMANTIC_ROLES:
                role.addItem(value or "—", value)
            _combo_text_set(role, str(mapping.get("role") or ""))
            unit = StandardComboBox()
            unit.setEditable(True)
            unit.addItem("", "")
            for value in Unit_KnownSymbols():
                unit.addItem(value, value)
            _combo_text_set(unit, str(mapping.get("unit") or ""))
            for table_column, widget in enumerate(
                (usage, display_name, channel_id, quantity, role, unit), start=2
            ):
                self.mapping_table.setCellWidget(column, table_column, widget)
            row_state = {
                "column": column,
                "header": header,
                "expected_header": expected_header,
                "usage": usage,
                "display_name": display_name,
                "channel_id": channel_id,
                "quantity": quantity,
                "role": role,
                "unit": unit,
            }
            self._mapping_rows.append(row_state)
            usage.currentIndexChanged.connect(
                lambda _index, row=column: self._mapping_row_changed(row)
            )
            for editor in (display_name, channel_id):
                editor.textChanged.connect(
                    lambda _value, row=column: self._mapping_row_changed(row)
                )
            for editor in (quantity, role, unit):
                editor.currentTextChanged.connect(
                    lambda _value, row=column: self._mapping_row_changed(row)
                )
            self._mapping_row_enabled_refresh(column)
        selected_time = self._config.get("time", {})
        selected_column = (
            selected_time.get("column") if isinstance(selected_time, Mapping) else None
        )
        self._time_columns_refresh(selected_column)
        self._syncing = False
        self._quick_mapping_rebuild()

    def _quick_type_text(self, type_id: str) -> str:
        if type_id == "time":
            return self._translations.translate("mapping.type.time")
        if type_id == "other":
            return self._translations.translate("mapping.type.other")
        capability = self._capability_registry.get(type_id)
        return self._translations.translate(
            capability.display_key,
            capability.capability_id,
        )

    def _quick_mapping_rebuild(self) -> None:
        if self._preview is None or self._syncing:
            return
        self._syncing = True
        self.quick_table.setRowCount(len(self._mapping_rows))
        self._quick_rows.clear()
        for row, state in enumerate(self._mapping_rows):
            column_item = QTableWidgetItem(Tabular_ColumnLabel(row))
            column_item.setFlags(column_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            header_item = QTableWidgetItem(str(state["header"]) or "—")
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.quick_table.setItem(row, 0, column_item)
            self.quick_table.setItem(row, 1, header_item)

            usage = str(state["usage"].currentData() or "ignore")
            if usage == TabularColumnUsage.TIME.value:
                type_id = "time"
            elif usage == TabularColumnUsage.DATA.value:
                type_id = self._capability_registry.mapping_type(
                    quantity=state["quantity"].currentText().strip(),
                    semantic_role=state["role"].currentText().strip() or None,
                ) or "other"
            else:
                type_id = "other"
            type_combo = StandardComboBox()
            for candidate_id in self.simple_type_ids():
                type_combo.addItem(
                    self._quick_type_text(candidate_id),
                    candidate_id,
                )
            _combo_value_set(type_combo, type_id)
            unit_combo = StandardComboBox()
            unit_combo.setEditable(True)
            unit_combo.addItem("", "")
            for symbol in Unit_KnownSymbols():
                unit_combo.addItem(symbol, symbol)
            current_unit = (
                str(self.time_unit_combo.currentData() or "s")
                if type_id == "time"
                else state["unit"].currentText().strip()
            )
            _combo_text_set(unit_combo, current_unit)
            self.quick_table.setCellWidget(row, 2, type_combo)
            self.quick_table.setCellWidget(row, 3, unit_combo)
            quick_state = {
                "type": type_combo,
                "unit": unit_combo,
            }
            self._quick_rows.append(quick_state)
            type_combo.currentIndexChanged.connect(
                lambda _index, selected_row=row: self._quick_type_changed(selected_row)
            )
            unit_combo.currentTextChanged.connect(
                lambda _value, selected_row=row: self._quick_unit_changed(selected_row)
            )
        self._syncing = False
        self._quick_readiness_refresh()

    def _quick_type_changed(self, row: int) -> None:
        if self._syncing or row >= len(self._mapping_rows):
            return
        type_id = str(self._quick_rows[row]["type"].currentData() or "other")
        state = self._mapping_rows[row]
        self._syncing = True
        if type_id == "time":
            _combo_value_set(state["usage"], TabularColumnUsage.TIME.value)
            _combo_value_set(self.time_mode_combo, TabularTimeMode.COLUMN.value)
            _combo_value_set(self.time_column_combo, row)
            _combo_text_set(
                self.time_unit_combo,
                self._quick_rows[row]["unit"].currentText().strip() or "s",
            )
        else:
            _combo_value_set(state["usage"], TabularColumnUsage.DATA.value)
            channel_id = state["channel_id"].text().strip()
            if not channel_id:
                channel_id = f"column_{Tabular_ColumnLabel(row).lower()}"
                state["channel_id"].setText(channel_id)
            if not state["display_name"].text().strip():
                state["display_name"].setText(str(state["header"]) or channel_id)
            if type_id == "other":
                known_type = self._capability_registry.mapping_type(
                    quantity=state["quantity"].currentText().strip(),
                    semantic_role=state["role"].currentText().strip() or None,
                )
                if known_type is not None or not state["quantity"].currentText().strip():
                    _combo_text_set(state["quantity"], f"custom.{channel_id}")
                _combo_text_set(state["role"], "auxiliary")
            else:
                capability = self._capability_registry.get(type_id)
                _combo_text_set(state["quantity"], capability.quantity)
                _combo_text_set(state["role"], capability.semantic_role)
            _combo_text_set(
                state["unit"],
                self._quick_rows[row]["unit"].currentText().strip(),
            )
        self._mapping_row_enabled_refresh(row)
        self._syncing = False
        self._quick_readiness_refresh()
        self.mapping_changed.emit()

    def _quick_unit_changed(self, row: int) -> None:
        if self._syncing or row >= len(self._mapping_rows):
            return
        unit = self._quick_rows[row]["unit"].currentText().strip()
        type_id = str(self._quick_rows[row]["type"].currentData() or "other")
        self._syncing = True
        if type_id == "time":
            _combo_text_set(self.time_unit_combo, unit or "s")
        else:
            _combo_text_set(self._mapping_rows[row]["unit"], unit)
        self._syncing = False
        self.mapping_changed.emit()

    def _quick_readiness_refresh(self) -> None:
        type_ids = tuple(
            str(item["type"].currentData() or "other") for item in self._quick_rows
        )
        time_count = type_ids.count("time")
        data_count = len(type_ids) - time_count
        generated_time = self.time_mode_combo.currentData() in {
            TabularTimeMode.SAMPLE_RATE.value,
            TabularTimeMode.SAMPLE_PERIOD.value,
        }
        if (time_count == 1 or (time_count == 0 and generated_time)) and data_count >= 1:
            key = "tabular.quick_ready"
        elif time_count > 1:
            key = "tabular.quick_multiple_time"
        else:
            key = "tabular.quick_missing_time"
        self.quick_status.setText(self._translations.translate(key))

    def _mapping_row_changed(self, row: int) -> None:
        if row >= len(self._mapping_rows):
            return
        self._mapping_row_enabled_refresh(row)
        if self._syncing:
            return
        state = self._mapping_rows[row]
        state["expected_header"] = state["header"] or None
        if state["usage"].currentData() == TabularColumnUsage.TIME.value:
            _combo_value_set(self.time_mode_combo, TabularTimeMode.COLUMN.value)
            self._time_columns_refresh(row)
        self.mapping_changed.emit()
        self._quick_mapping_rebuild()

    def _mapping_row_enabled_refresh(self, row: int) -> None:
        state = self._mapping_rows[row]
        is_data = state["usage"].currentData() == TabularColumnUsage.DATA.value
        for key in ("display_name", "channel_id", "quantity", "role", "unit"):
            state[key].setEnabled(is_data)

    def _time_columns_refresh(self, selected: Any = None) -> None:
        selected_value = (
            int(selected)
            if selected not in (None, "")
            else self.time_column_combo.currentData()
        )
        self.time_column_combo.blockSignals(True)
        self.time_column_combo.clear()
        width = self._preview.column_count if self._preview is not None else 0
        for column in range(width):
            header = self._preview.headers[column] if self._preview is not None else ""
            label = (
                f"{Tabular_ColumnLabel(column)} · {header}"
                if header
                else Tabular_ColumnLabel(column)
            )
            self.time_column_combo.addItem(label, column)
        index = self.time_column_combo.findData(selected_value)
        self.time_column_combo.setCurrentIndex(max(0, index))
        self.time_column_combo.blockSignals(False)

    def _time_column_changed(self, _index: int) -> None:
        if self._syncing or self.time_mode_combo.currentData() != TabularTimeMode.COLUMN.value:
            return
        selected = self.time_column_combo.currentData()
        for row, state in enumerate(self._mapping_rows):
            usage = state["usage"]
            if row == selected:
                _combo_value_set(usage, TabularColumnUsage.TIME.value)
            elif usage.currentData() == TabularColumnUsage.TIME.value:
                _combo_value_set(usage, TabularColumnUsage.IGNORE.value)
        self.mapping_changed.emit()

    def _time_controls_refresh(self, _index: int | None = None) -> None:
        mode = self.time_mode_combo.currentData()
        column_mode = mode == TabularTimeMode.COLUMN.value
        rate_mode = mode == TabularTimeMode.SAMPLE_RATE.value
        period_mode = mode == TabularTimeMode.SAMPLE_PERIOD.value
        column_widgets = (
            self.time_column_label,
            self.time_column_combo,
            self.time_unit_label,
            self.time_unit_combo,
        )
        for widget in column_widgets:
            widget.setVisible(column_mode)
        self.sample_rate_label.setVisible(rate_mode)
        self.sample_rate_spin.setVisible(rate_mode)
        self.sample_period_label.setVisible(period_mode)
        self.sample_period_spin.setVisible(period_mode)
        if not self._syncing and column_mode:
            self._time_column_changed(self.time_column_combo.currentIndex())

    def config(self) -> dict[str, Any]:
        config = dict(self._config)
        if self._reader_kind == "xlsx":
            config["sheet_name"] = str(self.sheet_combo.currentData() or "")
        elif self._reader_kind == "delimited":
            delimiter = str(self.delimiter_combo.currentData() or "auto")
            config["delimiter"] = delimiter
            config["custom_delimiter"] = self.custom_delimiter_edit.text()
            config["encoding"] = str(self.encoding_combo.currentData() or "auto")
        config["header_row"] = (
            self.header_spin.value() if self.header_enabled.isChecked() else None
        )
        config["data_start_row"] = self.data_start_spin.value()
        config["data_end_row"] = (
            self.data_end_spin.value() if self.data_end_enabled.isChecked() else None
        )
        config["invalid_row_policy"] = str(
            self.invalid_policy_combo.currentData() or "preserve"
        )
        mode = str(self.time_mode_combo.currentData() or "none")
        time: dict[str, Any] = {"mode": mode}
        if mode == TabularTimeMode.COLUMN.value:
            time.update(
                {
                    "column": self.time_column_combo.currentData(),
                    "unit": str(self.time_unit_combo.currentData() or "s"),
                }
            )
        elif mode == TabularTimeMode.SAMPLE_RATE.value:
            time["sample_rate_hz"] = self.sample_rate_spin.value()
        elif mode == TabularTimeMode.SAMPLE_PERIOD.value:
            time["sample_period_s"] = self.sample_period_spin.value()
        config["time"] = time
        mappings: list[dict[str, Any]] = []
        selected_time_column = time.get("column") if mode == "column" else None
        mapped_time_columns = tuple(
            row
            for row, state in enumerate(self._mapping_rows)
            if state["usage"].currentData() == TabularColumnUsage.TIME.value
        )
        if mapped_time_columns:
            mode = TabularTimeMode.COLUMN.value
            selected_time_column = mapped_time_columns[0]
            time = {
                "mode": mode,
                "column": selected_time_column,
                "unit": str(self.time_unit_combo.currentData() or "s"),
            }
            config["time"] = time
        for row, state in enumerate(self._mapping_rows):
            usage = str(state["usage"].currentData() or "ignore")
            if row in mapped_time_columns:
                usage = "time"
            mapping: dict[str, Any] = {
                "column": row,
                "usage": usage,
                "expected_header": state.get("expected_header"),
            }
            if usage == "time":
                mapping["unit"] = str(self.time_unit_combo.currentData() or "s")
            elif usage == "data":
                mapping.update(
                    {
                        "display_name": state["display_name"].text().strip(),
                        "channel_id": state["channel_id"].text().strip(),
                        "quantity": state["quantity"].currentText().strip(),
                        "role": state["role"].currentText().strip() or None,
                        "unit": state["unit"].currentText().strip() or None,
                    }
                )
            mappings.append(mapping)
        if self._mapping_rows:
            config["columns"] = mappings
        return config


def _combo_value_set(combo: StandardComboBox, value: Any) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


def _combo_text_set(combo: StandardComboBox, value: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)
    elif combo.isEditable():
        combo.setEditText(value)


def _mapping_copy(config: Mapping[str, Any]) -> dict[str, Any]:
    import json

    return json.loads(json.dumps(dict(config), ensure_ascii=False))
