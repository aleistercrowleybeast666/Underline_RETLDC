from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.app.settings import THEME_DARK, THEME_LIGHT, Theme_Normalize
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.regions import BurnCandidate, RegionSelection, TimeRegion
from underline_retldc.gui.schema_form import SchemaForm
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class ProcessPage(QWidget):
    detect_requested = Signal()
    apply_requested = Signal()
    plugins_requested = Signal()
    regions_changed = Signal()

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self._raw_dataset: Dataset | None = None
        self._calibrated_dataset: Dataset | None = None
        self._processed_dataset: Dataset | None = None
        self._candidates: list[BurnCandidate] = []
        self._processors: tuple[Any, ...] = ()
        self._curve_items: list[Any] = []
        self._regions_syncing = False
        self._theme = THEME_LIGHT

        self.plot_widget = pg.PlotWidget(background="#0b1f3a")
        self.plot_widget.setObjectName("analysisPlot")
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.setLabel("left", "Value")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.22)
        self.plot_legend = self.plot_widget.addLegend(offset=(12, 12))
        self.plot_legend.setBrush(pg.mkBrush(11, 31, 58, 210))
        self.plot_legend.setPen(pg.mkPen("#7f9bc2"))
        self.plot_legend.setLabelTextColor("#ffffff")
        for axis_name in ("bottom", "left"):
            axis = self.plot_widget.getAxis(axis_name)
            axis.setPen(pg.mkPen("#ffffff"))
            axis.setTextPen(pg.mkPen("#ffffff"))
        self.plot_widget.setDownsampling(auto=True, mode="peak")
        self.plot_widget.setClipToView(True)

        self.pre_region = pg.LinearRegionItem(
            [0.0, 1.0], brush=pg.mkBrush(70, 130, 180, 45), pen=pg.mkPen("#4682b4")
        )
        self.burn_region = pg.LinearRegionItem(
            [1.0, 2.0], brush=pg.mkBrush(255, 140, 70, 55), pen=pg.mkPen("#ff8c46")
        )
        self.post_region = pg.LinearRegionItem(
            [2.0, 3.0], brush=pg.mkBrush(90, 180, 120, 45), pen=pg.mkPen("#5ab478")
        )
        for region in (self.pre_region, self.burn_region, self.post_region):
            region.setVisible(False)
            region.sigRegionChanged.connect(self._region_edits_refresh)
            region.sigRegionChangeFinished.connect(self.regions_changed)
            self.plot_widget.addItem(region)

        controls = QWidget()
        controls.setMinimumWidth(310)
        controls.setMaximumWidth(380)
        controls_layout = QVBoxLayout(controls)
        self.curves_group = QGroupBox()
        curves_layout = QVBoxLayout(self.curves_group)
        self.curve_checks: dict[str, QCheckBox] = {}
        for key in ("uncorrected", "corrected"):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._plot_refresh)
            self.curve_checks[key] = checkbox
            curves_layout.addWidget(checkbox)
        controls_layout.addWidget(self.curves_group)

        self.candidates_group = QGroupBox()
        candidates_layout = QVBoxLayout(self.candidates_group)
        self.detect_button = QPushButton()
        self.detect_button.clicked.connect(self.detect_requested)
        self.fit_button = QPushButton()
        self.fit_button.clicked.connect(self._regions_view_fit)
        self.candidate_combo = StandardComboBox()
        self.candidate_combo.currentIndexChanged.connect(self._candidate_selected)
        self.region_hint = QLabel()
        self.region_hint.setWordWrap(True)
        candidate_buttons = QHBoxLayout()
        candidate_buttons.addWidget(self.detect_button)
        candidate_buttons.addWidget(self.fit_button)
        candidates_layout.addLayout(candidate_buttons)
        candidates_layout.addWidget(self.candidate_combo)
        candidates_layout.addWidget(self.region_hint)
        controls_layout.addWidget(self.candidates_group)

        self.regions_group = QGroupBox()
        regions_layout = QFormLayout(self.regions_group)
        self.region_labels: dict[str, QLabel] = {}
        self.region_edits: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]] = {}
        for region_name in ("pre", "burn", "post"):
            label = QLabel()
            start_edit = QDoubleSpinBox()
            end_edit = QDoubleSpinBox()
            for edit in (start_edit, end_edit):
                edit.setDecimals(8)
                edit.setRange(-1.0e12, 1.0e12)
                edit.setMinimumWidth(122)
                edit.setMaximumWidth(145)
                edit.setAlignment(Qt.AlignmentFlag.AlignRight)
                edit.setSuffix(" s")
                edit.setKeyboardTracking(False)
                edit.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
                edit.valueChanged.connect(self._regions_update_from_edits)
            row = QHBoxLayout()
            row.addWidget(start_edit)
            row.addWidget(QLabel("→"))
            row.addWidget(end_edit)
            self.region_labels[region_name] = label
            self.region_edits[region_name] = (start_edit, end_edit)
            regions_layout.addRow(label, row)
        controls_layout.addWidget(self.regions_group)

        self.processing_group = QGroupBox()
        processing_layout = QFormLayout(self.processing_group)
        self.compensation_label = QLabel()
        self.processor_combo = StandardComboBox()
        self.processor_combo.currentIndexChanged.connect(self._processor_schema_update)
        self.plugins_button = QPushButton()
        self.plugins_button.clicked.connect(self.plugins_requested)
        processor_row = QHBoxLayout()
        processor_row.addWidget(self.processor_combo, 1)
        processor_row.addWidget(self.plugins_button)
        self.processor_form = SchemaForm(translations)
        self.apply_button = QPushButton()
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.clicked.connect(self.apply_requested)
        processing_layout.addRow(self.compensation_label, processor_row)
        processing_layout.addRow(self.processor_form)
        processing_layout.addRow(self.apply_button)
        controls_layout.addWidget(self.processing_group)
        controls_layout.addStretch(1)

        splitter = QSplitter()
        splitter.addWidget(controls)
        splitter.addWidget(self.plot_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([350, 700])
        layout = QHBoxLayout(self)
        layout.addWidget(splitter)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.curves_group.setTitle(t("process.curves"))
        for key, checkbox in self.curve_checks.items():
            checkbox.setText(t(f"process.{key}"))
        self.candidates_group.setTitle(t("process.candidates"))
        self.detect_button.setText(t("process.detect_candidates"))
        self.fit_button.setText(t("process.fit_regions"))
        self.processing_group.setTitle(t("page.process"))
        self.compensation_label.setText(t("process.enable_baseline"))
        self.plugins_button.setText(t("process.plugins"))
        self.apply_button.setText(t("process.apply"))
        self.region_hint.setText(t("process.region_hint"))
        self.regions_group.setTitle(t("process.manual_regions"))
        for region_name, label in self.region_labels.items():
            label.setText(t(f"process.{region_name}"))
        self.plot_widget.setLabel("bottom", t("common.time"), units="s")
        self.plot_widget.setLabel("left", t("common.value"))
        selected_processor = self.processor_id()
        processor_values = (
            self.processor_form.values() if self.processor_form.field_names else {}
        )
        self._processors_populate(selected_processor)
        self.processor_form.set_values(processor_values)
        self.processor_form.retranslate()
        self._candidate_labels_update()
        self._plot_refresh()

    def set_datasets(
        self,
        raw_dataset: Dataset | None,
        calibrated_dataset: Dataset | None,
        processed_dataset: Dataset | None,
    ) -> None:
        self._raw_dataset = raw_dataset
        self._calibrated_dataset = calibrated_dataset
        self._processed_dataset = processed_dataset
        self._plot_refresh()
        dataset = calibrated_dataset or raw_dataset
        if dataset is not None and dataset.sample_count >= 2:
            finite_time = dataset.time[np.isfinite(dataset.time)]
            if finite_time.size >= 2 and not self.pre_region.isVisible():
                start = float(np.min(finite_time))
                end = float(np.max(finite_time))
                span = end - start
                self.set_regions(
                    {
                        "pre": [start, start + 0.2 * span],
                        "burn": [start + 0.3 * span, start + 0.7 * span],
                        "post": [start + 0.8 * span, end],
                    }
                )

    def set_candidates(self, candidates: list[BurnCandidate]) -> None:
        self._candidates = list(candidates)
        self._candidate_labels_update()
        if candidates:
            self.candidate_combo.setCurrentIndex(0)
            self._candidate_selected(0)

    def _candidate_labels_update(self) -> None:
        current = self.candidate_combo.currentIndex()
        self.candidate_combo.blockSignals(True)
        self.candidate_combo.clear()
        if not self._candidates:
            self.candidate_combo.addItem(
                self._translations.translate("process.not_detected"), None
            )
        for index, candidate in enumerate(self._candidates):
            prefix = (
                self._translations.translate("process.recommended") + " — "
                if index == 0
                else ""
            )
            self.candidate_combo.addItem(
                self._translations.translate(
                    "process.candidate_line",
                    prefix=prefix,
                    start=f"{candidate.start:.5g}",
                    end=f"{candidate.end:.5g}",
                    peak=f"{candidate.peak:.5g}",
                    score=f"{candidate.score:.4g}",
                ),
                index,
            )
        if self._candidates:
            self.candidate_combo.setCurrentIndex(min(max(current, 0), len(self._candidates) - 1))
        self.candidate_combo.blockSignals(False)

    def _candidate_selected(self, index: int) -> None:
        if index < 0 or index >= len(self._candidates):
            return
        dataset = self._calibrated_dataset or self._raw_dataset
        if dataset is None:
            return
        candidate = self._candidates[index]
        finite_time = dataset.time[np.isfinite(dataset.time)]
        if finite_time.size < 2:
            return
        data_start = float(np.min(finite_time))
        data_end = float(np.max(finite_time))
        data_span = data_end - data_start
        burn_span = max(candidate.duration, data_span * 0.02)
        gap = max(data_span * 0.005, np.finfo(float).eps)
        pre_end = max(data_start + gap, candidate.start - gap)
        pre_start = max(data_start, pre_end - burn_span)
        post_start = min(data_end - gap, candidate.end + gap)
        post_end = min(data_end, post_start + burn_span)
        if pre_start < pre_end <= candidate.start and candidate.end <= post_start < post_end:
            self.set_regions(
                {
                    "pre": [pre_start, pre_end],
                    "burn": [candidate.start, candidate.end],
                    "post": [post_start, post_end],
                }
            )

    def set_regions(self, regions: dict[str, list[float] | tuple[float, float]]) -> None:
        selection = RegionSelection.from_dict(
            {key: list(map(float, regions[key])) for key in ("pre", "burn", "post")}
        )
        self._regions_syncing = True
        self.pre_region.setRegion(selection.pre.to_list())
        self.burn_region.setRegion(selection.burn.to_list())
        self.post_region.setRegion(selection.post.to_list())
        for region in (self.pre_region, self.burn_region, self.post_region):
            region.setVisible(True)
        self._regions_syncing = False
        self._region_edits_refresh()
        self.regions_changed.emit()

    def _region_edits_refresh(self) -> None:
        if self._regions_syncing:
            return
        self._regions_syncing = True
        for region_name, region in (
            ("pre", self.pre_region),
            ("burn", self.burn_region),
            ("post", self.post_region),
        ):
            start_edit, end_edit = self.region_edits[region_name]
            start, end = map(float, region.getRegion())
            start_edit.setValue(start)
            end_edit.setValue(end)
        self._regions_syncing = False

    def _regions_update_from_edits(self) -> None:
        if self._regions_syncing:
            return
        payload = {
            region_name: [start_edit.value(), end_edit.value()]
            for region_name, (start_edit, end_edit) in self.region_edits.items()
        }
        try:
            selection = RegionSelection.from_dict(payload)
        except ValueError:
            self._region_edits_refresh()
            return
        self._regions_syncing = True
        self.pre_region.setRegion(selection.pre.to_list())
        self.burn_region.setRegion(selection.burn.to_list())
        self.post_region.setRegion(selection.post.to_list())
        for region in (self.pre_region, self.burn_region, self.post_region):
            region.setVisible(True)
        self._regions_syncing = False
        self.regions_changed.emit()

    def regions(self) -> dict[str, list[float]]:
        selection = RegionSelection(
            pre=TimeRegion(*map(float, self.pre_region.getRegion())),
            burn=TimeRegion(*map(float, self.burn_region.getRegion())),
            post=TimeRegion(*map(float, self.post_region.getRegion())),
        )
        return selection.to_dict()

    def set_processors(
        self,
        processors: tuple[Any, ...],
        *,
        preferred_id: str | None,
    ) -> None:
        previous_id = self.processor_id()
        previous_values = (
            self.processor_form.values() if self.processor_form.field_names else {}
        )
        self._processors = tuple(processors)
        self._processors_populate(preferred_id)
        if preferred_id == previous_id:
            self.processor_form.set_values(previous_values)

    def _processors_populate(self, selected: str | None) -> None:
        self.processor_combo.blockSignals(True)
        self.processor_combo.clear()
        self.processor_combo.addItem(
            self._translations.translate("process.processor_none"), None
        )
        for processor in self._processors:
            descriptor = processor.descriptor
            self.processor_combo.addItem(
                self._translations.translate(
                    descriptor.translation_key or "", descriptor.name
                ),
                descriptor.plugin_id,
            )
        index = self.processor_combo.findData(selected)
        self.processor_combo.setCurrentIndex(max(0, index))
        self.processor_combo.blockSignals(False)
        self._processor_schema_update()

    def _processor_schema_update(self, _index: int | None = None) -> None:
        processor = self._selected_processor()
        if processor is None:
            self.processor_form.set_schema({"type": "object", "properties": {}})
            return
        self.processor_form.set_schema(processor.config_schema())

    def _selected_processor(self) -> Any | None:
        plugin_id = self.processor_id()
        return next(
            (
                processor
                for processor in self._processors
                if processor.descriptor.plugin_id == plugin_id
            ),
            None,
        )

    def processor_id(self) -> str | None:
        plugin_id = self.processor_combo.currentData()
        return str(plugin_id) if plugin_id else None

    def processing_config(self) -> dict[str, Any]:
        processor = self._selected_processor()
        if processor is None:
            return {}
        schema = processor.config_schema()
        raw_properties = schema.get("properties", {})
        if not isinstance(raw_properties, Mapping):
            raise ValueError("Processor config schema properties must be an object")
        config = self.processor_form.values()
        injected = {
            "processor.selection": True,
            "thrust_analysis.input_channel": "force_calibrated",
            "thrust_analysis.regions": self.regions(),
        }
        for field_name, raw_property in raw_properties.items():
            if not isinstance(raw_property, Mapping):
                raise ValueError(f"Processor schema field {field_name!r} must be an object")
            source = raw_property.get("x-ui-source")
            if source is not None:
                try:
                    config[str(field_name)] = injected[str(source)]
                except KeyError as exc:
                    raise ValueError(
                        f"Unsupported Processor x-ui-source {source!r}"
                    ) from exc
            elif bool(raw_property.get("x-ui-hidden", False)) and "default" in raw_property:
                config[str(field_name)] = raw_property["default"]
        return config

    def set_processing_config(
        self, plugin_id: str | None, config: Mapping[str, Any]
    ) -> None:
        index = self.processor_combo.findData(plugin_id)
        if index < 0:
            raise ValueError(f"Processor {plugin_id!r} is not available")
        self.processor_combo.setCurrentIndex(index)
        self.processor_form.set_values(config)
        if config.get("regions"):
            self.set_regions(config["regions"])

    def detection_sign(self) -> int:
        if "sign" not in self.processor_form.field_names:
            return 1
        return int(self.processor_form.values().get("sign", 1))

    def set_theme(self, theme: str) -> None:
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
        self.plot_legend.setBrush(legend_background)
        self.plot_legend.setPen(pg.mkPen(legend_border))
        self.plot_legend.setLabelTextColor(axis_color)
        for axis_name in ("bottom", "left"):
            axis = self.plot_widget.getAxis(axis_name)
            axis.setPen(pg.mkPen(axis_color))
            axis.setTextPen(pg.mkPen(axis_color))
        self.pre_region.setBrush(pg.mkBrush(70, 130, 180, 48))
        self.burn_region.setBrush(pg.mkBrush(255, 140, 70, 58))
        self.post_region.setBrush(pg.mkBrush(90, 180, 120, 48))
        for region, color in (
            (self.pre_region, "#60a5fa"),
            (self.burn_region, "#fb923c"),
            (self.post_region, "#4ade80"),
        ):
            for boundary in region.lines:
                boundary.setPen(pg.mkPen(color))
        self.plot_widget.update()

    def _plot_refresh(self) -> None:
        for item in self._curve_items:
            self.plot_widget.removeItem(item)
        self._curve_items.clear()
        uncorrected_dataset = self._calibrated_dataset or self._raw_dataset
        uncorrected_channel = (
            "force_calibrated"
            if uncorrected_dataset is not None
            and "force_calibrated" in uncorrected_dataset.channels
            else "thrust_raw"
        )
        corrected_channel = (
            "thrust_processed"
            if self._processed_dataset is not None
            and "thrust_processed" in self._processed_dataset.channels
            else "thrust_corrected"
        )
        curves: list[tuple[str, Dataset | None, str, str]] = [
            ("uncorrected", uncorrected_dataset, uncorrected_channel, "#4cc9f0"),
            ("corrected", self._processed_dataset, corrected_channel, "#ff9f43"),
        ]
        for key, dataset, channel_id, color in curves:
            if (
                not self.curve_checks[key].isChecked()
                or dataset is None
                or channel_id not in dataset.channels
            ):
                continue
            item = self.plot_widget.plot(
                dataset.time,
                dataset.channel(channel_id).values,
                pen=pg.mkPen(color, width=1.5),
                name=self._translations.translate(f"process.{key}"),
            )
            self._curve_items.append(item)

    def _regions_view_fit(self) -> None:
        if not all(
            region.isVisible()
            for region in (self.pre_region, self.burn_region, self.post_region)
        ):
            return
        regions = self.regions()
        view_start = float(regions["pre"][0])
        view_end = float(regions["post"][1])
        if view_start >= view_end:
            return
        self.plot_widget.setXRange(view_start, view_end, padding=0.02)

        values: list[np.ndarray] = []
        uncorrected_dataset = self._calibrated_dataset or self._raw_dataset
        if self.curve_checks["uncorrected"].isChecked() and uncorrected_dataset is not None:
            channel_id = (
                "force_calibrated"
                if "force_calibrated" in uncorrected_dataset.channels
                else "thrust_raw"
            )
            mask = (uncorrected_dataset.time >= view_start) & (
                uncorrected_dataset.time <= view_end
            )
            values.append(uncorrected_dataset.channel(channel_id).values[mask])
        if self.curve_checks["corrected"].isChecked() and self._processed_dataset is not None:
            channel_id = (
                "thrust_processed"
                if "thrust_processed" in self._processed_dataset.channels
                else "thrust_corrected"
            )
            if channel_id in self._processed_dataset.channels:
                mask = (self._processed_dataset.time >= view_start) & (
                    self._processed_dataset.time <= view_end
                )
                values.append(self._processed_dataset.channel(channel_id).values[mask])
        finite_values = [array[np.isfinite(array)] for array in values if array.size]
        finite_values = [array for array in finite_values if array.size]
        if finite_values:
            minimum = min(float(np.min(array)) for array in finite_values)
            maximum = max(float(np.max(array)) for array in finite_values)
            if minimum == maximum:
                padding = max(abs(minimum) * 0.1, 1.0)
                minimum -= padding
                maximum += padding
            self.plot_widget.setYRange(minimum, maximum, padding=0.08)

    def clear_state(self) -> None:
        self._raw_dataset = None
        self._calibrated_dataset = None
        self._processed_dataset = None
        self._candidates.clear()
        for region in (self.pre_region, self.burn_region, self.post_region):
            region.setVisible(False)
        self._candidate_labels_update()
        self._plot_refresh()
