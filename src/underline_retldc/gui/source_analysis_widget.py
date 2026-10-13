from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.app.source_analysis import SourceAnalysisState
from underline_retldc.core.project_data import ChannelReference, ProjectData, SourceKind
from underline_retldc.core.source_analysis import SourceAnalysisConfig, SourceAnalysisInput
from underline_retldc.core.units import Quantity_Dimension
from underline_retldc.gui.schema_form import SchemaForm
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class SourceAnalysisWidget(QWidget):
    """Source selection and parameters in the existing result-panel footprint."""

    view_changed = Signal()
    config_changed = Signal(object)

    def __init__(
        self,
        translations: TranslationService,
        workspace_id: str,
        dimension: str | None,
    ) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._translations = translations
        self.workspace_id = workspace_id
        self.dimension = dimension
        self._syncing = False
        self._project = ProjectData()
        self._inputs: tuple[SourceAnalysisInput, ...] = ()
        self._states: Mapping[str, SourceAnalysisState] = {}
        self._processors: tuple[Any, ...] = ()
        self._processed_reference: ChannelReference | None = None
        self.source_label = QLabel()
        self.source_combo = StandardComboBox()
        self.source_combo.currentIndexChanged.connect(self._source_selected)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.parameter_scroll = QScrollArea()
        self.parameter_scroll.setWidgetResizable(True)
        self.parameter_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.parameter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.parameter_scroll.setMaximumHeight(200)
        editor = QWidget()
        form = QFormLayout(editor)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.record_label = QLabel()
        self.record_combo = StandardComboBox()
        self.record_combo.currentIndexChanged.connect(self._record_selected)
        form.addRow(self.record_label, self.record_combo)
        self.channel_label = QLabel()
        self.channel_combo = StandardComboBox()
        self.channel_combo.currentIndexChanged.connect(self._changed)
        self.channel_list = QListWidget()
        self.channel_list.setMaximumHeight(90)
        self.channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_list.itemChanged.connect(self._changed)
        form.addRow(self.channel_label, self.channel_combo)
        form.addRow(self.channel_list)
        self.interval_label = QLabel()
        self.interval_combo = StandardComboBox()
        self.interval_combo.addItem("", "full_record")
        self.interval_combo.addItem("", "custom")
        self.interval_combo.currentIndexChanged.connect(self._changed)
        form.addRow(self.interval_label, self.interval_combo)
        self.start_label, self.end_label = QLabel(), QLabel()
        self.start_spin, self.end_spin = self._time_spin(), self._time_spin()
        form.addRow(self.start_label, self.start_spin)
        form.addRow(self.end_label, self.end_spin)
        self.mass_known = QCheckBox()
        self.mass_spin = QDoubleSpinBox()
        self.mass_spin.setDecimals(9)
        self.mass_spin.setRange(-1.0e12, 1.0e12)
        self.mass_spin.setSuffix(" kg")
        self.mass_known.toggled.connect(self._changed)
        self.mass_spin.valueChanged.connect(self._changed)
        form.addRow(self.mass_known)
        form.addRow(self.mass_spin)
        self.stage_label = QLabel()
        self.stage_combo = StandardComboBox()
        self.stage_combo.addItem("", "calibrated")
        self.stage_combo.addItem("", "project_processed")
        self.stage_combo.currentIndexChanged.connect(self._changed)
        form.addRow(self.stage_label, self.stage_combo)
        self.polarity_label = QLabel()
        self.polarity_combo = StandardComboBox()
        self.polarity_combo.addItem("+1", 1)
        self.polarity_combo.addItem("−1", -1)
        self.polarity_combo.currentIndexChanged.connect(self._changed)
        form.addRow(self.polarity_label, self.polarity_combo)
        self.processor_label = QLabel()
        self.processor_combo = StandardComboBox()
        self.processor_combo.currentIndexChanged.connect(self._processor_changed)
        self.processor_form = SchemaForm(translations)
        self.processor_form.value_changed.connect(self._changed)
        form.addRow(self.processor_label, self.processor_combo)
        form.addRow(self.processor_form)
        self.baseline_checks: dict[str, QCheckBox] = {}
        self.baseline_spins: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]] = {}
        for key in ("pre", "post"):
            check = QCheckBox()
            check.toggled.connect(self._changed)
            spins = self._time_spin(), self._time_spin()
            self.baseline_checks[key] = check
            self.baseline_spins[key] = spins
            form.addRow(check)
            for spin in spins:
                form.addRow(spin)
        self.parameter_scroll.setWidget(editor)
        self.parameter_scroll.hide()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.source_label)
        layout.addWidget(self.source_combo)
        layout.addWidget(self.parameter_scroll)
        layout.addWidget(self.notice)
        self.retranslate()

    def _time_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(9)
        spin.setRange(-1.0e12, 1.0e12)
        spin.setSuffix(" s")
        spin.valueChanged.connect(self._changed)
        return spin

    def retranslate(self) -> None:
        t = self._translations.translate
        for label, key in (
            (self.source_label, "source_analysis.source"),
            (self.record_label, "source_analysis.theory_file"),
            (self.channel_label, "source_analysis.channels"),
            (self.interval_label, "source_analysis.interval"),
            (self.start_label, "source_analysis.start"),
            (self.end_label, "source_analysis.end"),
            (self.stage_label, "source_analysis.input"),
            (self.polarity_label, "process.polarity"),
            (self.processor_label, "process.thrust_correction"),
        ):
            label.setText(t(key))
            label.setWordWrap(True)
        self.mass_known.setText(t("source_analysis.mass_known"))
        self.interval_combo.setItemText(0, t("source_analysis.full_record"))
        self.interval_combo.setItemText(1, t("source_analysis.custom"))
        self.stage_combo.setItemText(0, t("source_analysis.calibrated"))
        self.stage_combo.setItemText(1, t("source_analysis.project_processed"))
        for key, check in self.baseline_checks.items():
            check.setText(t(f"source_analysis.{key}"))
        self.processor_form.retranslate()
        if self.source_combo.count():
            self.source_combo.setItemText(0, t("source_analysis.experimental"))
            self.source_combo.setItemText(1, t("source_analysis.theoretical"))
        self._notice_refresh()

    def source_id(self) -> str | None:
        return self.source_combo.currentData()

    def _record_selected(self) -> None:
        if self._syncing:
            return
        self.source_combo.setItemData(1, self.record_combo.currentData())
        self._editor_populate()
        self.view_changed.emit()

    def selected_state(self) -> SourceAnalysisState | None:
        source_id = self.source_id()
        return self._states.get(f"{source_id}/{self.workspace_id}") if source_id else None

    def _available(self) -> tuple[SourceAnalysisInput, ...]:
        return tuple(item for item in self._inputs if item.reference.source_id == self.source_id())

    def set_context(
        self,
        project: ProjectData,
        inputs: tuple[SourceAnalysisInput, ...],
        states: Mapping[str, SourceAnalysisState],
        processors: tuple[Any, ...],
        processed_reference: ChannelReference | None,
    ) -> None:
        selected = self.source_id()
        self._project, self._states, self._processors = project, states, processors
        self._processed_reference = processed_reference
        self._inputs = tuple(
            item
            for item in inputs
            if self.dimension is None
            or Quantity_Dimension(item.dataset.channel(item.channel_id).quantity) == self.dimension
        )
        self._syncing = True
        previous_theory = self.source_combo.itemData(1)
        self.source_combo.clear()
        self.source_combo.addItem(
            self._translations.translate("source_analysis.experimental"), None,
        )
        self.record_combo.clear()
        source_ids = {item.reference.source_id for item in self._inputs}
        for source in project.sources.values():
            if source.id in source_ids and source.source_kind == SourceKind.THEORETICAL:
                self.record_combo.addItem(source.path.name, source.id)
        self.record_combo.setCurrentIndex(max(0, self.record_combo.findData(previous_theory)))
        self.source_combo.addItem(
            self._translations.translate("source_analysis.theoretical"),
            self.record_combo.currentData(),
        )
        self.source_combo.model().item(1).setEnabled(self.record_combo.count() > 0)
        index = self.source_combo.findData(selected)
        self.source_combo.setCurrentIndex(max(0, index))
        self._syncing = False
        self._editor_populate()

    def _source_selected(self) -> None:
        if self._syncing:
            return
        self._editor_populate()
        self.view_changed.emit()

    def _editor_populate(self) -> None:
        self._syncing = True
        self.source_combo.setToolTip(self.source_combo.currentText())
        available = self._available()
        state = self.selected_state()
        config = state.config if state else None
        selected_ids = {item.stable_id for item in config.channels} if config else set()
        if config is None and (len(available) == 1 or self.workspace_id == "temperature"):
            selected_ids = {item.reference.stable_id for item in available}
        self.channel_combo.clear()
        self.channel_combo.addItem(self._translations.translate("primary_channels.none"), None)
        self.channel_list.clear()
        for item in available:
            stable_id = item.reference.stable_id
            self.channel_combo.addItem(item.label, stable_id)
            check = QListWidgetItem(item.label)
            check.setData(Qt.ItemDataRole.UserRole, stable_id)
            check.setFlags(check.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(
                Qt.CheckState.Checked if stable_id in selected_ids else Qt.CheckState.Unchecked
            )
            self.channel_list.addItem(check)
        index = self.channel_combo.findData(next(iter(selected_ids), None))
        self.channel_combo.setCurrentIndex(max(0, index))
        self.channel_list.setVisible(self.workspace_id == "temperature")
        self.channel_combo.setVisible(self.workspace_id != "temperature")
        times = [item.dataset.project_time for item in available]
        finite = [time[np.isfinite(time)] for time in times if np.any(np.isfinite(time))]
        bounds = (
            (
                min(float(np.min(time)) for time in finite),
                max(float(np.max(time)) for time in finite),
            )
            if finite
            else (0, 0)
        )
        interval = config.interval if config else None
        self.interval_combo.setCurrentIndex(1 if interval is not None else 0)
        self.start_spin.setValue((interval or bounds)[0])
        self.end_spin.setValue((interval or bounds)[1])
        self.mass_known.setChecked(config is not None and config.propellant_mass_kg is not None)
        self.mass_spin.setValue(config.propellant_mass_kg or 0 if config else 0)
        self.stage_combo.setCurrentIndex(
            1 if config and config.input_stage == "project_processed" else 0
        )
        self.stage_combo.model().item(1).setEnabled(
            self._processed_reference is not None
            and self._processed_reference.source_id == self.source_id()
        )
        self.polarity_combo.setCurrentIndex(1 if config and config.polarity == -1 else 0)
        self.processor_combo.clear()
        self.processor_combo.addItem(self._translations.translate("process.processor_none"), None)
        for processor in self._processors:
            descriptor = processor.descriptor
            self.processor_combo.addItem(
                self._translations.translate(descriptor.translation_key or "", descriptor.name),
                descriptor.plugin_id,
            )
        selected_processor = config.processor["id"] if config and config.processor else None
        self.processor_combo.setCurrentIndex(
            max(0, self.processor_combo.findData(selected_processor))
        )
        self._processor_schema()
        if config and config.processor:
            self.processor_form.set_values(config.processor["config"])
        for key in ("pre", "post"):
            interval = getattr(config, key) if config else None
            self.baseline_checks[key].setChecked(interval is not None)
            for spin, value in zip(self.baseline_spins[key], interval or bounds, strict=True):
                spin.setValue(value)
        self._syncing = False
        self._visibility_refresh()
        self._notice_refresh()

    def _processor(self) -> Any | None:
        return next(
            (
                item
                for item in self._processors
                if item.descriptor.plugin_id == self.processor_combo.currentData()
            ),
            None,
        )

    def _processor_schema(self) -> None:
        processor = self._processor()
        self.processor_form.set_schema(
            processor.config_schema() if processor else {"properties": {}}
        )

    def _processor_changed(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        self._processor_schema()
        self._syncing = False
        self._changed()

    def config(self) -> SourceAnalysisConfig:
        source_id = self.source_id()
        if source_id is None:
            raise ValueError("Select a Source for independent calculation")
        if self.workspace_id == "temperature":
            ids = {
                self.channel_list.item(index).data(Qt.ItemDataRole.UserRole)
                for index in range(self.channel_list.count())
                if self.channel_list.item(index).checkState() == Qt.CheckState.Checked
            }
        else:
            ids = {self.channel_combo.currentData()}
        channels = tuple(
            item.reference for item in self._available() if item.reference.stable_id in ids
        )
        processor = self._processor()
        processor_reference = None
        if processor is not None:
            descriptor = processor.descriptor
            processor_reference = {
                "id": descriptor.plugin_id,
                "version": descriptor.version,
                "api_version": descriptor.api_version,
                "config": self.processor_form.values(),
            }
        return SourceAnalysisConfig(
            source_id,
            self.workspace_id,
            channels,
            (self.start_spin.value(), self.end_spin.value())
            if self.interval_combo.currentData() == "custom"
            else None,
            self.mass_spin.value() if self.mass_known.isChecked() else None,
            str(self.stage_combo.currentData()),
            int(self.polarity_combo.currentData()),
            processor_reference,
            (self.baseline_spins["pre"][0].value(), self.baseline_spins["pre"][1].value())
            if self.baseline_checks["pre"].isChecked()
            else None,
            (self.baseline_spins["post"][0].value(), self.baseline_spins["post"][1].value())
            if self.baseline_checks["post"].isChecked()
            else None,
        )

    def _changed(self, *_args: object) -> None:
        if self._syncing:
            return
        self._visibility_refresh()
        if self.source_id() is not None:
            self.config_changed.emit(self.config())
        self.view_changed.emit()

    def _visibility_refresh(self) -> None:
        active = self.source_id() is not None
        self.record_label.setVisible(active and self.record_combo.count() > 1)
        self.record_combo.setVisible(active and self.record_combo.count() > 1)
        self.parameter_scroll.setVisible(active)
        self.updateGeometry()
        for control in (self.start_spin, self.end_spin):
            control.setEnabled(self.interval_combo.currentData() == "custom")
        force = self.workspace_id == "thrust_analysis"
        for control in (self.mass_known, self.mass_spin, self.stage_label, self.stage_combo):
            control.setVisible(force)
        self.mass_spin.setEnabled(self.mass_known.isChecked())
        own_pipeline = force and self.stage_combo.currentData() != "project_processed"
        for control in (
            self.polarity_label,
            self.polarity_combo,
            self.processor_label,
            self.processor_combo,
        ):
            control.setVisible(own_pipeline)
        has_processor = own_pipeline and self._processor() is not None
        self.processor_form.setVisible(has_processor)
        for key, check in self.baseline_checks.items():
            check.setVisible(has_processor)
            for spin in self.baseline_spins[key]:
                spin.setVisible(has_processor)
                spin.setEnabled(check.isChecked())
        self.notice.setVisible(active)

    def _notice_refresh(self) -> None:
        state = self.selected_state()
        key = "source_analysis.ready" if state and state.completed else "source_analysis.pending"
        self.notice.setText(
            self._translations.translate("source_analysis.failed", error=state.error)
            if state and state.error else self._translations.translate(key)
        )
