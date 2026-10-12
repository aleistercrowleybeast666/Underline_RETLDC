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
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.channel import Channel
from underline_retldc.core.curve_display import CurveDisplay_IsCompatible, DisplayCurve
from underline_retldc.core.project_data import ProjectData
from underline_retldc.core.units import Quantity_Dimension, UnitDisplayMode
from underline_retldc.gui.analysis_widgets import AnalysisPlotWidget
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class TheoryOverlayWidget(QWidget):
    """Shared view controls; emits source display state, never workflow input changes."""

    display_changed = Signal(str, object)
    view_changed = Signal()

    def __init__(self, translations: TranslationService, dimension: str | None) -> None:
        super().__init__()
        self._translations = translations
        self._dimension = dimension
        self._project = ProjectData()
        self._curves: tuple[DisplayCurve, ...] = ()
        self._compatible: set[str] = set()
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
        self.shift_spin.valueChanged.connect(self._shift_changed)
        self.zero_button = QPushButton()
        self.zero_button.clicked.connect(self._zero_start)
        self.reset_button = QPushButton()
        self.reset_button.clicked.connect(self._reset)
        self.align_label = QLabel()
        self.shift_label = QLabel()
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow(self.align_label, self.curve_combo)
        form.addRow(self.shift_label, self.shift_spin)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(self.title_label)
        layout.addWidget(self.curve_list)
        layout.addLayout(form)
        layout.addWidget(self.zero_button)
        layout.addWidget(self.reset_button)
        layout.addWidget(self.status_label)
        self.retranslate()
        self.hide()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.title_label.setText(t("theory.curves"))
        self.align_label.setText(t("theory.align_source"))
        self.shift_label.setText(t("theory.shift"))
        self.zero_button.setText(t("theory.zero_start"))
        self.reset_button.setText(t("theory.reset_time"))

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
        self.setVisible(bool(self._curves))
        self._alignment_refresh()

    def _selected_curve(self) -> DisplayCurve | None:
        selected = self.curve_combo.currentData()
        return next((item for item in self._curves if item.reference.stable_id == selected), None)

    def _alignment_refresh(self) -> None:
        curve = self._selected_curve()
        self.shift_spin.blockSignals(True)
        source = self._project.sources[curve.reference.source_id] if curve else None
        self.shift_spin.setValue(source.display_transform.shift_s if source else 0.0)
        self.shift_spin.blockSignals(False)
        self.shift_spin.setEnabled(source is not None)
        self.zero_button.setEnabled(
            source is not None and self._project.source_display_anchor(source.id) is not None
        )
        self.reset_button.setEnabled(source is not None)
        self.zero_button.setToolTip(self._translations.translate("theory.zero_hint"))

    def _selection_changed(self) -> None:
        self._alignment_refresh()
        self.view_changed.emit()

    def _emit_transform(self, **changes: object) -> None:
        curve = self._selected_curve()
        if curve is not None:
            source = self._project.sources[curve.reference.source_id]
            self.display_changed.emit(source.id, replace(source.display_transform, **changes))

    def _shift_changed(self, value: float) -> None:
        self._emit_transform(shift_s=value)

    def _zero_start(self) -> None:
        self._emit_transform(zero_start=True, shift_s=0.0)

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
