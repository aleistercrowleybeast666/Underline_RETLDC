from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.measurement_statistics import (
    MeasurementStatistics,
    MeasurementStatistics_Calculate,
)
from underline_retldc.core.project_data import ChannelReference
from underline_retldc.core.regions import ActivityCandidate
from underline_retldc.core.units import (
    Quantity_Dimension,
    Unit_AreConvertible,
    Unit_ValueFormat,
    UnitDisplayMode,
    UnitDisplayMode_Normalize,
)
from underline_retldc.gui.analysis_widgets import (
    AnalysisPlotWidget,
    AnalysisResultsPanel,
    AnalysisWorkspaceShell,
)
from underline_retldc.gui.pages.analyze_page import AnalyzePage
from underline_retldc.gui.pages.import_page import ImportPage
from underline_retldc.gui.pages.process_page import ProcessPage
from underline_retldc.gui.pages.setup_page import SetupPage
from underline_retldc.gui.primary_channels_widget import PrimaryChannelsWidget
from underline_retldc.gui.test_interval_widget import TestIntervalEditor
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class ProjectWorkspacePage(QWidget):
    def __init__(
        self,
        translations: TranslationService,
        import_page: ImportPage,
        setup_page: SetupPage,
    ) -> None:
        super().__init__()
        self._translations = translations
        self.import_page = import_page
        self.setup_page = setup_page
        self.primary_channels = PrimaryChannelsWidget(translations)

        setup_scroll = QScrollArea()
        setup_scroll.setWidgetResizable(True)
        setup_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        project_settings = QWidget()
        project_settings_layout = QVBoxLayout(project_settings)
        project_settings_layout.setContentsMargins(0, 0, 0, 0)
        project_settings_layout.addWidget(self.primary_channels)
        project_settings_layout.addWidget(setup_page)
        project_settings_layout.addStretch(1)
        setup_scroll.setWidget(project_settings)

        import_scroll = QScrollArea()
        import_scroll.setWidgetResizable(True)
        import_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        import_scroll.setWidget(import_page)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(import_scroll)
        splitter.addWidget(setup_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 480])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        self.retranslate()

    def retranslate(self) -> None:
        self.import_page.retranslate()
        self.primary_channels.retranslate()
        self.setup_page.retranslate()


class ThrustAnalysisWorkspacePage(QWidget):
    def __init__(
        self,
        process_page: ProcessPage,
        analyze_page: AnalyzePage,
    ) -> None:
        super().__init__()
        self.process_page = process_page
        self.analyze_page = analyze_page
        self.shell = AnalysisWorkspaceShell(
            process_page,
            process_page.analysis_plot,
            analyze_page,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

    def retranslate(self) -> None:
        self.process_page.retranslate()
        self.analyze_page.retranslate()


@dataclass(frozen=True, slots=True)
class WorkspaceSeries:
    reference: ChannelReference
    dataset: Dataset
    channel_id: str
    label: str
    auxiliary: bool = False


class MeasurementWorkspacePage(QWidget):
    """Binding-driven workspace built from the shared analysis shell and plot."""

    primary_channel_changed = Signal(object)
    temperature_channels_changed = Signal(object)
    select_channel_requested = Signal()
    detect_requested = Signal()
    candidate_selected = Signal(int)
    regions_changed = Signal(object)

    def __init__(
        self,
        translations: TranslationService,
        *,
        dimension: str | None,
        empty_key: str,
        title_key: str,
        selection_mode: str,
        metric_mode: str,
        semantic_roles: Iterable[str] = (),
        allow_auxiliary: bool = False,
    ) -> None:
        super().__init__()
        if selection_mode not in {"single", "multiple", "explorer"}:
            raise ValueError(f"Unknown measurement selection mode {selection_mode!r}")
        self._translations = translations
        self._dimension = dimension
        self._semantic_roles = frozenset(str(role) for role in semantic_roles)
        self._empty_key = empty_key
        self._title_key = title_key
        self._selection_mode = selection_mode
        self._metric_mode = metric_mode
        self._allow_auxiliary = allow_auxiliary
        self._series: tuple[WorkspaceSeries, ...] = ()
        self._series_by_id: dict[str, WorkspaceSeries] = {}
        self._display_preferences: dict[str, str] = {}
        self._display_mode = UnitDisplayMode.ENGINEERING
        self._regions: dict[str, list[float] | tuple[float, float] | None] = {}
        self._syncing = False
        self._regions_syncing = False

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        self.channel_group = QGroupBox()
        channel_layout = QVBoxLayout(self.channel_group)
        self.channel_label = QLabel()
        self.channel_combo = StandardComboBox()
        self.channel_combo.currentIndexChanged.connect(self._selection_changed)
        self.temperature_list = QListWidget()
        self.temperature_list.setMinimumHeight(170)
        self.temperature_list.itemChanged.connect(self._selection_changed)
        self.channel_summary = QLabel()
        self.channel_summary.setWordWrap(True)
        channel_layout.addWidget(self.channel_label)
        channel_layout.addWidget(self.channel_combo)
        channel_layout.addWidget(self.temperature_list)
        channel_layout.addWidget(self.channel_summary)
        controls_layout.addWidget(self.channel_group)

        self.interval_editor: TestIntervalEditor | None = None
        if self._metric_mode == "pressure":
            self.interval_editor = TestIntervalEditor(translations)
            self.interval_editor.detect_requested.connect(self.detect_requested.emit)
            self.interval_editor.fit_requested.connect(self._fit_view)
            self.interval_editor.candidate_selected.connect(
                self.candidate_selected.emit
            )
            self.interval_editor.regions_changed.connect(
                self._interval_regions_changed
            )
            controls_layout.addWidget(self.interval_editor)

        self.view_group = QGroupBox()
        view_layout = QVBoxLayout(self.view_group)
        self.display_unit_text = QLabel()
        self.display_unit_text.setWordWrap(True)
        self.segmentation_status = QLabel()
        self.segmentation_status.setWordWrap(True)
        self.show_auxiliary_check = QCheckBox()
        self.show_auxiliary_check.toggled.connect(self._series_controls_rebuild)
        self.fit_button = QPushButton()
        self.fit_button.clicked.connect(self._fit_view)
        view_layout.addWidget(self.display_unit_text)
        view_layout.addWidget(self.segmentation_status)
        view_layout.addWidget(self.show_auxiliary_check)
        view_layout.addWidget(self.fit_button)
        controls_layout.addWidget(self.view_group)
        controls_layout.addStretch(1)

        self.analysis_plot = AnalysisPlotWidget(
            translations,
            regions_movable=self._metric_mode == "pressure",
        )
        self.analysis_plot.select_channel_requested.connect(
            self.select_channel_requested
        )
        # Compatibility aliases for extensions written against the first GUI.
        self.plot_widget = self.analysis_plot.plot_widget
        self.pre_region = self.analysis_plot.pre_region
        self.active_region = self.analysis_plot.active_region
        self.post_region = self.analysis_plot.post_region
        if self._metric_mode == "pressure":
            for region in (
                self.pre_region,
                self.active_region,
                self.post_region,
            ):
                region.sigRegionChanged.connect(self._plot_regions_sync)
                region.sigRegionChangeFinished.connect(
                    self._plot_regions_finished
                )

        self.results_panel = AnalysisResultsPanel()
        self.statistics_group = self.results_panel
        self.metrics_table = self.results_panel.table
        self.shell = AnalysisWorkspaceShell(
            controls,
            self.analysis_plot,
            self.results_panel,
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

        self.channel_combo.setVisible(selection_mode != "multiple")
        self.temperature_list.setVisible(selection_mode == "multiple")
        self.show_auxiliary_check.setVisible(allow_auxiliary)
        self.retranslate()

    def retranslate(self) -> None:
        translate = self._translations.translate
        self.channel_group.setTitle(
            translate(
                "workspace.measurement_channel"
                if self._selection_mode == "explorer"
                else "primary_channels.title"
            )
        )
        if self._selection_mode == "multiple":
            self.channel_label.setText(translate("primary_channels.temperature"))
        elif self._metric_mode == "pressure":
            self.channel_label.setText(translate("primary_channels.pressure"))
        else:
            self.channel_label.setText(translate("setup.channel"))
        self.view_group.setTitle(translate("workspace.view_controls"))
        self.fit_button.setText(translate("process.fit_regions"))
        self.show_auxiliary_check.setText(translate("workspace.show_auxiliary"))
        self.results_panel.setTitle(translate(self._title_key))
        self.results_panel.set_headers(
            translate("workspace.metric"),
            translate("common.value"),
        )
        if self.interval_editor is not None:
            self.interval_editor.retranslate()
        self.analysis_plot.set_axis(
            x_label=translate("common.time"),
            y_label=self._axis_label(()),
        )
        self._plot_refresh()

    def _axis_label(self, selected: tuple[WorkspaceSeries, ...]) -> str:
        translate = self._translations.translate
        if self._metric_mode == "pressure":
            return translate("primary_channels.pressure")
        if self._metric_mode == "temperature":
            return translate("quantity.temperature")
        if selected:
            channel = selected[0].dataset.channel(selected[0].channel_id)
            return str(channel.name or channel.id)
        return translate("workspace.measurement_channel")

    def set_theme(self, theme: str) -> None:
        self.analysis_plot.apply_theme(theme)

    def set_series(
        self,
        series: Iterable[WorkspaceSeries],
        *,
        selected: ChannelReference | Iterable[ChannelReference] | None = None,
    ) -> None:
        self._series = tuple(series)
        self._series_by_id = {
            item.reference.stable_id: item for item in self._series
        }
        if len(self._series_by_id) != len(self._series):
            raise ValueError("Workspace series references must be unique")
        if selected is None:
            selected_ids: set[str] = set()
        elif isinstance(selected, ChannelReference):
            selected_ids = {selected.stable_id}
        else:
            selected_ids = {item.stable_id for item in selected}
        self._series_controls_rebuild(selected_ids=selected_ids)

    def selected_references(self) -> tuple[ChannelReference, ...]:
        return tuple(item.reference for item in self._selected_series())

    def _available_series(self) -> tuple[WorkspaceSeries, ...]:
        if not self._allow_auxiliary or self.show_auxiliary_check.isChecked():
            return self._series
        return tuple(item for item in self._series if not item.auxiliary)

    def _series_controls_rebuild(
        self,
        _checked: bool | None = None,
        *,
        selected_ids: set[str] | None = None,
    ) -> None:
        if selected_ids is None:
            selected_ids = {
                item.reference.stable_id for item in self._selected_series()
            }
        available = self._available_series()
        self._syncing = True
        self.channel_combo.clear()
        self.temperature_list.clear()
        if self._selection_mode == "single":
            self.channel_combo.addItem(
                self._translations.translate("primary_channels.none"),
                None,
            )
        for item in available:
            stable_id = item.reference.stable_id
            self.channel_combo.addItem(item.label, stable_id)
            list_item = QListWidgetItem(item.label)
            list_item.setData(Qt.ItemDataRole.UserRole, stable_id)
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(
                Qt.CheckState.Checked
                if stable_id in selected_ids
                else Qt.CheckState.Unchecked
            )
            self.temperature_list.addItem(list_item)
        if self._selection_mode != "multiple":
            selected_id = next(iter(selected_ids), None)
            index = self.channel_combo.findData(selected_id)
            if index < 0 and self._selection_mode == "explorer" and available:
                index = 0
            self.channel_combo.setCurrentIndex(index)
        self._syncing = False
        self._plot_refresh()

    def _selected_series(self) -> tuple[WorkspaceSeries, ...]:
        if self._selection_mode == "multiple":
            identifiers = tuple(
                str(self.temperature_list.item(index).data(Qt.ItemDataRole.UserRole))
                for index in range(self.temperature_list.count())
                if self.temperature_list.item(index).checkState()
                == Qt.CheckState.Checked
            )
        else:
            value = self.channel_combo.currentData()
            identifiers = (str(value),) if value else ()
        return tuple(
            self._series_by_id[identifier]
            for identifier in identifiers
            if identifier in self._series_by_id
        )

    def _selection_changed(self, _value: object = None) -> None:
        if self._syncing:
            return
        selected = self._selected_series()
        self._plot_refresh()
        if self._selection_mode == "single":
            self.primary_channel_changed.emit(
                selected[0].reference if selected else None
            )
        elif self._selection_mode == "multiple":
            self.temperature_channels_changed.emit(
                tuple(item.reference for item in selected)
            )

    def set_datasets(self, datasets: Iterable[Dataset]) -> None:
        """Compatibility adapter; application code should pass explicit bindings."""
        generated: list[WorkspaceSeries] = []
        for dataset_index, dataset in enumerate(datasets):
            source_id = dataset.source_id or f"source_{dataset_index + 1}"
            stream_id = dataset.stream_id or f"stream_{dataset_index + 1}"
            for channel in dataset.channels.values():
                if (
                    self._dimension is not None
                    and Quantity_Dimension(channel.quantity) != self._dimension
                ):
                    continue
                if self._semantic_roles and channel.semantic_role not in self._semantic_roles:
                    continue
                reference = ChannelReference(source_id, stream_id, channel.id)
                generated.append(
                    WorkspaceSeries(
                        reference=reference,
                        dataset=dataset,
                        channel_id=channel.id,
                        label=f"{stream_id} · {channel.name} [{channel.data_unit}]",
                        auxiliary=(
                            channel.semantic_role == "auxiliary"
                            or channel.metadata.get("workspace_category") == "other"
                        ),
                    )
                )
        selected: ChannelReference | tuple[ChannelReference, ...] | None
        if self._selection_mode == "multiple":
            selected = tuple(item.reference for item in generated)
        elif generated:
            selected = generated[0].reference
        else:
            selected = None
        self.set_series(generated, selected=selected)

    def set_regions(
        self,
        regions: Mapping[str, list[float] | tuple[float, float] | None],
    ) -> None:
        self._regions = dict(regions)
        self._regions_syncing = True
        if self.interval_editor is not None:
            if self._regions:
                self.interval_editor.set_regions(self._regions)
            else:
                self.interval_editor.clear()
        self.analysis_plot.set_regions(self._regions)
        self._regions_syncing = False
        self._results_refresh()
        self._segmentation_status_refresh()

    def set_candidates(
        self,
        candidates: list[ActivityCandidate] | tuple[ActivityCandidate, ...],
        *,
        selected_index: int = 0,
    ) -> None:
        if self.interval_editor is not None:
            self.interval_editor.set_candidates(
                candidates,
                selected_index=selected_index,
            )

    def set_segmentation_reference(
        self,
        reference_name: str,
        *,
        manually_modified: bool,
    ) -> None:
        if self.interval_editor is not None:
            self.interval_editor.set_reference(
                reference_name,
                manually_modified=manually_modified,
            )

    def set_detection_enabled(self, enabled: bool) -> None:
        if self.interval_editor is not None:
            self.interval_editor.set_detection_enabled(enabled)

    def _interval_regions_changed(
        self,
        regions: Mapping[str, list[float] | tuple[float, float] | None],
    ) -> None:
        if self._regions_syncing:
            return
        self._regions = dict(regions)
        self._regions_syncing = True
        self.analysis_plot.set_regions(self._regions)
        self._regions_syncing = False
        self._results_refresh()
        self._segmentation_status_refresh()
        self.regions_changed.emit(dict(self._regions))

    def _plot_regions_sync(self) -> None:
        if (
            self._regions_syncing
            or self.interval_editor is None
            or not self.active_region.isVisible()
        ):
            return
        payload = {
            "pre": (
                list(map(float, self.pre_region.getRegion()))
                if self.pre_region.isVisible()
                else None
            ),
            "active_test": list(map(float, self.active_region.getRegion())),
            "post": (
                list(map(float, self.post_region.getRegion()))
                if self.post_region.isVisible()
                else None
            ),
        }
        self._regions_syncing = True
        self.interval_editor.set_regions(payload)
        self._regions_syncing = False
        self._regions = payload

    def _plot_regions_finished(self) -> None:
        if self.interval_editor is None:
            return
        self._plot_regions_sync()
        self.interval_editor.mark_manually_modified()
        self._results_refresh()
        self._segmentation_status_refresh()
        self.regions_changed.emit(dict(self._regions))

    def set_display_preferences(self, preferences: Mapping[str, str]) -> None:
        self._display_preferences = dict(preferences)
        self._plot_refresh()

    def set_display_mode(self, mode: UnitDisplayMode | str) -> None:
        self._display_mode = UnitDisplayMode_Normalize(mode)
        self.analysis_plot.set_display_mode(self._display_mode)
        self._plot_refresh()

    def _plot_refresh(self) -> None:
        selected = self._selected_series()
        self.analysis_plot.clear_series()
        display_units: set[str] = set()
        common_unit = ""
        if selected:
            first_channel = selected[0].dataset.channel(selected[0].channel_id)
            common_unit = first_channel.effective_display_unit(
                self._display_preferences,
                display_mode=self._display_mode,
            )
        for style_index, item in enumerate(selected):
            channel = item.dataset.channel(item.channel_id)
            own_unit = channel.effective_display_unit(
                self._display_preferences,
                display_mode=self._display_mode,
            )
            display_unit = (
                common_unit
                if common_unit
                and Unit_AreConvertible(channel.data_unit, common_unit)
                else own_unit
            )
            display_units.add(display_unit)
            self.analysis_plot.add_series(
                item.dataset.project_time,
                channel.display_values(
                    display_unit,
                    preferences=self._display_preferences,
                    display_mode=self._display_mode,
                ),
                name=item.label,
                style_index=style_index,
            )
        unit = next(iter(display_units)) if len(display_units) == 1 else ""
        self.analysis_plot.set_axis(
            x_label=self._translations.translate("common.time"),
            y_label=self._axis_label(selected),
            y_unit=unit,
        )
        self.analysis_plot.set_regions(self._regions)
        self.analysis_plot.set_empty_state(
            None if selected else self._translations.translate(self._empty_key),
            button_text=self._translations.translate("workspace.select_channel"),
            button_visible=self._selection_mode != "explorer",
        )
        self.display_unit_text.setText(
            self._translations.translate(
                "workspace.display_unit",
                unit=unit or self._translations.translate("common.multiple"),
            )
            if selected
            else ""
        )
        self.channel_summary.setText(
            self._translations.translate(
                "workspace.selected_count",
                count=len(selected),
            )
            if self._selection_mode == "multiple"
            else (selected[0].label if selected else "")
        )
        self._results_refresh()
        self._segmentation_status_refresh()

    def _active_interval(self) -> tuple[float, float] | None:
        active = self._regions.get("active_test", self._regions.get("burn"))
        if active is None or len(active) != 2:
            return None
        return float(active[0]), float(active[1])

    def _value_format(self, value: float | None, unit: str = "") -> str:
        suffix = f" {unit}" if unit else ""
        return (
            Unit_ValueFormat(
                value,
                display_mode=self._display_mode,
            )
            + suffix
        )

    def _statistics_for(
        self,
        item: WorkspaceSeries,
        display_unit: str | None = None,
    ) -> tuple[MeasurementStatistics, str]:
        channel = item.dataset.channel(item.channel_id)
        unit = display_unit or channel.effective_display_unit(
            self._display_preferences,
            display_mode=self._display_mode,
        )
        statistics = MeasurementStatistics_Calculate(
            item.dataset.project_time,
            channel.display_values(
                unit,
                preferences=self._display_preferences,
                display_mode=self._display_mode,
            ),
            self._active_interval(),
        )
        return statistics, unit

    def _results_refresh(self) -> None:
        translate = self._translations.translate
        rows: list[tuple[str, str]] = []
        selected = self._selected_series()
        common_unit = None
        if selected:
            first = selected[0].dataset.channel(selected[0].channel_id)
            common_unit = first.effective_display_unit(
                self._display_preferences,
                display_mode=self._display_mode,
            )
        for item in selected:
            channel = item.dataset.channel(item.channel_id)
            target_unit = (
                common_unit
                if common_unit
                and Unit_AreConvertible(channel.data_unit, common_unit)
                else None
            )
            statistics, unit = self._statistics_for(item, target_unit)
            prefix = f"{item.label} · " if self._selection_mode == "multiple" else ""
            if self._metric_mode == "pressure":
                values = (
                    ("test_start_value", statistics.test_start_value, unit),
                    ("active_mean", statistics.active_mean, unit),
                    ("active_maximum", statistics.active_maximum, unit),
                    (
                        "active_time_to_maximum_s",
                        statistics.active_time_to_maximum_s,
                        "s",
                    ),
                    ("active_minimum", statistics.active_minimum, unit),
                )
            elif self._metric_mode == "temperature":
                values = (
                    ("test_start_value", statistics.test_start_value, unit),
                    ("active_maximum", statistics.active_maximum, unit),
                    ("full_maximum", statistics.full_maximum, unit),
                    ("full_maximum_time_s", statistics.full_maximum_time_s, "s"),
                )
            else:
                values = (
                    ("active_minimum", statistics.active_minimum, unit),
                    ("active_mean", statistics.active_mean, unit),
                    ("active_maximum", statistics.active_maximum, unit),
                    ("full_maximum", statistics.full_maximum, unit),
                )
            rows.extend(
                (
                    prefix + translate(f"workspace.statistic.{key}"),
                    self._value_format(value, value_unit),
                )
                for key, value, value_unit in values
            )
        self.results_panel.set_rows(tuple(rows))

    def _segmentation_status_refresh(self) -> None:
        active = self._active_interval()
        self.segmentation_status.setText(
            self._translations.translate(
                "workspace.segmentation_active",
                start=f"{active[0]:.8g}",
                end=f"{active[1]:.8g}",
            )
            if active is not None
            else self._translations.translate("workspace.segmentation_missing")
        )

    def _fit_view(self) -> None:
        selected = self._selected_series()
        if not selected:
            return
        times = tuple(item.dataset.project_time for item in selected)
        values = tuple(
            item.dataset.channel(item.channel_id).display_values(
                (
                    selected[0]
                    .dataset.channel(selected[0].channel_id)
                    .effective_display_unit(
                        self._display_preferences,
                        display_mode=self._display_mode,
                    )
                ),
                preferences=self._display_preferences,
                display_mode=self._display_mode,
            )
            for item in selected
        )
        # Thermal lag can peak after ACTIVE, so Temperature defaults to full record.
        fit_regions = {} if self._metric_mode == "temperature" else self._regions
        self.analysis_plot.fit_view(
            time=np.concatenate(times),
            values=values,
            regions=fit_regions,
        )


class ChamberPressureWorkspacePage(MeasurementWorkspacePage):
    def __init__(self, translations: TranslationService) -> None:
        super().__init__(
            translations,
            dimension="pressure",
            empty_key="workspace.no_pressure_channel",
            title_key="page.chamber_pressure",
            selection_mode="single",
            metric_mode="pressure",
            semantic_roles=("chamber_pressure",),
        )


class TemperatureWorkspacePage(MeasurementWorkspacePage):
    def __init__(self, translations: TranslationService) -> None:
        super().__init__(
            translations,
            dimension="temperature",
            empty_key="workspace.no_temperature_channel",
            title_key="page.temperature",
            selection_mode="multiple",
            metric_mode="temperature",
        )


class DataExplorerWorkspacePage(MeasurementWorkspacePage):
    def __init__(self, translations: TranslationService) -> None:
        super().__init__(
            translations,
            dimension=None,
            empty_key="workspace.no_channel",
            title_key="page.data_explorer",
            selection_mode="explorer",
            metric_mode="generic",
            allow_auxiliary=True,
        )


# Retained for extensions that imported the pre-specialization name.
AnalysisWorkspacePage = ThrustAnalysisWorkspacePage
