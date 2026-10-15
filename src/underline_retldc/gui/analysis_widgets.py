from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.app.settings import THEME_DARK, Theme_Normalize
from underline_retldc.core.diagnostics import Diagnostic
from underline_retldc.core.units import (
    UnitDisplayMode,
    UnitDisplayMode_Normalize,
)
from underline_retldc.gui.plot_analysis import AnalysisPlotDataItem
from underline_retldc.gui.plot_ui_i18n import PlotQtTranslations_Ensure, PlotUiLocalizer
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
        self._forced_tick: float | None = None
        self.enableAutoSIPrefix(False)

    def set_display_mode(self, mode: UnitDisplayMode | str) -> None:
        self._display_mode = UnitDisplayMode_Normalize(mode)
        self.picture = None
        self.update()

    def set_forced_tick(self, value: float | None) -> None:
        self._forced_tick = None if value is None else float(value)
        self.picture = None
        self.update()

    def tickValues(
        self,
        minVal: float,
        maxVal: float,
        size: float,
    ) -> list[tuple[float, list[float]]]:
        levels = super().tickValues(minVal, maxVal, size)
        forced = self._forced_tick
        if self.logMode or forced is None or forced < minVal or forced > maxVal or not levels:
            return levels
        spacing, values = levels[0]
        tolerance = max(abs(float(spacing)) * 1.0e-6, 1.0e-12)
        if not any(abs(float(value) - forced) <= tolerance for value in values):
            levels[0] = (spacing, sorted([*values, forced]))
        return levels

    def tickStrings(
        self,
        values: list[float],
        scale: float,
        spacing: float,
    ) -> list[str]:
        if self._display_mode is UnitDisplayMode.SI_SCIENTIFIC and not self.logMode:
            return [
                "0" if float(value) == 0.0 else f"{float(value):.3e}"
                for value in values
            ]
        return super().tickStrings(values, scale, spacing)


class AnalysisPlotWidget(QWidget):
    select_channel_requested = Signal()
    analysis_scope_changed = Signal(bool)

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
        self._series_data: list[tuple[np.ndarray, np.ndarray]] = []
        self._horizontal_references: dict[str, dict[str, Any]] = {}
        self._axis_labels = ("", "", "")
        self._active_interval: tuple[float, float] | None = None
        PlotQtTranslations_Ensure(translations)
        self.bottom_axis = DisplayAxisItem("bottom")
        self.left_axis = DisplayAxisItem("left")
        self.plot_widget = pg.PlotWidget(
            axisItems={
                "bottom": self.bottom_axis,
                "left": self.left_axis,
            }
        )
        self.plot_widget.setObjectName("analysisPlot")
        self._plot_ui_localizer = PlotUiLocalizer(self.plot_widget, translations, self)
        control = self.plot_widget.getPlotItem().ctrl
        self.analysis_scope_check = QCheckBox(control.transformGroup)
        self.analysis_scope_check.setObjectName("analysisActiveOnly")
        control.gridLayout.addWidget(self.analysis_scope_check, 6, 0, 1, 1)
        self.analysis_scope_check.toggled.connect(self._analysis_scope_update)
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

        self.plot_container = QWidget()
        plot_layout = QVBoxLayout(self.plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(2)
        plot_layout.addWidget(self.plot_widget, 1)
        self.analysis_status = QToolButton()
        self.analysis_status.setObjectName("plotAnalysisStatus")
        self.analysis_status.setCheckable(True)
        self.analysis_status.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.analysis_status.setArrowType(Qt.ArrowType.RightArrow)
        plot_layout.addWidget(self.analysis_status, alignment=Qt.AlignmentFlag.AlignLeft)
        self.analysis_details = QLabel()
        self.analysis_details.setWordWrap(True)
        self.analysis_details.setTextFormat(Qt.TextFormat.PlainText)
        self.analysis_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setMaximumHeight(100)
        details_scroll.setWidget(self.analysis_details)
        details_scroll.hide()
        plot_layout.addWidget(details_scroll)
        self.analysis_status.toggled.connect(details_scroll.setVisible)
        self.analysis_status.toggled.connect(lambda expanded: self.analysis_status.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow,
        ))
        self._analysis_details_scroll = details_scroll
        stack = QStackedLayout(self)
        stack.setStackingMode(QStackedLayout.StackingMode.StackOne)
        stack.addWidget(self.plot_container)
        stack.addWidget(self.empty_widget)
        self._stack = stack
        self.set_empty_state("", button_visible=False)
        self.apply_theme("light")
        self.plot_widget.getPlotItem().ctrl.fftCheck.toggled.connect(self._axis_labels_refresh)
        translations.locale_changed.connect(self._axis_labels_refresh)

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
        self._axis_labels = (x_label, y_label, y_unit)
        self._axis_labels_refresh()

    def _axis_labels_refresh(self, *_args: object) -> None:
        """Describe pyqtgraph's existing abs(rfft(y)/N), without changing its algorithm."""
        x_label, y_label, y_unit = self._axis_labels
        if self.plot_widget.getPlotItem().ctrl.fftCheck.isChecked():
            x_label = self._translations.translate("plot.axis.frequency")
            y_label = self._translations.translate("plot.axis.fft_magnitude", quantity=y_label)
            x_unit = "Hz"
        else:
            x_unit = "s"
        self.plot_widget.setLabel("bottom", x_label, units=x_unit)
        self.plot_widget.setLabel("left", y_label, units=y_unit or None)
        self.analysis_scope_check.setText(self._translations.translate("plot.analysis.active_only"))
        self.analysis_scope_check.setToolTip(self._translations.translate("plot.analysis.scope_tip"))
        self.plot_widget.getPlotItem().ctrl.fftCheck.setToolTip(
            self._translations.translate("plot.analysis.fft_tip"),
        )
        fft = self.plot_widget.getPlotItem().ctrl.fftCheck.isChecked()
        for region in (self.pre_region, self.active_region, self.post_region):
            in_scope = not self.analysis_scope_check.isChecked() or region is self.active_region
            region.setVisible(bool(region.property("timeRegionVisible")) and not fft and in_scope)
        for reference in self._horizontal_references.values():
            reference["item"].setVisible(reference["visible"] and not fft)
        self._analysis_notices_refresh()

    def set_analysis_active_only(self, enabled: bool) -> None:
        if self.analysis_scope_check.isChecked() == enabled:
            return
        blocker = QSignalBlocker(self.analysis_scope_check)
        self.analysis_scope_check.setChecked(enabled)
        del blocker
        self._analysis_scope_apply()
        self.plot_widget.enableAutoRange()

    def _analysis_scope_update(self, enabled: bool) -> None:
        self._analysis_scope_apply()
        self.plot_widget.enableAutoRange()
        self.analysis_scope_changed.emit(enabled)

    def _analysis_scope_apply(self) -> None:
        for series in self._series:
            interval = series.analysis_interval if series.theoretical else self._active_interval
            series.set_analysis_scope(self.analysis_scope_check.isChecked(), interval)
        self._analysis_notices_refresh()
        self._axis_labels_refresh()
        if self.analysis_scope_check.isChecked():
            self.plot_widget.enableAutoRange()

    def _analysis_notices_refresh(self) -> None:
        messages = []
        resampled = unavailable = 0
        for series in self._series:
            if series.analysis_notice:
                message = self._translations.translate("plot.analysis." + series.analysis_notice)
                messages.append(f"{series.name()}: {message}")
                interpolated = series.analysis_notice.startswith("resampled")
                resampled += interpolated
                unavailable += not interpolated
        self.analysis_status.setText(self._translations.translate(
            "plot.analysis.status", resampled=resampled, unavailable=unavailable,
        ))
        details = "\n".join(messages)
        self.analysis_status.setToolTip(details)
        self.analysis_details.setText(details)
        self.analysis_status.setVisible(bool(messages))
        if not messages:
            self.analysis_status.setChecked(False)
            self._analysis_details_scroll.hide()

    def clear_series(self) -> None:
        for item in self._series:
            self.plot_widget.removeItem(item)
        self._series.clear()
        self._series_data.clear()
        self._analysis_notices_refresh()

    def add_series(
        self,
        time: np.ndarray,
        values: np.ndarray,
        *,
        name: str,
        style_index: int = 0,
        theoretical: bool = False,
        scientific_time: np.ndarray | None = None,
        active_interval: tuple[float, float] | None = None,
    ) -> Any:
        style = self.SERIES_STYLES[style_index % len(self.SERIES_STYLES)]
        used_colors = {series.opts["pen"].color().name() for series in self._series}
        color = QColor(style.color)
        if color.name() in used_colors:
            available = next(
                (candidate.color for candidate in self.SERIES_STYLES
                 if candidate.color not in used_colors),
                None,
            )
            if available is not None:
                color = QColor(available)
            else:
                index = len(self._series)
                while color.name() in used_colors:
                    color = QColor.fromHsvF((index * 0.61803398875) % 1.0, 0.65, 0.95)
                    index += 1
        item = AnalysisPlotDataItem(
            time,
            values,
            scientific_time=time if scientific_time is None else scientific_time,
            interval=active_interval if theoretical else self._active_interval,
            active_only=self.analysis_scope_check.isChecked(), theoretical=theoretical,
            connect="finite",
            pen=pg.mkPen(
                color,
                width=style.width,
                style=Qt.PenStyle.DashLine if theoretical else Qt.PenStyle.SolidLine,
            ),
            name=name,
        )
        item.notice_changed.connect(self._analysis_notices_refresh)
        self.plot_widget.addItem(item)
        self._series.append(item)
        self._series_data.append((np.asarray(time), np.asarray(values)))
        self._analysis_notices_refresh()
        return item

    def set_horizontal_reference(
        self,
        key: str,
        value: float,
        label: str,
        visible: bool = True,
        style: Mapping[str, Any] | None = None,
    ) -> Any:
        """Create or update a display-only horizontal reference overlay."""
        reference_style = dict(style or {})
        color = str(reference_style.get("color", "#cbd5e1"))
        width = float(reference_style.get("width", 1.2))
        pen_style = reference_style.get("pen_style", Qt.PenStyle.DashLine)
        entry = self._horizontal_references.get(str(key))
        if entry is None:
            item = pg.InfiniteLine(
                pos=float(value),
                angle=0,
                movable=False,
                pen=pg.mkPen(color, width=width, style=pen_style),
                label=label,
                labelOpts={"position": 0.96, "anchors": [(1, 1), (1, 1)]},
            )
            item.setZValue(20)
            self.plot_widget.addItem(item)
            entry = {"item": item}
            self._horizontal_references[str(key)] = entry
        item = entry["item"]
        item.setValue(float(value))
        item.setPen(pg.mkPen(color, width=width, style=pen_style))
        if getattr(item, "label", None) is not None:
            item.label.setText(label)
            item.label.setColor(color)
        item.setVisible(bool(visible))
        entry.update(
            {
                "value": float(value),
                "visible": bool(visible),
                "force_fit": bool(reference_style.get("force_fit", False)),
                "force_tick": bool(reference_style.get("force_tick", False)),
            }
        )
        forced_ticks = [
            float(candidate["value"])
            for candidate in self._horizontal_references.values()
            if candidate["visible"] and candidate["force_tick"]
        ]
        self.left_axis.set_forced_tick(forced_ticks[0] if forced_ticks else None)
        self._axis_labels_refresh()
        return item

    def set_regions(
        self,
        regions: Mapping[str, list[float] | tuple[float, float] | None],
    ) -> None:
        active = regions.get("active_test", regions.get("burn"))
        self._active_interval = tuple(active) if active is not None else None
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
            item.setProperty("timeRegionVisible", value is not None and len(value) == 2)
        self._analysis_scope_apply()
        self._axis_labels_refresh()

    def fit_view(
        self,
        *,
        time: np.ndarray | None = None,
        values: tuple[np.ndarray, ...] = (),
        regions: Mapping[str, list[float] | tuple[float, float] | None] | None = None,
    ) -> None:
        control = self.plot_widget.getPlotItem().ctrl
        if self.analysis_scope_check.isChecked() or any(check.isChecked() for check in (
            control.fftCheck, control.derivativeCheck, control.phasemapCheck,
        )):
            self.plot_widget.enableAutoRange()
            return
        selected_regions = dict(regions or {})
        if time is None and self._series_data:
            time = np.concatenate([item[0] for item in self._series_data])
        if not values and self._series_data:
            values = tuple(item[1] for item in self._series_data)
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
            data_span = max(maximum - minimum, abs(maximum) * 0.05, 1.0e-12)
            for reference in self._horizontal_references.values():
                if not reference["visible"]:
                    continue
                reference_value = float(reference["value"])
                reasonably_near = (
                    minimum - 2.0 * data_span
                    <= reference_value
                    <= maximum + 2.0 * data_span
                )
                if reference["force_fit"] or reasonably_near:
                    minimum = min(minimum, reference_value)
                    maximum = max(maximum, reference_value)
            if minimum == maximum:
                padding = max(abs(minimum) * 0.1, 1.0)
                minimum -= padding
                maximum += padding
            self.plot_widget.setYRange(minimum, maximum, padding=0.08)

    def reset_view(self) -> None:
        """Restore the chart's data-driven automatic X/Y range."""
        if self._series_data:
            self.fit_view()
            return
        self.plot_widget.enableAutoRange(x=True, y=True)
        self.plot_widget.autoRange(padding=0.05)

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
        self._stack.setCurrentWidget(self.empty_widget if empty else self.plot_container)


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
            label_item = QTableWidgetItem(label)
            label_item.setToolTip(label)
            value_item = QTableWidgetItem(value)
            value_item.setToolTip(value)
            self.table.setItem(row, 0, label_item)
            self.table.setItem(row, 1, value_item)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.updateGeometry()
        self.table.viewport().update()


class AnalysisDiagnosticsPanel(QGroupBox):
    """Shared diagnostic presentation for measurement analysis results."""

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self.list = QListWidget()
        self.list.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)

    def set_diagnostics(
        self,
        diagnostics: Iterable[Diagnostic],
        *,
        notice: str = "",
    ) -> None:
        translate = self._translations.translate
        self.setTitle(translate("import.diagnostics"))
        self.list.clear()
        for diagnostic in diagnostics:
            message = translate(
                f"diagnostic.{diagnostic.code}",
                diagnostic.message,
                message=diagnostic.message,
            )
            self.list.addItem(
                f"[{diagnostic.severity.value}] {diagnostic.code}: {message}"
            )
        if notice:
            self.list.addItem(notice)


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
        self._splitter_timer = QTimer(self)
        self._splitter_timer.setSingleShot(True)
        self._splitter_timer.timeout.connect(self._splitter_sizes_initialize)

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if not self._splitter_initialized:
            self._splitter_timer.start(0)

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
