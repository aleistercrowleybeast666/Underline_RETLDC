from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
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
from underline_retldc.core.units import Quantity_Dimension, Unit_IsPhysicalForQuantity
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
        self._project_mass: float | None = None
        self._base_config: SourceAnalysisConfig | None = None
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
        self._form = form
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
        self.parameter_scroll.setWidget(editor)
        self.parameter_scroll.hide()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        selector = QHBoxLayout()
        selector.addWidget(self.source_label)
        selector.addWidget(self.source_combo, 1)
        layout.addLayout(selector)
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
        ):
            label.setText(t(key))
            label.setWordWrap(True)
        self.interval_combo.setItemText(0, t("source_analysis.full_record"))
        self.interval_combo.setItemText(1, t("source_analysis.custom"))
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
        *,
        project_mass: float | None = None,
    ) -> None:
        selected = self.source_id()
        self._project, self._states, self._processors = project, states, processors
        self._processed_reference = processed_reference
        self._project_mass = project_mass
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

    def select_reference(self, reference: ChannelReference | None) -> None:
        """Use the existing theory-curve selection without changing experimental bindings."""
        if reference is None or not any(item.reference == reference for item in self._inputs):
            return
        active = self.source_combo.currentIndex() == 1
        self._syncing = True
        self.record_combo.setCurrentIndex(self.record_combo.findData(reference.source_id))
        self.source_combo.setItemData(1, reference.source_id)
        self._syncing = False
        if not active:
            return
        self._editor_populate()
        if self.workspace_id != "temperature":
            was_blocked = self.channel_combo.blockSignals(True)
            self.channel_combo.setCurrentIndex(self.channel_combo.findData(reference.stable_id))
            self.channel_combo.blockSignals(was_blocked)
        self.view_changed.emit()

    def unavailable_reason(self) -> str:
        if self.source_id() is None:
            return ""
        selected = {reference.stable_id for reference in self.config().channels}
        inputs = tuple(item for item in self._available() if item.reference.stable_id in selected)
        if not inputs:
            return self._translations.translate("source_analysis.no_input")
        for item in inputs:
            channel = item.dataset.channel(item.channel_id)
            finite = np.isfinite(item.dataset.project_time) & np.isfinite(channel.values)
            if (np.count_nonzero(finite) < 2
                    or not Unit_IsPhysicalForQuantity(channel.quantity, channel.data_unit)):
                return self._translations.translate("source_analysis.no_input")
        return ""

    def _editor_populate(self) -> None:
        self._syncing = True
        self.source_combo.setToolTip(self.source_combo.currentText())
        available = self._available()
        state = self.selected_state()
        config = state.config if state else None
        self._base_config = config
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
        self._syncing = False
        self._visibility_refresh()
        self._notice_refresh()

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
        base = self._base_config or SourceAnalysisConfig(
            source_id, self.workspace_id, mass_source="project",
        )
        return replace(
            base,
            channels=channels,
            interval=(self.start_spin.value(), self.end_spin.value())
            if self.interval_combo.currentData() == "custom" else None,
            propellant_mass_kg=(self._project_mass if base.mass_source == "project"
                                else base.propellant_mass_kg),
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
        self._form.setRowVisible(self.record_combo, active and self.record_combo.count() > 1)
        self._form.setRowVisible(self.channel_list, self.workspace_id == "temperature")
        self.parameter_scroll.hide()
        custom = self.interval_combo.currentData() == "custom"
        self._form.setRowVisible(self.start_spin, custom)
        self._form.setRowVisible(self.end_spin, custom)
        self._form.activate()
        self.parameter_scroll.setMaximumHeight(min(200, self._form.sizeHint().height() + 2))
        self.updateGeometry()

    def _notice_refresh(self) -> None:
        state = self.selected_state()
        error = state.error if state else ""
        message = (
            self._translations.translate("source_analysis.failed", error=error) if error else ""
        )
        message = message or self.unavailable_reason()
        self.notice.setText(message)
        self.notice.setVisible(bool(message))
