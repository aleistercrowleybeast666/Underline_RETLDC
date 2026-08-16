from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.app.settings import THEME_LIGHT, Theme_Normalize
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project_data import ChannelReference
from underline_retldc.core.regions import BurnCandidate
from underline_retldc.core.units import UnitDisplayMode, UnitDisplayMode_Normalize
from underline_retldc.gui.analysis_widgets import AnalysisPlotWidget
from underline_retldc.gui.schema_form import SchemaForm
from underline_retldc.gui.test_interval_widget import TestIntervalEditor
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class ProcessPage(QWidget):
    detect_requested = Signal()
    apply_requested = Signal()
    plugins_requested = Signal()
    regions_changed = Signal(object)
    candidate_selected = Signal(int)
    primary_thrust_changed = Signal(object)
    thrust_polarity_changed = Signal(int)
    select_thrust_requested = Signal()

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self._raw_dataset: Dataset | None = None
        self._calibrated_dataset: Dataset | None = None
        self._processed_dataset: Dataset | None = None
        self._input_channel_id: str | None = None
        self._thrust_references: dict[str, ChannelReference] = {}
        self._candidates: list[BurnCandidate] = []
        self._processors: tuple[Any, ...] = ()
        self._curve_items: list[Any] = []
        self._regions_syncing = False
        self._theme = THEME_LIGHT
        self._display_preferences: dict[str, str] = {}
        self._display_mode = UnitDisplayMode.ENGINEERING

        self.analysis_plot = AnalysisPlotWidget(
            translations,
            regions_movable=True,
        )
        # Compatibility aliases retained for extensions and existing tests.
        self.plot_widget = self.analysis_plot.plot_widget
        self.plot_legend = self.analysis_plot.legend
        self.pre_region = self.analysis_plot.pre_region
        self.burn_region = self.analysis_plot.active_region
        self.post_region = self.analysis_plot.post_region
        for region in (self.pre_region, self.burn_region, self.post_region):
            region.sigRegionChanged.connect(self._region_edits_refresh)
            region.sigRegionChangeFinished.connect(self._plot_regions_finished)
        self.analysis_plot.select_channel_requested.connect(
            self.select_thrust_requested
        )

        controls = QWidget()
        controls.setMinimumWidth(260)
        controls_layout = QVBoxLayout(controls)
        self.input_group = QGroupBox()
        input_layout = QVBoxLayout(self.input_group)
        self.input_label = QLabel()
        self.input_combo = StandardComboBox()
        self.input_combo.currentIndexChanged.connect(self._input_selection_changed)
        self.input_hint = QLabel()
        self.input_hint.setWordWrap(True)
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_combo)
        input_layout.addWidget(self.input_hint)
        controls_layout.addWidget(self.input_group)

        self.interval_editor = TestIntervalEditor(
            translations,
            detect_translation_key="process.detect_with_thrust",
        )
        self.interval_editor.detect_requested.connect(self.detect_requested.emit)
        self.interval_editor.fit_requested.connect(self._regions_view_fit)
        self.interval_editor.candidate_selected.connect(self.candidate_selected.emit)
        self.interval_editor.regions_changed.connect(
            self._interval_regions_changed
        )
        controls_layout.addWidget(self.interval_editor)
        # Compatibility aliases retained for existing extensions and tests.
        self.candidates_group = self.interval_editor
        self.regions_group = self.interval_editor
        self.detect_button = self.interval_editor.detect_button
        self.fit_button = self.interval_editor.fit_button
        self.candidate_combo = self.interval_editor.candidate_combo
        self.region_hint = self.interval_editor.region_hint
        self.region_labels = self.interval_editor.region_labels
        self.region_edits = dict(self.interval_editor.region_edits)
        self.region_edits["burn"] = self.region_edits["active_test"]
        self.region_use_checks = self.interval_editor.region_use_checks

        self.polarity_group = QGroupBox()
        polarity_layout = QFormLayout(self.polarity_group)
        self.polarity_label = QLabel()
        self.polarity_combo = StandardComboBox()
        self.polarity_combo.addItem("", 1)
        self.polarity_combo.addItem("", -1)
        self.polarity_combo.currentIndexChanged.connect(
            self._polarity_selection_changed
        )
        polarity_layout.addRow(self.polarity_label, self.polarity_combo)
        controls_layout.addWidget(self.polarity_group)

        self.curves_group = QGroupBox()
        curves_layout = QVBoxLayout(self.curves_group)
        self.curve_checks: dict[str, QCheckBox] = {}
        for key in ("uncorrected", "corrected"):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._plot_refresh)
            self.curve_checks[key] = checkbox
            curves_layout.addWidget(checkbox)
        self.reset_chart_button = QPushButton()
        self.reset_chart_button.clicked.connect(self.analysis_plot.reset_view)
        curves_layout.addWidget(self.reset_chart_button)
        controls_layout.addWidget(self.curves_group)

        self.baseline_status_group = QGroupBox()
        baseline_status_layout = QFormLayout(self.baseline_status_group)
        self.baseline_status_labels = {"pre": QLabel(), "post": QLabel()}
        self.baseline_status_values = {"pre": QLabel("—"), "post": QLabel("—")}
        for name in ("pre", "post"):
            baseline_status_layout.addRow(
                self.baseline_status_labels[name], self.baseline_status_values[name]
            )
        controls_layout.addWidget(self.baseline_status_group)

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

        self.controls_widget = controls
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(controls)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.curves_group.setTitle(t("process.curves"))
        self.input_group.setTitle(t("primary_channels.title"))
        self.input_label.setText(t("workspace.thrust_data"))
        self.polarity_group.setTitle(t("process.thrust_polarity"))
        self.polarity_label.setText(t("process.polarity"))
        self.polarity_combo.setItemText(0, t("process.polarity_positive"))
        self.polarity_combo.setItemText(1, t("process.polarity_reversed"))
        for key, checkbox in self.curve_checks.items():
            checkbox.setText(t(f"process.{key}"))
        self.reset_chart_button.setText(t("workspace.reset_chart"))
        self.interval_editor.retranslate()
        self.processing_group.setTitle(t("page.process"))
        self.compensation_label.setText(t("process.enable_baseline"))
        self.plugins_button.setText(t("process.plugins"))
        self.apply_button.setText(t("process.apply"))
        self.baseline_status_group.setTitle(t("process.baseline_status"))
        self.baseline_status_labels["pre"].setText(t("process.pre_baseline"))
        self.baseline_status_labels["post"].setText(t("process.post_baseline"))
        self.analysis_plot.set_axis(
            x_label=t("common.time"),
            y_label=t("primary_channels.thrust"),
        )
        self.analysis_plot.empty_button.setText(t("workspace.select_thrust"))
        selected_processor = self.processor_id()
        processor_values = (
            self.processor_form.values() if self.processor_form.field_names else {}
        )
        self._processors_populate(selected_processor)
        self.processor_form.set_values(processor_values)
        self.processor_form.retranslate()
        self._plot_refresh()

    def set_datasets(
        self,
        raw_dataset: Dataset | None,
        calibrated_dataset: Dataset | None,
        processed_dataset: Dataset | None,
        *,
        input_channel_id: str | None = None,
    ) -> None:
        self._raw_dataset = raw_dataset
        self._calibrated_dataset = calibrated_dataset
        self._processed_dataset = processed_dataset
        self._input_channel_id = input_channel_id
        self.input_hint.setText(
            ""
            if input_channel_id is not None
            else self._translations.translate("workspace.no_primary_thrust")
        )
        self.apply_button.setEnabled(input_channel_id is not None)
        self.interval_editor.set_detection_enabled(input_channel_id is not None)
        self._plot_refresh()

    def set_thrust_choices(
        self,
        choices: tuple[tuple[str, object], ...],
        selected: object | None,
    ) -> None:
        self.input_combo.blockSignals(True)
        self.input_combo.clear()
        self._thrust_references.clear()
        self.input_combo.addItem(
            self._translations.translate("primary_channels.none"),
            None,
        )
        for label, reference in choices:
            if not isinstance(reference, ChannelReference):
                continue
            self._thrust_references[reference.stable_id] = reference
            self.input_combo.addItem(label, reference.stable_id)
        selected_id = selected.stable_id if isinstance(selected, ChannelReference) else None
        index = self.input_combo.findData(selected_id)
        self.input_combo.setCurrentIndex(max(0, index))
        self.input_combo.blockSignals(False)

    def _input_selection_changed(self, _index: int) -> None:
        stable_id = self.input_combo.currentData()
        self.primary_thrust_changed.emit(
            self._thrust_references.get(str(stable_id)) if stable_id else None
        )

    def _polarity_selection_changed(self, _index: int) -> None:
        polarity = int(self.polarity_combo.currentData())
        if polarity not in {-1, 1}:
            raise ValueError("Thrust polarity must be +1 or -1")
        self.thrust_polarity_changed.emit(polarity)

    def thrust_polarity(self) -> int:
        polarity = int(self.polarity_combo.currentData())
        if polarity not in {-1, 1}:
            raise ValueError("Thrust polarity must be +1 or -1")
        return polarity

    def set_thrust_polarity(self, polarity: int) -> None:
        normalized = int(polarity)
        if normalized not in {-1, 1}:
            raise ValueError("Thrust polarity must be +1 or -1")
        index = self.polarity_combo.findData(normalized)
        if index < 0:
            raise ValueError(f"Unsupported Thrust polarity {normalized!r}")
        self.polarity_combo.blockSignals(True)
        self.polarity_combo.setCurrentIndex(index)
        self.polarity_combo.blockSignals(False)

    def set_candidates(
        self,
        candidates: list[BurnCandidate],
        *,
        selected_index: int = 0,
    ) -> None:
        self._candidates = list(candidates)
        self.interval_editor.set_candidates(
            candidates,
            selected_index=selected_index,
        )

    def _candidate_labels_update(self) -> None:
        self.interval_editor.set_candidates(
            self._candidates,
            selected_index=max(0, self.candidate_combo.currentIndex()),
        )

    def _candidate_selected(self, index: int) -> None:
        if index < 0 or index >= len(self._candidates):
            return
        self.candidate_selected.emit(index)

    def set_regions(
        self,
        regions: Mapping[str, list[float] | tuple[float, float] | None],
        *,
        emit: bool = False,
    ) -> None:
        self.interval_editor.set_regions(regions)
        payload = self.interval_editor.regions()
        self._regions_syncing = True
        self.analysis_plot.set_regions(payload)
        self._regions_syncing = False
        if emit:
            self.regions_changed.emit(payload)

    def _interval_regions_changed(
        self,
        regions: Mapping[str, list[float] | tuple[float, float] | None],
    ) -> None:
        if self._regions_syncing:
            return
        self._regions_syncing = True
        self.analysis_plot.set_regions(regions)
        self._regions_syncing = False
        self.regions_changed.emit(dict(regions))

    def _region_edits_refresh(self) -> None:
        if self._regions_syncing or not self.burn_region.isVisible():
            return
        self._regions_syncing = True
        self.interval_editor.set_regions(
            {
                "pre": (
                    list(map(float, self.pre_region.getRegion()))
                    if self.pre_region.isVisible()
                    else None
                ),
                "active_test": list(map(float, self.burn_region.getRegion())),
                "post": (
                    list(map(float, self.post_region.getRegion()))
                    if self.post_region.isVisible()
                    else None
                ),
            }
        )
        self._regions_syncing = False

    def _plot_regions_finished(self) -> None:
        self._region_edits_refresh()
        self.interval_editor.mark_manually_modified()
        payload = self.interval_editor.regions()
        if payload:
            self.regions_changed.emit(payload)

    def regions(self) -> dict[str, list[float] | None]:
        return self.interval_editor.regions()

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

    @property
    def input_channel_id(self) -> str | None:
        return self._input_channel_id

    def processing_config(self) -> dict[str, Any]:
        processor = self._selected_processor()
        if processor is None:
            return {}
        schema = processor.config_schema()
        raw_properties = schema.get("properties", {})
        if not isinstance(raw_properties, Mapping):
            raise ValueError("Processor config schema properties must be an object")
        config = self.processor_form.values()
        regions = self.regions()
        processor_regions = {
            "pre": regions.get("pre"),
            "burn": regions.get("active_test"),
            "post": regions.get("post"),
        }
        injected = {
            "processor.selection": True,
            "thrust_analysis.input_channel": self._input_channel_id,
            "thrust_analysis.regions": processor_regions,
        }
        if self._input_channel_id is None:
            raise ValueError("The Project has no Primary Thrust Channel")
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

    def set_theme(self, theme: str) -> None:
        self._theme = Theme_Normalize(theme)
        self.analysis_plot.apply_theme(self._theme)

    def set_display_preferences(self, preferences: Mapping[str, str]) -> None:
        self._display_preferences = dict(preferences)
        self._plot_refresh()

    def set_display_mode(self, mode: UnitDisplayMode | str) -> None:
        self._display_mode = UnitDisplayMode_Normalize(mode)
        self.analysis_plot.set_display_mode(self._display_mode)
        self._plot_refresh()

    def set_segmentation_reference(
        self,
        reference_name: str,
        *,
        manually_modified: bool,
    ) -> None:
        self.interval_editor.set_reference(
            reference_name,
            manually_modified=manually_modified,
        )

    def _plot_refresh(self) -> None:
        self.analysis_plot.clear_series()
        self._curve_items.clear()
        uncorrected_dataset = self._calibrated_dataset or self._raw_dataset
        uncorrected_channel = self._input_channel_id or ""
        corrected_channel = (
            "thrust_processed"
            if self._processed_dataset is not None
            and "thrust_processed" in self._processed_dataset.channels
            else "thrust_corrected"
        )
        curves: list[tuple[str, Dataset | None, str, int]] = [
            ("uncorrected", uncorrected_dataset, uncorrected_channel, 0),
            ("corrected", self._processed_dataset, corrected_channel, 1),
        ]
        for key, dataset, channel_id, style_index in curves:
            if (
                not self.curve_checks[key].isChecked()
                or dataset is None
                or channel_id not in dataset.channels
            ):
                continue
            item = self.analysis_plot.add_series(
                dataset.project_time,
                dataset.channel(channel_id).display_values(
                    preferences=self._display_preferences,
                    display_mode=self._display_mode,
                ),
                name=self._translations.translate(f"process.{key}"),
                style_index=style_index,
            )
            self._curve_items.append(item)
            display_unit = dataset.channel(channel_id).effective_display_unit(
                self._display_preferences,
                display_mode=self._display_mode,
            )
            self.analysis_plot.set_axis(
                x_label=self._translations.translate("common.time"),
                y_label=self._translations.translate("primary_channels.thrust"),
                y_unit=display_unit,
            )
        missing_input = self._input_channel_id is None or uncorrected_dataset is None
        self.analysis_plot.set_empty_state(
            (
                self._translations.translate("workspace.no_primary_thrust")
                if missing_input
                else None
            ),
            button_text=self._translations.translate("workspace.select_thrust"),
            button_visible=True,
        )

    def _regions_view_fit(self) -> None:
        if not self.burn_region.isVisible():
            return
        regions = self.regions()
        pre = regions["pre"]
        burn = regions["active_test"]
        post = regions["post"]
        assert burn is not None
        view_start = float(pre[0] if pre is not None else burn[0])
        view_end = float(post[1] if post is not None else burn[1])
        if view_start >= view_end:
            return
        values: list[np.ndarray] = []
        uncorrected_dataset = self._calibrated_dataset or self._raw_dataset
        if self.curve_checks["uncorrected"].isChecked() and uncorrected_dataset is not None:
            channel_id = self._input_channel_id or ""
            if channel_id not in uncorrected_dataset.channels:
                channel_id = ""
            if not channel_id:
                return
            project_time = uncorrected_dataset.project_time
            mask = (project_time >= view_start) & (
                project_time <= view_end
            )
            values.append(
                uncorrected_dataset.channel(channel_id).display_values(
                    preferences=self._display_preferences,
                    display_mode=self._display_mode,
                )[mask]
            )
        if self.curve_checks["corrected"].isChecked() and self._processed_dataset is not None:
            channel_id = (
                "thrust_processed"
                if "thrust_processed" in self._processed_dataset.channels
                else "thrust_corrected"
            )
            if channel_id in self._processed_dataset.channels:
                project_time = self._processed_dataset.project_time
                mask = (project_time >= view_start) & (
                    project_time <= view_end
                )
                values.append(
                    self._processed_dataset.channel(channel_id).display_values(
                        preferences=self._display_preferences,
                        display_mode=self._display_mode,
                    )[mask]
                )
        self.analysis_plot.fit_view(
            values=tuple(values),
            regions=regions,
        )

    def set_processing_metadata(self, metadata: Mapping[str, Any] | None) -> None:
        values = dict(metadata or {})
        for name in ("pre", "post"):
            baseline = values.get("baseline_start" if name == "pre" else "baseline_end")
            source = values.get(f"baseline_{name}_source")
            if baseline is None:
                text = "—"
            elif source == "assumed_zero":
                text = self._translations.translate(
                    "process.baseline_assumed", value=f"{float(baseline):.8g}"
                )
            else:
                text = self._translations.translate(
                    "process.baseline_measured", value=f"{float(baseline):.8g}"
                )
            self.baseline_status_values[name].setText(text)

    def clear_state(self) -> None:
        self._raw_dataset = None
        self._calibrated_dataset = None
        self._processed_dataset = None
        self._input_channel_id = None
        self._candidates.clear()
        self.interval_editor.clear()
        for region in (self.pre_region, self.burn_region, self.post_region):
            region.setVisible(False)
        self.set_processing_metadata(None)
        self._plot_refresh()
