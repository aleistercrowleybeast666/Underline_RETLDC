from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.app.settings import THEME_DARK, Theme_Normalize
from underline_retldc.core.units import (
    UnitDisplayMode,
    UnitDisplayMode_Normalize,
)
from underline_retldc.i18n.service import TranslationService


@dataclass(frozen=True, slots=True)
class AnalysisSeriesStyle:
    color: str
    width: float = 1.6


class DisplayAxisItem(pg.AxisItem):
    """Axis that never invents pyqtgraph SI prefixes and can show scientific ticks."""

    def __init__(self, orientation: str) -> None:
        super().__init__(orientation=orientation)
        self._display_mode = UnitDisplayMode.ENGINEERING
        self.enableAutoSIPrefix(False)

    def set_display_mode(self, mode: UnitDisplayMode | str) -> None:
        self._display_mode = UnitDisplayMode_Normalize(mode)
        self.picture = None
        self.update()

    def tickStrings(
        self,
        values: list[float],
        scale: float,
        spacing: float,
    ) -> list[str]:
        if self._display_mode is UnitDisplayMode.SI_SCIENTIFIC:
            return [
                "0" if float(value) == 0.0 else f"{float(value):.3e}"
                for value in values
            ]
        return super().tickStrings(values, scale, spacing)


class AnalysisPlotWidget(QWidget):
    select_channel_requested = Signal()

    SERIES_STYLES = (
        AnalysisSeriesStyle("#4cc9f0"),
        AnalysisSeriesStyle("#ff9f43"),
        AnalysisSeriesStyle("#4ade80"),
        AnalysisSeriesStyle("#c084fc"),
        AnalysisSeriesStyle("#f87171"),
        AnalysisSeriesStyle("#facc15"),
    )

    def __init__(
        self,
        translations: TranslationService,
        *,
        regions_movable: bool,
    ) -> None:
        super().__init__()
        self._translations = translations
        self._theme = "light"
        self._display_mode = UnitDisplayMode.ENGINEERING
        self._series: list[Any] = []
        self.bottom_axis = DisplayAxisItem("bottom")
        self.left_axis = DisplayAxisItem("left")
        self.plot_widget = pg.PlotWidget(
            axisItems={
                "bottom": self.bottom_axis,
                "left": self.left_axis,
            }
        )
        self.plot_widget.setObjectName("analysisPlot")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.22)
        self.plot_widget.setDownsampling(auto=True, mode="peak")
        self.plot_widget.setClipToView(True)
        self.legend = self.plot_widget.addLegend(offset=(12, 12))

        self.pre_region = self._region_create(
            [0.0, 1.0], "#60a5fa", (70, 130, 180, 48), regions_movable
        )
        self.active_region = self._region_create(
            [1.0, 2.0], "#fb923c", (255, 140, 70, 58), regions_movable
        )
        self.post_region = self._region_create(
            [2.0, 3.0], "#4ade80", (90, 180, 120, 48), regions_movable
        )
        for region in (self.pre_region, self.active_region, self.post_region):
            region.setVisible(False)
            self.plot_widget.addItem(region)

        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.addStretch(1)
        self.empty_label = QLabel()
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_button = QPushButton()
        self.empty_button.clicked.connect(self.select_channel_requested)
        empty_layout.addWidget(self.empty_label)
        empty_layout.addWidget(
            self.empty_button,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        empty_layout.addStretch(1)

        stack = QStackedLayout(self)
        stack.setStackingMode(QStackedLayout.StackingMode.StackOne)
        stack.addWidget(self.plot_widget)
        stack.addWidget(self.empty_widget)
        self._stack = stack
        self.set_empty_state("", button_visible=False)
        self.apply_theme("light")

    def set_display_mode(self, mode: UnitDisplayMode | str) -> None:
        self._display_mode = UnitDisplayMode_Normalize(mode)
        self.bottom_axis.set_display_mode(self._display_mode)
        self.left_axis.set_display_mode(self._display_mode)

    @staticmethod
    def _region_create(
        values: list[float],
        color: str,
        brush: tuple[int, int, int, int],
        movable: bool,
    ) -> pg.LinearRegionItem:
        return pg.LinearRegionItem(
            values,
            movable=movable,
            brush=pg.mkBrush(*brush),
            pen=pg.mkPen(color),
        )

    def apply_theme(self, theme: str) -> None:
        self._theme = Theme_Normalize(theme)
        if self._theme == THEME_DARK:
            background = "#0b1220"
            axis_color = "#cbd5e1"
            legend_background = pg.mkBrush(15, 23, 42, 220)
            legend_border = "#475569"
        else:
            background = "#0b1f3a"
            axis_color = "#ffffff"
            legend_background = pg.mkBrush(11, 31, 58, 210)
            legend_border = "#7f9bc2"
        self.plot_widget.setBackground(background)
        self.legend.setBrush(legend_background)
        self.legend.setPen(pg.mkPen(legend_border))
        self.legend.setLabelTextColor(axis_color)
        for axis_name in ("bottom", "left"):
            axis = self.plot_widget.getAxis(axis_name)
            axis.setPen(pg.mkPen(axis_color))
            axis.setTextPen(pg.mkPen(axis_color))
        self.plot_widget.update()

    def set_axis(self, *, x_label: str, y_label: str, y_unit: str = "") -> None:
        self.plot_widget.setLabel("bottom", x_label, units="s")
        self.plot_widget.setLabel("left", y_label, units=y_unit or None)

    def clear_series(self) -> None:
        for item in self._series:
            self.plot_widget.removeItem(item)
        self._series.clear()

    def add_series(
        self,
        time: np.ndarray,
        values: np.ndarray,
        *,
        name: str,
        style_index: int = 0,
    ) -> Any:
        finite = np.isfinite(time) & np.isfinite(values)
        style = self.SERIES_STYLES[style_index % len(self.SERIES_STYLES)]
        item = self.plot_widget.plot(
            time[finite],
            values[finite],
            pen=pg.mkPen(style.color, width=style.width),
            name=name,
        )
        self._series.append(item)
        return item

    def set_regions(
        self,
        regions: Mapping[str, list[float] | tuple[float, float] | None],
    ) -> None:
        for keys, item in (
            (("pre",), self.pre_region),
            (("active_test", "burn"), self.active_region),
            (("post",), self.post_region),
        ):
            value = next((regions.get(key) for key in keys if key in regions), None)
            if value is not None and len(value) == 2:
                item.setRegion([float(value[0]), float(value[1])])
                item.setVisible(True)
            else:
                item.setVisible(False)

    def fit_view(
        self,
        *,
        time: np.ndarray | None = None,
        values: tuple[np.ndarray, ...] = (),
        regions: Mapping[str, list[float] | tuple[float, float] | None] | None = None,
    ) -> None:
        selected_regions = dict(regions or {})
        active = selected_regions.get("active_test", selected_regions.get("burn"))
        pre = selected_regions.get("pre")
        post = selected_regions.get("post")
        if active is not None:
            start = float(pre[0] if pre is not None else active[0])
            end = float(post[1] if post is not None else active[1])
        elif time is not None and np.any(np.isfinite(time)):
            finite_time = time[np.isfinite(time)]
            start, end = float(np.min(finite_time)), float(np.max(finite_time))
        else:
            self.plot_widget.enableAutoRange()
            return
        if start < end:
            self.plot_widget.setXRange(start, end, padding=0.02)
        finite_values = tuple(
            array[np.isfinite(array)] for array in values if np.any(np.isfinite(array))
        )
        if finite_values:
            minimum = min(float(np.min(array)) for array in finite_values)
            maximum = max(float(np.max(array)) for array in finite_values)
            if minimum == maximum:
                padding = max(abs(minimum) * 0.1, 1.0)
                minimum -= padding
                maximum += padding
            self.plot_widget.setYRange(minimum, maximum, padding=0.08)

    def reset_view(self) -> None:
        """Restore the chart's data-driven automatic X/Y range."""

        # PlotDataItem clipping is useful while panning large logs, but its
        # current viewport bounds would otherwise make autoRange fit only the
        # already zoomed fragment. Temporarily expose the full curve bounds.
        self.plot_widget.setClipToView(False)
        try:
            self.plot_widget.enableAutoRange(x=True, y=True)
            self.plot_widget.autoRange(padding=0.05)
        finally:
            self.plot_widget.setClipToView(True)

    def set_empty_state(
        self,
        message: str | None,
        *,
        button_text: str = "",
        button_visible: bool = True,
    ) -> None:
        empty = bool(message)
        self.empty_label.setText(message or "")
        self.empty_button.setText(button_text)
        self.empty_button.setVisible(empty and button_visible)
        self._stack.setCurrentWidget(self.empty_widget if empty else self.plot_widget)


class AnalysisResultsPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__()
        self.table = QTableWidget(0, 2)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)

    def set_headers(self, first: str, second: str) -> None:
        self.table.setHorizontalHeaderLabels([first, second])

    def set_rows(self, rows: tuple[tuple[str, str], ...]) -> None:
        self.table.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(label))
            self.table.setItem(row, 1, QTableWidgetItem(value))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.updateGeometry()
        self.table.viewport().update()


class AnalysisWorkspaceShell(QWidget):
    CONTROLS_MINIMUM_WIDTH = 320
    CONTROLS_MAXIMUM_WIDTH = 400
    PLOT_MINIMUM_WIDTH = 250
    RESULTS_MINIMUM_WIDTH = 220
    RESULTS_MAXIMUM_WIDTH = 310

    def __init__(
        self,
        controls: QWidget,
        plot: AnalysisPlotWidget,
        results: QWidget,
    ) -> None:
        super().__init__()
        controls_scroll = QScrollArea()
        controls_scroll.setObjectName("analysisControlsScroll")
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        controls_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        controls_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        controls_scroll.setMinimumWidth(self.CONTROLS_MINIMUM_WIDTH)
        controls_scroll.setMaximumWidth(self.CONTROLS_MAXIMUM_WIDTH)
        controls_scroll.setWidget(controls)
        plot.setMinimumWidth(self.PLOT_MINIMUM_WIDTH)
        results.setMinimumWidth(self.RESULTS_MINIMUM_WIDTH)
        results.setMaximumWidth(self.RESULTS_MAXIMUM_WIDTH)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(controls_scroll)
        splitter.addWidget(plot)
        splitter.addWidget(results)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setChildrenCollapsible(False)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.splitter = splitter
        self.controls = controls
        self.controls_scroll = controls_scroll
        self.plot = plot
        self.results = results
        self._splitter_initialized = False

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if not self._splitter_initialized:
            QTimer.singleShot(0, self._splitter_sizes_initialize)

    def _splitter_sizes_initialize(self) -> None:
        handle_space = self.splitter.handleWidth() * 2
        available = max(0, self.splitter.width() - handle_space)
        if available <= 0:
            return
        left = min(
            self.CONTROLS_MAXIMUM_WIDTH,
            max(self.CONTROLS_MINIMUM_WIDTH, round(available * 0.28)),
        )
        right = min(
            self.RESULTS_MAXIMUM_WIDTH,
            max(self.RESULTS_MINIMUM_WIDTH, round(available * 0.23)),
        )
        center = available - left - right
        if center < self.PLOT_MINIMUM_WIDTH:
            shortfall = self.PLOT_MINIMUM_WIDTH - center
            left_reduction = min(
                shortfall,
                left - self.CONTROLS_MINIMUM_WIDTH,
            )
            left -= left_reduction
            shortfall -= left_reduction
            right -= min(
                shortfall,
                right - self.RESULTS_MINIMUM_WIDTH,
            )
            center = available - left - right
        self.splitter.setSizes(
            [left, max(self.PLOT_MINIMUM_WIDTH, center), right]
        )
        self._splitter_initialized = True
