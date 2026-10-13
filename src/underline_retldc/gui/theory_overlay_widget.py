from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.channel import Channel
from underline_retldc.core.curve_display import CurveDisplay_IsCompatible, DisplayCurve
from underline_retldc.core.project_data import ProjectData, Source, SourceKind
from underline_retldc.core.units import Quantity_Dimension, UnitDisplayMode
from underline_retldc.gui.analysis_widgets import AnalysisPlotWidget
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class TheoryOverlayWidget(QWidget):
    """Shared view controls; emits source display state, never workflow input changes."""

    display_changed = Signal(str, object)
    align_requested = Signal(str)
    view_changed = Signal()

    def __init__(self, translations: TranslationService, dimension: str | None) -> None:
        super().__init__()
        self._translations = translations
        self._dimension = dimension
        self._project = ProjectData()
        self._curves: tuple[DisplayCurve, ...] = ()
        self._compatible: set[str] = set()
        self._notice_key = ""
        self._notice_values: dict[str, object] = {}
        self.title_label = QLabel()
        self.curve_list = QListWidget()
        self.curve_list.setMaximumHeight(120)
        self.curve_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.curve_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.curve_list.itemChanged.connect(self._visibility_changed)
        self.curve_combo = StandardComboBox()
        self.curve_combo.currentIndexChanged.connect(self._selection_changed)
        self.shift_spin = QDoubleSpinBox()
        self.shift_spin.setDecimals(9)
        self.shift_spin.setRange(-1.0e100, 1.0e100)
        self.shift_spin.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.shift_spin.setMinimumWidth(90)
        self.shift_spin.valueChanged.connect(self._shift_changed)
        self.shift_slider = QSlider(Qt.Orientation.Horizontal)
        self.shift_slider.setRange(-10000, 10000)
        self._slider_span = 10.0
        self.shift_slider.valueChanged.connect(self._slider_changed)
        self.align_button = QPushButton()
        self.align_button.clicked.connect(self._align_start)
        self.reset_button = QPushButton()
        self.reset_button.clicked.connect(self._reset)
        for button in (self.align_button, self.reset_button):
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.align_label = QLabel()
        self.shift_label = QLabel()
        for label in (self.title_label, self.align_label, self.shift_label):
            label.setWordWrap(True)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.alignment_notice = QLabel()
        self.alignment_notice.setWordWrap(True)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow(self.align_label, self.curve_combo)
        form.addRow(self.shift_label, self.shift_spin)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(self.title_label)
        layout.addWidget(self.curve_list)
        layout.addLayout(form)
        layout.addWidget(self.shift_slider)
        layout.addWidget(self.align_button)
        layout.addWidget(self.alignment_notice)
        layout.addWidget(self.reset_button)
        layout.addWidget(self.status_label)
        self.retranslate()
        self.hide()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.title_label.setText(t("theory.curves"))
        self.align_label.setText(t("theory.align_source"))
        self.shift_label.setText(t("theory.shift"))
        self.align_button.setText(t("theory.align_test"))
        self.shift_slider.setToolTip(t("theory.shift_hint"))
        self.reset_button.setText(t("theory.reset_time"))
        self.set_alignment_notice(self._notice_key, **self._notice_values)

    def set_curves(self, project: ProjectData, curves: tuple[DisplayCurve, ...]) -> None:
        self._project = project
        self._curves = tuple(
            item for item in curves
            if self._dimension is None
            or Quantity_Dimension(item.channel.quantity) == self._dimension
        )
        selected = self.curve_combo.currentData()
        self.curve_combo.blockSignals(True)
        self.curve_combo.clear()
        for item in self._curves:
            self.curve_combo.addItem(item.label, item.reference.stable_id)
        index = self.curve_combo.findData(selected)
        self.curve_combo.setCurrentIndex(max(0, index) if self._curves else -1)
        self.curve_combo.blockSignals(False)
        self.setVisible(bool(project.sources))
        self._alignment_refresh()

    def _selected_curve(self) -> DisplayCurve | None:
        selected = self.curve_combo.currentData()
        return next((item for item in self._curves if item.reference.stable_id == selected), None)

    def _alignment_source(self) -> Source | None:
        curve = self._selected_curve()
        if curve is not None:
            return self._project.sources[curve.reference.source_id]
        return next((source for source in self._project.sources.values()
                     if source.source_kind == SourceKind.THEORETICAL), None)

    def _alignment_refresh(self) -> None:
        self.shift_spin.blockSignals(True)
        source = self._alignment_source()
        shift = source.display_transform.shift_s if source else 0.0
        if source and source.display_transform.zero_start:
            shift -= self._project.source_display_anchor(source.id) or 0.0
        self.shift_spin.setValue(shift)
        self.shift_spin.blockSignals(False)
        self.shift_spin.setEnabled(source is not None)
        self.shift_slider.blockSignals(True)
        if not self.shift_slider.isSliderDown():
            times = [stream.dataset.project_time for stream in self._project.streams.values()]
            finite = [values[np.isfinite(values)] for values in times]
            finite = [values for values in finite if values.size]
            span = (max(float(values.max()) for values in finite)
                    - min(float(values.min()) for values in finite)) if finite else 10.0
            self._slider_span = max(10.0, span, abs(self.shift_spin.value()) * 1.25)
        self.shift_slider.setValue(round(self.shift_spin.value() / self._slider_span * 10000))
        self.shift_slider.blockSignals(False)
        self.shift_slider.setEnabled(source is not None)
        self.reset_button.setEnabled(source is not None)
        self.align_button.setToolTip(self._translations.translate("theory.align_hint"))

    def _selection_changed(self) -> None:
        self._alignment_refresh()
        self.view_changed.emit()

    def _emit_transform(self, **changes: object) -> None:
        source = self._alignment_source()
        if source is not None:
            self.display_changed.emit(source.id, replace(source.display_transform, **changes))

    def _shift_changed(self, value: float) -> None:
        self._emit_transform(zero_start=False, shift_s=value)

    def _slider_changed(self, value: int) -> None:
        self.shift_spin.setValue(value / 10000 * self._slider_span)

    def _align_start(self) -> None:
        source = self._alignment_source()
        self.align_requested.emit(source.id if source else "")

    def set_alignment_notice(self, key: str = "", **values: object) -> None:
        self._notice_key, self._notice_values = key, values
        self.alignment_notice.setText(self._translations.translate(key, **values) if key else "")

    def _reset(self) -> None:
        self._emit_transform(zero_start=False, shift_s=0.0)

    def _visibility_changed(self, item: QListWidgetItem) -> None:
        stable_id = str(item.data(Qt.ItemDataRole.UserRole))
        curve = next(curve for curve in self._curves if curve.reference.stable_id == stable_id)
        source = self._project.sources[curve.reference.source_id]
        hidden = set(source.display_transform.hidden_curve_ids)
        if item.checkState() == Qt.CheckState.Checked:
            hidden.discard(stable_id)
        else:
            hidden.add(stable_id)
        transform = replace(source.display_transform, hidden_curve_ids=tuple(sorted(hidden)))
        self.display_changed.emit(source.id, transform)

    def plot_onto(
        self,
        plot: AnalysisPlotWidget,
        target: Channel | None,
        display_unit: str,
        preferences: Mapping[str, str],
        display_mode: UnitDisplayMode,
    ) -> tuple[str, bool]:
        selected = self._selected_curve()
        if target is None and selected is not None:
            target = selected.channel
            display_unit = target.effective_display_unit(preferences, display_mode=display_mode)
        self.curve_list.blockSignals(True)
        self.curve_list.clear()
        self._compatible.clear()
        blocked = 0
        plotted = False
        for index, curve in enumerate(self._curves):
            source = self._project.sources[curve.reference.source_id]
            compatible = target is not None and CurveDisplay_IsCompatible(
                curve.channel, target, display_unit
            )
            time = self._project.display_time(curve.reference)
            usable = bool(np.any(np.isfinite(time) & np.isfinite(curve.channel.values)))
            stable_id = curve.reference.stable_id
            visible = stable_id not in source.display_transform.hidden_curve_ids
            text = self._translations.translate("theory.legend", curve=curve.label)
            item = QListWidgetItem(text)
            item.setToolTip(text)
            item.setData(Qt.ItemDataRole.UserRole, stable_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if visible and compatible and usable
                else Qt.CheckState.Unchecked
            )
            if not compatible or not usable:
                reason = self._translations.translate(
                    "theory.incompatible" if not compatible else "theory.empty"
                )
                item.setText(f"{text} — {reason}")
                item.setToolTip(reason)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                blocked += 1
            else:
                self._compatible.add(stable_id)
                if visible:
                    plot.add_series(
                        time, curve.channel.display_values(display_unit),
                        name=text, style_index=index + 2, theoretical=True,
                    )
                    plotted = True
            self.curve_list.addItem(item)
        self.curve_list.blockSignals(False)
        row_height = max(24, self.curve_list.sizeHintForRow(0))
        self.curve_list.setFixedHeight(min(4, max(1, len(self._curves))) * row_height + 6)
        self.status_label.setText(
            self._translations.translate("theory.blocked", count=blocked) if blocked
            else self._translations.translate("theory.alignment_hint")
        )
        return display_unit, plotted
