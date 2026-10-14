from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from underline_retldc.app.settings import SettingsService
from underline_retldc.core.channel import Channel
from underline_retldc.core.curve_display import DisplayCurve
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project import Project_Load, Project_Save
from underline_retldc.core.project_data import (
    ChannelReference,
    ProjectData,
    Source,
    SourceDisplayTransform,
    SourceKind,
    Stream,
)
from underline_retldc.core.source_analysis import SourceAnalysisConfig
from underline_retldc.core.units import UnitDisplayMode
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.gui.plot_view import PlotViews_Capture, PlotViews_Restore
from underline_retldc.i18n.service import TranslationService

ROOT = Path(__file__).resolve().parents[2]


def _wait(window: MainWindow) -> None:
    for _ in range(1000):
        QApplication.processEvents()
        QTest.qWait(10)
        if window._active_task is None:
            QTest.qWait(30)
            QApplication.processEvents()
            if window._active_task is None:
                return
    raise AssertionError("GUI task did not finish")


@pytest.fixture
def window(tmp_path: Path, monkeypatch) -> MainWindow:
    app = QApplication.instance() or QApplication([])
    result = MainWindow(
        TranslationService("en_US"), SettingsService(tmp_path / "settings.ini"),
        project_root=tmp_path, bundled_plugin_directory=ROOT / "plugins",
        user_plugin_directory=tmp_path / "user_plugins",
    )
    monkeypatch.setattr(result, "_tabular_preview_refresh", lambda *_args: None)
    errors: list[str] = []
    monkeypatch.setattr(result, "_error_show", lambda error: errors.append(str(error)))
    result._test_errors = errors
    assert app is not None
    return result


def _mapping(units: list[str]) -> dict:
    return {
        "delimiter": ",", "header_row": 1, "data_start_row": 2,
        "time": {"mode": "column", "column": 0, "unit": "s"},
        "columns": [
            {"column": 0, "usage": "time"},
            *[
                {"column": index + 1, "usage": "data", "channel_id": channel,
                 "quantity": quantity, "role": role, "unit": unit}
                for index, (channel, quantity, role, unit) in enumerate(zip(
                    ["f", "p", "t", "web"], ["force", "pressure", "temperature", "length"],
                    ["thrust", "chamber_pressure", "temperature", "auxiliary"], units, strict=True,
                ))
            ],
        ],
        "invalid_row_policy": "preserve",
    }


def _experimental_import(window: MainWindow, path: Path) -> None:
    path.write_text("time,f,p,t,web\n0,0,0,20,0\n1,1000,1000000,21,1\n"
                    "2,2000,2000000,22,2\n3,1000,1000000,23,3\n4,0,0,24,4\n",
                    encoding="utf-8")
    window.import_page.set_source_path(path)
    window.import_page.set_parser_id("builtin.parser.generic_delimited")
    _configure_mapping(window, path, ["N", "Pa", "°C", "mm"])
    window._source_parse()
    _wait(window)
    assert not window._test_errors


def _configure_mapping(window: MainWindow, path: Path, units: list[str]) -> None:
    config = _mapping(units)
    parser = window.registry.get("builtin.parser.generic_delimited")
    window.import_page.tabular_mapping_editor.set_preview(
        parser.preview(path, config), config=config,
    )


def _configure_theory_mapping(window: MainWindow, path: Path) -> None:
    config = _mapping(["kN", "Pa", "K", "m"])
    # Distinct saved mappings for the same bytes must not reuse another Source's Dataset.
    config["columns"][1]["column"] = 4
    config["columns"][4]["column"] = 1
    parser = window.registry.get("builtin.parser.generic_delimited")
    window.import_page.tabular_mapping_editor.set_preview(
        parser.preview(path, config), config=config,
    )


def test_theory_import_overlay_alignment_reopen_and_removal(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    exp_path = tmp_path / "exp.csv"
    _experimental_import(window, exp_path)
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window._processing_apply()
    _wait(window)
    window._analysis_calculate()
    _wait(window)
    window.chamber_pressure_page._analysis_calculate()
    window.temperature_page._analysis_calculate()
    bindings = window.session.project_data.primary_channels
    processing = window.session.processing_result
    analysis = window.session.analysis_result
    regions = dict(window.session.regions)
    candidates = list(window.session.candidates)
    selected_exports = window.export_dialog.selected_exporter_ids()
    expected_metrics = dict(analysis.metrics)
    pressure_rows = window.chamber_pressure_page.metrics_table.rowCount()
    exp_stream = window.session.project_data.streams[bindings.thrust.stream_id]

    theory_path = tmp_path / "theory.csv"
    theory_path.write_text("time,f,p,t,web\n8,0,0,293.15,0\n9,1,1000000,294.15,.001\n"
                           "10,,2000000,295.15,.002\n11,1,1000000,296.15,.003\n"
                           "13,0,0,297.15,.004\n", encoding="utf-8")
    original_bytes = theory_path.read_bytes()
    window.import_page.new_kind_combo.setCurrentIndex(
        window.import_page.new_kind_combo.findData("theoretical")
    )
    window.import_page.add_source_paths([theory_path])
    _configure_mapping(window, theory_path, ["kN", "Pa", "K", "m"])
    window._source_parse()
    _wait(window)
    assert not window._test_errors
    assert window.session.processing_result is processing
    assert window.session.analysis_result is analysis
    assert window.session.project_data.primary_channels == bindings
    assert window.session.project_data.streams[exp_stream.id] is exp_stream
    assert window.session.regions == regions
    assert window.session.candidates == candidates
    assert window.export_dialog.selected_exporter_ids() == selected_exports
    assert window.chamber_pressure_page.analysis_complete
    assert window.temperature_page.analysis_complete
    assert window.chamber_pressure_page.metrics_table.rowCount() == pressure_rows
    theory_source = next(source for source in window.session.project_data.sources.values()
                         if source.source_kind == SourceKind.THEORETICAL)
    theory_stream = next(stream for stream in window.session.project_data.streams.values()
                         if stream.source_id == theory_source.id)
    ref = ChannelReference(theory_source.id, theory_stream.id, "f")
    assert window.session.project_data.channel(bindings.thrust).id == ref.channel_id
    assert window.session.project_data.channel(ref).data_unit == "kN"
    assert not window.session.project_data.channel(ref).values.flags.writeable
    np.testing.assert_array_equal(theory_stream.dataset.time, [8, 9, 10, 11, 13])
    assert window.process_page.input_combo.count() == 2  # None plus experimental input.
    for page in (window.process_page, window.chamber_pressure_page, window.temperature_page):
        assert page.theory_overlay.curve_list.count() == 1
        item = page.analysis_plot._series[-1]
        assert item.opts["pen"].style() == Qt.PenStyle.DashLine
        assert "Theoretical:" in item.name()
    force_values = window.process_page.analysis_plot._series_data[-1][1]
    np.testing.assert_array_equal(force_values, [0, 1000, np.nan, 1000, 0])
    assert window.process_page.analysis_plot._series[-1].opts["connect"] == "finite"
    np.testing.assert_allclose(window.temperature_page.analysis_plot._series_data[-1][1],
                               [20, 21, 22, 23, 24])
    explorer = window.data_explorer_page
    explorer.show_auxiliary_check.setChecked(True)
    explorer.channel_combo.setCurrentIndex(explorer.channel_combo.findData(
        ChannelReference(exp_stream.source_id, exp_stream.id, "web").stable_id
    ))
    np.testing.assert_allclose(explorer.analysis_plot._series_data[-1][1], [0, 1, 2, 3, 4])

    overlay = window.process_page.theory_overlay
    for shift in [-2.25, 1.75]:
        overlay.shift_spin.setValue(shift)
        np.testing.assert_allclose(window.process_page.analysis_plot._series_data[-1][0],
                                   np.array([8, 9, 10, 11, 13]) + shift)
        assert window.session.analysis_result is analysis
    overlay.align_button.click()
    _wait(window)
    np.testing.assert_array_equal(window.process_page.analysis_plot._series_data[-1][0],
                                  [0, 1, 2, 3, 5])
    overlay.shift_spin.setValue(-1.25)
    overlay.curve_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert len(window.process_page.analysis_plot._series_data) == 2
    overlay.curve_list.item(0).setCheckState(Qt.CheckState.Checked)
    window.temperature_page.set_display_mode(UnitDisplayMode.SI_SCIENTIFIC)
    np.testing.assert_allclose(window.temperature_page.analysis_plot._series_data[-1][1],
                               [293.15, 294.15, 295.15, 296.15, 297.15])
    # Selecting/calibrating a theoretical source must preserve completed experiment state.
    window._source_selection_changed(str(theory_path))
    window._calibration_apply()
    _wait(window)
    assert not window._test_errors
    assert window.session.analysis_result is analysis
    assert window.session.processing_result is processing
    assert window.chamber_pressure_page.analysis_complete
    assert window.temperature_page.analysis_complete
    window.chamber_pressure_page.theory_overlay.curve_list.item(0).setCheckState(
        Qt.CheckState.Unchecked
    )

    project_path = tmp_path / "overlay.retldc.json"
    window._project_save_path(project_path)
    _wait(window)
    saved = Project_Load(project_path)
    assert saved.software_version == "0.1.0"
    state = next(source for source in saved.sources if source.source_id == theory_source.id)
    assert state.display_transform.shift_s == -1.25
    assert not state.display_transform.zero_start
    assert state.source_kind == SourceKind.THEORETICAL
    assert len(state.display_transform.hidden_curve_ids) == 1
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project_path), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    assert dict(window.session.analysis_result.metrics) == expected_metrics
    assert window.chamber_pressure_page.theory_overlay.curve_list.item(0).checkState() == (
        Qt.CheckState.Unchecked
    )
    assert len(window.chamber_pressure_page.analysis_plot._series_data) == 1
    np.testing.assert_array_equal(window.process_page.analysis_plot._series_data[-1][0],
                                  [6.75, 7.75, 8.75, 9.75, 11.75])
    window.process_page.theory_overlay.reset_button.click()
    np.testing.assert_array_equal(window.process_page.analysis_plot._series_data[-1][0],
                                  [8, 9, 10, 11, 13])
    analysis_after_reopen = window.session.analysis_result
    window.import_page.source_list.setCurrentRow(1)
    window.import_page._source_remove()
    assert window.session.analysis_result is analysis_after_reopen
    assert window.chamber_pressure_page.analysis_complete
    assert window.temperature_page.analysis_complete
    assert all(source.source_kind == SourceKind.EXPERIMENTAL
               for source in window.session.project_data.sources.values())
    assert not window.process_page.theory_overlay._curves
    assert theory_path.read_bytes() == original_bytes
    empty_path = tmp_path / "empty.csv"
    empty_path.write_text("", encoding="utf-8")
    window.import_page.add_source_paths([empty_path])
    window._source_parse()
    _wait(window)
    assert window._test_errors
    assert window.session.analysis_result is analysis_after_reopen
    assert len(window.session.project_data.sources) == 1


def test_incompatible_and_empty_curves_are_disabled(window: MainWindow) -> None:
    curves: list[DisplayCurve] = []
    sources = {}
    streams = {}
    for index, (unit, values) in enumerate([
        ("Pa", [0, 1]), ("raw", [0, 1]), ("N", [np.nan, np.nan]), ("N", []),
    ]):
        key = f"theory{index}"
        dataset = Dataset(list(range(len(values))), {
            "f": Channel("f", "force", unit, values, "raw")
        })
        sources[key] = Source(key, Path(key), source_kind=SourceKind.THEORETICAL)
        stream = Stream(key, key, dataset)
        streams[key] = stream
        curves.append(DisplayCurve(ChannelReference(key, key, "f"), stream.dataset, "f", key))
    window.session.project_data = ProjectData(sources, streams)
    window._measurement_workspaces_update()
    overlay = window.process_page.theory_overlay
    assert overlay.curve_list.count() == 4
    assert all(not overlay.curve_list.item(index).flags() & Qt.ItemFlag.ItemIsEnabled
               for index in range(4))
    assert not window.process_page.analysis_plot._series_data
    assert window.process_page.input_channel_id is None


def test_theory_only_import_and_legacy_reopen(
    window: MainWindow, tmp_path: Path, monkeypatch, capsys,
) -> None:
    path = tmp_path / "theory.csv"
    window.import_page.new_kind_combo.setCurrentIndex(1)
    _experimental_import(window, path)
    assert window.session.project_data.primary_channels.thrust is None
    assert window.session.project_data.primary_channels.chamber_pressure is None
    assert window.session.project_data.primary_channels.temperature_channels == ()
    assert len(window.process_page.analysis_plot._series_data) == 1
    assert window.chamber_pressure_page.calculate_button.isEnabled() is False
    theory_source = next(iter(window.session.project_data.sources.values()))
    # Legacy saved source-start zeroing remains readable; the new GUI emits absolute shifts.
    window.session.project_data = window.session.project_data.with_source_display(
        theory_source.id, SourceDisplayTransform(-2, True),
    )
    window._measurement_workspaces_update()
    exp_path = tmp_path / "experimental.csv"
    window.import_page.new_kind_combo.setCurrentIndex(0)
    exp_path.write_bytes(path.read_bytes())
    window.import_page.add_source_paths([exp_path])
    _configure_mapping(window, exp_path, ["N", "Pa", "°C", "mm"])
    window._source_parse()
    _wait(window)
    assert not window._test_errors
    assert window.session.project_data.sources[theory_source.id].display_transform == (
        SourceDisplayTransform(-2, True)
    )
    assert window.session.project_data.primary_channels.thrust.source_id != theory_source.id
    # Removing the additive origin fields gives an ordinary legacy experimental project.
    document = window._project_document_create()
    sources = tuple(
        replace(source, source_kind=SourceKind.EXPERIMENTAL,
                display_transform=SourceDisplayTransform())
        for source in document.sources
    )
    legacy_path = tmp_path / "legacy.retldc.json"
    Project_Save(replace(document, sources=sources), legacy_path)
    payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    for source in payload["sources"]:
        source.pop("source_kind")
        source.pop("display_transform")
    legacy_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(legacy_path), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    assert all(source.source_kind == SourceKind.EXPERIMENTAL
               for source in window.session.project_data.sources.values())
    assert window.session.project_data.primary_channels.thrust is not None
    assert not window.process_page.theory_overlay._curves
    payload["workflow_state"]["parsed"] = False
    legacy_path.write_text(json.dumps(payload), encoding="utf-8")
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    assert window.session.raw_dataset is None
    assert all(window.import_page.source_kind(path) == SourceKind.EXPERIMENTAL
               for path in window.import_page.source_paths())
    assert "Traceback" not in capsys.readouterr().err


def _source_result_calculate(window: MainWindow, page, source_id: str):
    control = page.source_analysis
    control.source_combo.setCurrentIndex(control.source_combo.findData(source_id))
    if control.workspace_id == "data_explorer" and control.channel_combo.currentData() is None:
        control.channel_combo.setCurrentIndex(1)
    page.calculate_button.click()
    _wait(window)
    state = window.session.source_analyses[f"{source_id}/{control.workspace_id}"]
    assert state.completed, state.error
    return state


def test_hidden_theory_panel_uses_shared_toolbar_action_and_saved_source_interval(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "compact-results.csv"
    _experimental_import(window, path)
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window._processing_apply()
    _wait(window)
    window.setup_page.set_motor_metadata({"propellant_mass_kg": .1})
    window._workspace_select("thrust_analysis")
    assert window.calculate_action.isEnabled()
    window.calculate_action.trigger()
    _wait(window)
    experimental = window.session.analysis_result
    processing = window.session.processing_result
    bindings = window.session.project_data.primary_channels
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([path])
    _configure_theory_mapping(window, path)
    window._source_parse()
    _wait(window)
    theory = next(source for source in window.session.project_data.sources.values()
                  if source.source_kind == SourceKind.THEORETICAL)
    control = window.analyze_page.source_analysis
    control.source_combo.setCurrentIndex(1)
    assert control.source_id() == theory.id
    for page in (window.analyze_page, *window._measurement_pages()):
        widget = page.source_analysis
        widget.source_combo.setCurrentIndex(1)
        assert widget.parameter_scroll.isHidden()
        assert page.calculate_button.isHidden()
        panel = page.metrics_group if page is window.analyze_page else page.results_panel
        assert widget.parent() is panel
    config = replace(control.config(), interval=(1, 3))
    window._source_analysis_config_changed(config)
    window._source_analysis_views_sync()
    window.process_page.theory_overlay.shift_spin.setValue(100)
    window.calculate_action.trigger()
    _wait(window)
    state = window.session.source_analyses[config.key]
    assert state.completed, state.error
    assert state.config.interval == (1, 3)
    assert next(iter(state.results.values())).metrics["total_impulse_ns"] == 4000
    assert window.session.analysis_result is experimental
    assert window.session.processing_result is processing
    assert window.session.project_data.primary_channels == bindings
    control.source_combo.setCurrentIndex(0)
    assert window.analyze_page._result is experimental
    control.source_combo.setCurrentIndex(1)
    assert control.selected_state() is state
    project = tmp_path / "compact-results.json"
    window._project_save_path(project)
    _wait(window)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    restored = window.session.source_analyses[config.key]
    assert restored.completed and restored.config.interval == (1, 3)
    window._workspace_select("thrust_analysis")
    control.source_combo.setCurrentIndex(1)
    window.calculate_action.trigger()
    _wait(window)
    assert window.session.source_analyses[config.key].completed
    assert not window._test_errors


def test_toolbar_calculation_uses_selected_theory_curve_and_reports_unavailable(
    window: MainWindow, tmp_path: Path,
) -> None:
    path = tmp_path / "curve-choice.csv"
    _experimental_import(window, path)
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([path])
    _configure_theory_mapping(window, path)
    window._source_parse()
    _wait(window)
    for workspace_id, page in (("chamber_pressure", window.chamber_pressure_page),
                               ("temperature", window.temperature_page),
                               ("data_explorer", window.data_explorer_page)):
        window._workspace_select(workspace_id)
        page.source_analysis.source_combo.setCurrentIndex(1)
        selected = page.theory_overlay.selected_reference()
        assert page.source_analysis.source_id() == selected.source_id
        assert window.calculate_action.isEnabled()
        window.calculate_action.trigger()
        _wait(window)
        assert page.source_analysis.selected_state().completed
    window._workspace_select("project")
    assert not window.calculate_action.isVisible()
    window._project_new()
    window._workspace_select("thrust_analysis")
    assert not window.calculate_action.isEnabled()
    assert not window._test_errors


def test_toolbar_switches_theory_sources_without_experimental_fallback(
    window: MainWindow, tmp_path: Path,
) -> None:
    _experimental_import(window, tmp_path / "experiment.csv")
    bindings = window.session.project_data.primary_channels
    theory_ids = []
    for index, peak in enumerate((10, 20)):
        path = tmp_path / f"theory-{index}.csv"
        path.write_text(f"time,f,p,t,web\n0,0,0,293,0\n1,{peak},1,294,1\n"
                        "2,0,0,293,0\n", encoding="utf-8")
        window.import_page.new_kind_combo.setCurrentIndex(1)
        window.import_page.add_source_paths([path])
        _configure_mapping(window, path, ["N", "Pa", "K", "m"])
        window._source_parse()
        _wait(window)
        theory_ids.append(next(source.id for source in window.session.project_data.sources.values()
                               if source.path == path))
    window._workspace_select("thrust_analysis")
    control = window.analyze_page.source_analysis
    control.source_combo.setCurrentIndex(1)
    overlay = window.process_page.theory_overlay
    for source_id, expected in zip(reversed(theory_ids), (20, 10), strict=True):
        reference = next(item.reference for item in control._inputs
                         if item.reference.source_id == source_id
                         and item.dataset.channel(item.channel_id).quantity == "force")
        overlay.curve_combo.setCurrentIndex(overlay.curve_combo.findData(reference.stable_id))
        assert control.source_id() == source_id
        window.calculate_action.trigger()
        _wait(window)
        state = control.selected_state()
        assert state.completed, state.error
        assert state.config.channels == (reference,)
        assert next(iter(state.results.values())).metrics["total_impulse_ns"] == expected
        assert window.session.analysis_result is None
        assert window.session.project_data.primary_channels == bindings
    # A theory input with conflicting physical units is visibly unavailable, never experimental.
    source_id = theory_ids[0]
    reference = window.session.source_analyses[f"{source_id}/thrust_analysis"].config.channels[0]
    stream = window.session.project_data.streams[reference.stream_id]
    channel = stream.dataset.channel(reference.channel_id)
    invalid = Channel(channel.id, channel.quantity, "ADC", channel.values, channel.role,
                      semantic_role=channel.semantic_role)
    channels = dict(stream.dataset.channels)
    channels[channel.id] = invalid
    dataset = replace(stream.dataset, channels=channels)
    streams = dict(window.session.project_data.streams)
    streams[stream.id] = replace(stream, dataset=dataset)
    window.session.project_data = replace(window.session.project_data, streams=streams)
    window.session.calibrated_streams.pop(stream.id, None)
    window._source_analysis_views_sync()
    control.source_combo.setCurrentIndex(0)
    overlay.curve_combo.setCurrentIndex(overlay.curve_combo.findData(reference.stable_id))
    control.source_combo.setCurrentIndex(1)
    assert not window.calculate_action.isEnabled()
    assert control.notice.text() and not control.notice.isHidden()
    assert window.session.analysis_result is None


def test_independent_source_results_params_display_reopen_and_removal(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "shared.csv"
    _experimental_import(window, path)
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window.process_page.apply_button.click()
    _wait(window)
    window.setup_page.set_motor_metadata({"propellant_mass_kg": .1})
    window.analyze_page.calculate_button.click()
    _wait(window)
    legacy_analysis = window.session.analysis_result
    legacy_processing = window.session.processing_result
    bindings = window.session.project_data.primary_channels
    exports = window.export_dialog.selected_exporter_ids()
    experimental_id = bindings.thrust.source_id
    window._source_analysis_calculate(SourceAnalysisConfig(
        experimental_id, "thrust_analysis", (bindings.thrust,),
    ))
    _wait(window)
    experiment_profile = window.session.source_analyses[f"{experimental_id}/thrust_analysis"]
    assert next(iter(experiment_profile.results.values())).metrics["total_impulse_ns"] == 4000
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([path])
    _configure_theory_mapping(window, path)
    window.import_page.parse_button.click()
    _wait(window)
    theory = next(source for source in window.session.project_data.sources.values()
                  if source.source_kind == SourceKind.THEORETICAL)
    theory_profile = _source_result_calculate(window, window.analyze_page, theory.id)
    result = next(iter(theory_profile.results.values()))
    assert result.metrics["total_impulse_ns"] == 8000
    assert result.metrics["specific_impulse_s"] == 8000 / (.1 * 9.80665)
    assert theory_profile.config.mass_source == "project"
    assert window.setup_page.motor_metadata()["propellant_mass_kg"] == .1
    control = window.analyze_page.source_analysis
    window._source_analysis_config_changed(replace(
        theory_profile.config, mass_source="source", propellant_mass_kg=.25,
    ))
    window._source_analysis_views_sync()
    assert not window.session.source_analyses[theory_profile.config.key].completed
    window.analyze_page.calculate_button.click()
    _wait(window)
    theory_profile = window.session.source_analyses[theory_profile.config.key]
    metrics = dict(next(iter(theory_profile.results.values())).metrics)
    assert metrics["specific_impulse_s"] == 8000 / (.1 * 9.80665)
    assert theory_profile.config.legacy_physical_parameters == {"propellant_mass_kg": .25}
    states = {}
    for page in window._measurement_pages():
        state = _source_result_calculate(window, page, theory.id)
        states[state.config.key] = state
        assert page.metrics_table.rowCount() > 0
    overlay = window.process_page.theory_overlay
    overlay.shift_spin.setValue(-5)
    overlay.align_button.click()
    _wait(window)
    overlay.shift_spin.setValue(2)
    overlay.reset_button.click()
    assert window.session.source_analyses[theory_profile.config.key] is theory_profile
    assert window.session.analysis_result is legacy_analysis
    assert window.session.processing_result is legacy_processing
    assert window.session.project_data.primary_channels == bindings
    assert window.export_dialog.selected_exporter_ids() == exports
    # Selecting the legacy result or another same-name Source cannot replace its metrics.
    control.source_combo.setCurrentIndex(0)
    assert window.analyze_page._result is legacy_analysis
    assert control.source_combo.findData(experimental_id) == -1
    assert control.source_combo.count() == 2
    assert control.selected_state() is None
    control.source_combo.setCurrentIndex(control.source_combo.findData(theory.id))
    # Draft remains pending after save/reopen instead of being implicitly calculated.
    pressure_control = window.chamber_pressure_page.source_analysis
    pressure_control.interval_combo.setCurrentIndex(1)
    pressure_control.start_spin.setValue(1)
    pressure_control.end_spin.setValue(3)
    pressure_key = f"{theory.id}/chamber_pressure"
    assert not window.session.source_analyses[pressure_key].completed
    project_path = tmp_path / "source-results.retldc.json"
    window._project_save_path(project_path)
    _wait(window)
    saved = json.loads(project_path.read_text(encoding="utf-8"))
    saved["source_analyses"][theory_profile.config.key]["config"].pop("mass_source")
    snapshot = saved["source_analyses"][theory_profile.config.key]["results"]
    next(iter(snapshot.values()))["metrics"]["total_impulse_ns"] = -999
    project_path.write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project_path), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    loaded = window.session.source_analyses
    assert dict(next(iter(loaded[theory_profile.config.key].results.values())).metrics) == metrics
    assert not loaded[pressure_key].completed
    assert loaded[pressure_key].config.interval == (1, 3)
    assert loaded[theory_profile.config.key].config.mass_source == "project"
    assert loaded[theory_profile.config.key].config.legacy_physical_parameters == {
        "propellant_mass_kg": .25,
    }
    assert window.statusBar().currentMessage() == window.translations.translate(
        "source_analysis.legacy_parameters_kept",
    )
    assert loaded[experiment_profile.config.key].completed
    assert dict(window.session.analysis_result.metrics) == dict(legacy_analysis.metrics)
    row = next(index for index in range(window.import_page.source_list.count())
               if window.import_page.source_list.item(index).data(
                   window.import_page.SOURCE_ID_ROLE) == theory.id)
    window.import_page.source_list.setCurrentRow(row)
    experimental_profile_after_reopen = loaded[experiment_profile.config.key]
    experimental_analysis_after_reopen = window.session.analysis_result
    window._calibration_apply()
    _wait(window)
    assert not window.session.source_analyses[theory_profile.config.key].completed
    assert window.session.source_analyses[experiment_profile.config.key] is (
        experimental_profile_after_reopen
    )
    assert window.session.analysis_result is experimental_analysis_after_reopen
    window.import_page.remove_source_button.click()
    assert set(window.session.source_analyses) == {experiment_profile.config.key}
    assert window.session.source_analyses[experiment_profile.config.key].completed
    assert dict(window.session.analysis_result.metrics) == dict(legacy_analysis.metrics)


def test_theory_only_calculation_reopen_preserves_independent_calibration_stage(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    source = tmp_path / "theory-only.csv"
    source.write_text("time,f,p,t,web\n0,0,0,20,0\n1,1000,1000000,21,1\n"
                      "2,2000,2000000,22,2\n3,1000,1000000,23,3\n4,0,0,24,4\n",
                      encoding="utf-8")
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([source])
    window.import_page.set_parser_id("builtin.parser.generic_delimited")
    _configure_mapping(window, source, ["N", "Pa", "°C", "mm"])
    window.import_page.parse_button.click()
    _wait(window)
    assert window.session.project_data.primary_channels.thrust is None
    window._calibration_apply()
    _wait(window)
    source_id = next(iter(window.session.project_data.sources))
    profile = _source_result_calculate(window, window.analyze_page, source_id)
    assert window.session.analysis_result is None
    assert window.session.processing_result is None

    path = tmp_path / "theory-only.retldc.json"
    window._project_save_path(path)
    _wait(window)
    document = Project_Load(path)
    assert document.calibrated_stream_ids
    assert not document.workflow_state["analyzed"]
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(path), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    assert window.session.source_analyses[profile.config.key].completed
    assert window.session.calibrated_streams
    assert window.session.analysis_result is None
    assert window.session.processing_result is None

    def fail_calculator(*_args, **_kwargs):
        raise RuntimeError("Source Analyzer failure fixture")

    analyzer = window.registry.get("builtin.analyzer.thrust")
    monkeypatch.setattr(analyzer, "analyze", fail_calculator)
    window._source_analysis_calculate(profile.config)
    _wait(window)
    failed = window.session.source_analyses[profile.config.key]
    assert not failed.completed
    assert "failure fixture" in failed.error
    assert not window._test_errors
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    assert len(window.session.project_data.sources) == 1
    assert "failure fixture" in window.session.source_analyses[profile.config.key].error


def test_shared_mass_updates_both_results_without_changing_inputs(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "shared-mass.csv"
    _experimental_import(window, path)
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window._processing_apply()
    _wait(window)
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([path])
    _configure_theory_mapping(window, path)
    window._source_parse()
    _wait(window)
    theory = next(source for source in window.session.project_data.sources.values()
                  if source.source_kind == SourceKind.THEORETICAL)
    control = window.analyze_page.source_analysis
    binding = window.session.project_data.primary_channels
    processing = window.session.processing_result
    regions = dict(window.session.regions)
    raw = window.session.project_data.streams[binding.thrust.stream_id].dataset
    original = raw.channel("f").values.copy()
    for mass in (.1, .2, None, 0):
        window.setup_page.motor_edits["propellant_mass_kg"].setText(
            "" if mass is None else str(mass),
        )
        assert window.session.analysis_result is None
        key = f"{theory.id}/thrust_analysis"
        if key in window.session.source_analyses:
            assert not window.session.source_analyses[key].completed
        control.source_combo.setCurrentIndex(0)
        window.analyze_page.calculate_button.click()
        _wait(window)
        state = _source_result_calculate(window, window.analyze_page, theory.id)
        assert state.config.mass_source == "project"
        assert state.config.propellant_mass_kg == mass
        assert state.config.input_stage == "calibrated"
        assert state.config.polarity == 1 and state.config.processor is None
        for result in (window.session.analysis_result, *state.results.values()):
            impulse = result.metrics["total_impulse_ns"]
            expected = impulse / (mass * 9.80665) if mass else None
            assert result.metrics["specific_impulse_s"] == expected
        assert window.session.processing_result is processing
        assert window.session.project_data.primary_channels == binding
        assert window.session.regions == regions
        np.testing.assert_array_equal(raw.channel("f").values, original)
    # Explicit shared provenance and the effective value survive save/reopen.
    project = tmp_path / "shared-mass.json"
    window._project_save_path(project)
    _wait(window)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    loaded = window.session.source_analyses[key]
    assert loaded.completed and loaded.config.mass_source == "project"
    assert loaded.config.propellant_mass_kg == 0
    assert not window._source_analysis_has_legacy_parameters()
    assert not window._test_errors


def test_compact_source_controls_preserve_hidden_legacy_config_and_switching(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "legacy-config.csv"
    _experimental_import(window, path)
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([path])
    _configure_theory_mapping(window, path)
    window._source_parse()
    _wait(window)
    theory = next(source for source in window.session.project_data.sources.values()
                  if source.source_kind == SourceKind.THEORETICAL)
    window._thrust_polarity_changed(-1)
    window.process_page.set_processing_config("builtin.processor.vertical_linear_baseline", {})
    state = _source_result_calculate(window, window.analyze_page, theory.id)
    assert state.config.polarity == 1 and state.config.processor is None
    legacy = replace(
        state.config, mass_source="source", propellant_mass_kg=.25, polarity=-1,
        pre=(0, 1), post=(3, 4), interval=(1, 3),
        processor=window._plugin_reference_create(
            "builtin.processor.vertical_linear_baseline", {},
        ).to_dict(),
    )
    window._source_analysis_calculate(legacy)
    _wait(window)
    state = window.session.source_analyses[legacy.key]
    assert state.completed, state.error
    window.setup_page.motor_edits["propellant_mass_kg"].setText(".1")
    assert not window.session.source_analyses[legacy.key].completed
    window._source_analysis_calculate(window.session.source_analyses[legacy.key].config)
    _wait(window)
    state = window.session.source_analyses[legacy.key]
    effective = replace(legacy, mass_source="project", propellant_mass_kg=.1,
                        legacy_physical_parameters={"propellant_mass_kg": .25})
    assert state.config == effective
    control = window.analyze_page.source_analysis
    for page in (window.analyze_page, *window._measurement_pages()):
        widget = page.source_analysis
        for name in ("mass_spin", "mass_known", "stage_combo", "polarity_combo",
                     "processor_combo", "processor_form", "baseline_spins"):
            assert not hasattr(widget, name)
        widget.source_combo.setCurrentIndex(1)
        assert widget.notice.isHidden()
        assert widget._form.rowCount() == 6
        assert not widget._form.isRowVisible(widget.record_combo)
    for _ in range(2):
        control.source_combo.setCurrentIndex(0)
        assert control.parameter_scroll.isHidden() and control.notice.isHidden()
        control.source_combo.setCurrentIndex(1)
        assert control.config() == effective
    assert control._form.isRowVisible(control.start_spin)
    assert control._form.isRowVisible(control.end_spin)
    assert window._source_analysis_has_legacy_parameters()
    project = tmp_path / "legacy-config.json"
    window._project_save_path(project)
    _wait(window)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    restored = window.session.source_analyses[legacy.key]
    assert restored.config == effective and restored.completed
    assert [dict(item.metrics) for item in restored.results.values()] == [
        dict(item.metrics) for item in state.results.values()
    ]
    assert not window._test_errors


def test_mass_changed_during_analysis_does_not_restore_stale_results(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    from underline_retldc.plugin_api.common import TaskContext

    _experimental_import(window, tmp_path / "mass-task.csv")
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window._processing_apply()
    _wait(window)
    window.setup_page.motor_edits["propellant_mass_kg"].setText(".1")
    pending = []
    monkeypatch.setattr(window, "_task_start", lambda label, op, done: pending.append((op, done)))
    window._analysis_calculate()
    operation, success = pending.pop()
    result = operation(TaskContext())
    window.setup_page.motor_edits["propellant_mass_kg"].setText(".2")
    success(result)
    assert window.session.analysis_result is None
    assert window.session.motor_metadata["propellant_mass_kg"] == .2
    ref = window.session.project_data.primary_channels.thrust
    config = SourceAnalysisConfig(ref.source_id, "thrust_analysis", (ref,), mass_source="project")
    window._source_analysis_calculate(config)
    operation, success = pending.pop()
    state = operation(TaskContext())
    window.setup_page.motor_edits["propellant_mass_kg"].setText(".3")
    success(state)
    assert not window.session.source_analyses[config.key].completed
    assert window.session.source_analyses[config.key].config.propellant_mass_kg == .3


def test_processed_source_result_invalidation_and_own_source_error_isolation(
    window: MainWindow, tmp_path: Path,
) -> None:
    _experimental_import(window, tmp_path / "exp.csv")
    reference = window.session.project_data.primary_channels.thrust
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window.process_page.apply_button.click()
    _wait(window)
    config = SourceAnalysisConfig(reference.source_id, "thrust_analysis", (reference,),
                                  input_stage="project_processed", interval=(1, 3),
                                  propellant_mass_kg=.25)
    window._source_analysis_calculate(config)
    _wait(window)
    assert window.session.source_analyses[config.key].completed
    window._thrust_polarity_changed(-1)
    assert not window.session.source_analyses[config.key].completed
    independent = replace(config, input_stage="calibrated")
    window._source_analysis_calculate(independent)
    _wait(window)
    completed = window.session.source_analyses[config.key]
    assert completed.completed
    window._regions_store({"pre": None, "active_test": [0, 4], "post": None})
    assert window.session.source_analyses[config.key] is completed
    invalid = replace(independent, workspace_id="chamber_pressure")
    window._source_analysis_calculate(invalid)
    _wait(window)
    assert window.session.source_analyses[invalid.key].error
    assert window.session.source_analyses[config.key] is completed


def test_portable_source_workflow_uses_real_gui_and_generated_fixture(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from underline_retldc.app.release_smoke import _source_workflow_check, _xlsx_write

    monkeypatch.setattr(
        window, "_tabular_preview_refresh", MainWindow._tabular_preview_refresh.__get__(window),
    )
    source = tmp_path / "generated_4001.xlsx"
    _xlsx_write(source)
    window.import_page.add_source_paths([source])
    window._parser_detect()
    _wait(window)
    assert not window._test_errors
    assert window.session.raw_dataset.sample_count == 4001
    window._regions_store({"pre": [0, 1], "active_test": [2, 8], "post": [9, 10]})
    window.process_page.apply_button.click()
    _wait(window)
    window.analyze_page.calculate_button.click()
    _wait(window)
    window.chamber_pressure_page.calculate_button.click()
    window.temperature_page.calculate_button.click()
    report = {"checks": [], "screenshots": []}

    def check(name: str, passed: bool) -> None:
        assert passed, name
        report["checks"].append(name)

    _source_workflow_check(window, tmp_path, source, window._test_errors, report, check)
    assert not window._test_errors
    assert not report["source_workflow"]["scientific_stubs"]
    assert report["source_workflow"]["automatic_preview_enabled"]
    assert not report["source_workflow"]["propellant_mass_supplied"]


def _metric_cells(window: MainWindow) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(table.item(row, column).text()
              for row in range(table.rowCount()) for column in range(table.columnCount()))
        for table in (
            window.chamber_pressure_page.metrics_table, window.temperature_page.metrics_table,
            window.data_explorer_page.metrics_table,
        )
    )


def test_finished_worker_callback_is_delivered_before_another_task(window: MainWindow) -> None:
    delivered: list[str] = []
    first = window._task_start("first", lambda _context: "first", delivered.append)
    assert first is not None
    assert first.wait(2) == "first"
    assert first.done
    assert window._task_start("second", lambda _context: "second", delivered.append) is None
    assert delivered == []
    window._task_poll()
    assert delivered == ["first"]
    second = window._task_start("second", lambda _context: "second", delivered.append)
    assert second is not None
    _wait(window)
    assert delivered == ["first", "second"]


def test_theory_only_pressure_reference_uses_the_plot_unit(window: MainWindow) -> None:
    source = Source("theory", Path("reference.csv"), source_kind=SourceKind.THEORETICAL)
    dataset = Dataset([0, 1], {
        "p": Channel("p", "pressure", "Pa", [100000, 200000], "raw", display_unit="kPa")
    })
    stream = Stream("theory_stream", source.id, dataset)
    window.session.project_data = ProjectData({source.id: source}, {stream.id: stream})
    window._measurement_workspaces_update()
    page = window.chamber_pressure_page
    assert page._pressure_display_unit() == "kPa"
    assert page.reference_spin.value() == pytest.approx(101.325)
    assert page.analysis_plot._horizontal_references["pressure_reference"]["value"] == (
        pytest.approx(101.325)
    )
    second = Source("second", Path("second.csv"), source_kind=SourceKind.THEORETICAL)
    second_stream = Stream("second_stream", second.id, Dataset([0, 1], {
        "p": Channel("p", "pressure", "Pa", [100000, 200000], "raw", display_unit="MPa")
    }))
    window.session.project_data = ProjectData(
        {source.id: source, second.id: second},
        {stream.id: stream, second_stream.id: second_stream},
    )
    window._measurement_workspaces_update()
    page.theory_overlay.curve_combo.setCurrentIndex(1)
    assert page._pressure_display_unit() == "MPa"
    assert page.reference_spin.value() == pytest.approx(.101325)
    page.set_display_mode(UnitDisplayMode.SI_SCIENTIFIC)
    assert page._pressure_display_unit() == "Pa"
    assert page.reference_spin.value() == pytest.approx(101325)
    np.testing.assert_array_equal(stream.dataset.channel("p").values, [100000, 200000])


def test_real_parser_unit_conflict_is_blocked_without_changing_experiment(
    window: MainWindow, tmp_path: Path,
) -> None:
    source = tmp_path / "conflict.csv"
    _experimental_import(window, source)
    bindings = window.session.project_data.primary_channels
    raw_values = window.session.project_data.channel(bindings.thrust).values.copy()
    page = window.import_page
    page.new_kind_combo.setCurrentIndex(1)
    page.add_source_paths([source])
    _configure_mapping(window, source, ["Pa", "Pa", "K", "m"])
    page.parse_button.click()
    _wait(window)
    assert not window._test_errors
    assert window.session.project_data.primary_channels == bindings
    overlay = window.process_page.theory_overlay
    assert overlay.curve_list.count() == 1
    assert not overlay.curve_list.item(0).flags() & Qt.ItemFlag.ItemIsEnabled
    assert overlay.curve_list.item(0).checkState() == Qt.CheckState.Unchecked
    assert len(window.process_page.analysis_plot._series_data) == 1
    np.testing.assert_array_equal(window.session.project_data.channel(bindings.thrust).values,
                                  raw_values)


def test_secondary_experiment_selection_does_not_relabel_the_primary_dataset_on_reopen(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    source_a = tmp_path / "primary.csv"
    _experimental_import(window, source_a)
    bindings = window.session.project_data.primary_channels
    source_b = tmp_path / "secondary.csv"
    source_b.write_text("time,f,p,t,web\n0,0,0,293.15,0\n1,1,1,294.15,1\n"
                        "2,2,2,295.15,2\n3,1,1,296.15,3\n4,0,0,297.15,4\n",
                        encoding="utf-8")
    window.import_page.add_source_paths([source_b])
    _configure_mapping(window, source_b, ["kN", "MPa", "K", "m"])
    window.import_page.parse_button.click()
    _wait(window)
    window._primary_bindings_changed(bindings)
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window.process_page.apply_button.click()
    _wait(window)
    window.analyze_page.calculate_button.click()
    _wait(window)
    expected = dict(window.session.analysis_result.metrics)
    window.import_page.source_list.setCurrentRow(1)
    assert window.session.source_path == source_b
    project_path = tmp_path / "secondary.retldc.json"
    window._project_save_path(project_path)
    _wait(window)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project_path), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    assert window.session.project_data.primary_channels == bindings
    assert dict(window.session.analysis_result.metrics) == expected
    np.testing.assert_array_equal(window.session.project_data.channel(bindings.thrust).values,
                                  [0, 1000, 2000, 1000, 0])


@pytest.mark.parametrize("theory_first", [False, True])
@pytest.mark.parametrize("remove_kind", [SourceKind.THEORETICAL, SourceKind.EXPERIMENTAL])
def test_one_physical_file_two_origins_with_real_compensation_and_reopen(
    window: MainWindow, tmp_path: Path, monkeypatch, capsys,
    theory_first: bool, remove_kind: SourceKind,
) -> None:
    source = tmp_path / "shared.csv"
    source.write_text("time,f,p,t,web\n" + "".join(
        f"{time},{5 + thrust},{thrust * 1000},{20 + time},{time}\n"
        for time, thrust in enumerate([0, 0, 0, 0, 1000, 2000, 1000, 0, 0, 0, 0])
    ), encoding="utf-8")
    original_bytes = source.read_bytes()
    page = window.import_page
    if theory_first:
        page.new_kind_combo.setCurrentIndex(1)
        page.add_source_paths([source])
        page.set_parser_id("builtin.parser.generic_delimited")
        _configure_theory_mapping(window, source)
        page.parse_button.click()
        _wait(window)
    page.new_kind_combo.setCurrentIndex(0)
    page.add_source_paths([source])
    page.set_parser_id("builtin.parser.generic_delimited")
    _configure_mapping(window, source, ["N", "Pa", "°C", "mm"])
    page.parse_button.click()
    _wait(window)
    assert not window._test_errors
    window._burn_detect("chamber_pressure")
    _wait(window)
    window._regions_store({"pre": [0, 2], "active_test": [3, 7], "post": [8, 10]})
    processor_id = "builtin.processor.vertical_linear_baseline"
    window.process_page.processor_combo.setCurrentIndex(
        window.process_page.processor_combo.findData(processor_id)
    )
    window.process_page.apply_button.click()
    _wait(window)
    window.analyze_page.calculate_button.click()
    _wait(window)
    window.chamber_pressure_page.calculate_button.click()
    window.temperature_page.calculate_button.click()
    assert not window._test_errors
    bindings = window.session.project_data.primary_channels
    processing = window.session.processing_result
    assert processing is not None
    assert window.session.processor_id == processor_id
    assert processing.metadata["baseline_pre_source"] == "measured_fit"
    analysis = window.session.analysis_result
    cells = _metric_cells(window)
    candidates = tuple(window.session.candidates)
    regions = dict(window.session.regions)
    processor_config = dict(window.session.processor_config)
    expected_metrics = dict(analysis.metrics)
    if not theory_first:
        page.new_kind_combo.setCurrentIndex(1)
        page.add_source_paths([source])
        # Removing an unparsed same-file theory entry must retain the parsed experiment.
        page.source_kind_combo.setCurrentIndex(0)
        assert page.source_import_entries()[1][2] == SourceKind.THEORETICAL
        page.remove_source_button.click()
        assert window.session.analysis_result is analysis
        page.add_source_paths([source])
        _configure_theory_mapping(window, source)
        page.parse_button.click()
        page.parse_button.click()  # A pending task/undelivered callback cannot be replaced.
        _wait(window)
    assert page.source_list.count() == 2
    page.add_source_paths([source])  # Same origin still deduplicates.
    assert page.source_list.count() == 2
    assert len(window.session.project_data.sources) == 2
    theory = next(item for item in window.session.project_data.sources.values()
                  if item.source_kind == SourceKind.THEORETICAL)
    experimental = next(item for item in window.session.project_data.sources.values()
                         if item.source_kind == SourceKind.EXPERIMENTAL)
    assert theory.path == experimental.path
    assert theory.id != experimental.id
    assert window.session.project_data.primary_channels == bindings
    overlay = window.process_page.theory_overlay
    for index in range(12):
        window.navigation.setCurrentRow(index % len(window.workspaces))
        overlay.align_button.click()
        _wait(window)
        overlay.shift_spin.setValue(-.25 if index % 2 else .5)
        overlay.curve_list.item(0).setCheckState(Qt.CheckState.Unchecked)
        overlay.curve_list.item(0).setCheckState(Qt.CheckState.Checked)
    assert window.session.processing_result is processing
    assert window.session.analysis_result is analysis
    assert window.session.processor_config == processor_config
    assert window.session.regions == regions
    assert tuple(window.session.candidates) == candidates
    assert _metric_cells(window) == cells
    assert window.process_page.input_combo.count() == 2
    for index in range(page.source_list.count()):
        page.source_list.setCurrentRow(index)
        selected_id = page.selected_source_id()
        assert window.session.project_data.streams[window.session.active_stream_id].source_id == (
            selected_id
        )
    project_path = tmp_path / "shared.retldc.json"
    window._project_save_path(project_path)
    _wait(window)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project_path), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    assert page.source_list.count() == 2
    assert window.session.project_data.primary_channels == bindings
    assert dict(window.session.analysis_result.metrics) == expected_metrics
    assert window.session.processor_id == processor_id
    source_states = window.session.project_data.sources
    for source_id, expected_unit in [(theory.id, "kN"), (experimental.id, "N")]:
        mapping = next(item for item in source_states[source_id].parser_config["columns"]
                       if item.get("channel_id") == "f")
        assert mapping["unit"] == expected_unit
    theory_stream = next(stream for stream in window.session.project_data.streams.values()
                         if stream.source_id == theory.id)
    np.testing.assert_array_equal(theory_stream.dataset.channel("f").values, np.arange(11))
    assert window.session.project_data.sources[theory.id].display_transform.shift_s == -.25
    row = next(index for index in range(page.source_list.count())
               if page.source_list.item(index).data(page.KIND_ROLE) == remove_kind.value)
    page.source_list.setCurrentRow(row)
    page.remove_source_button.click()
    remaining = experimental if remove_kind == SourceKind.THEORETICAL else theory
    assert tuple(window.session.project_data.sources) == (remaining.id,)
    window._project_save_path(project_path)
    _wait(window)
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    assert not window._test_errors
    assert tuple(window.session.project_data.sources) == (remaining.id,)
    assert page.source_list.count() == 1
    if remove_kind == SourceKind.THEORETICAL:
        assert dict(window.session.analysis_result.metrics) == expected_metrics
        assert window.session.processor_id == processor_id
        assert not window.process_page.theory_overlay._curves
    else:
        assert window.session.analysis_result is None
        assert window.session.project_data.primary_channels.thrust is None
        assert len(window.process_page.analysis_plot._series_data) == 1
    assert source.read_bytes() == original_bytes
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("shift", [-8.5, 4.25])
def test_plot_view_reopen_after_shift_and_page_switch(
    window: MainWindow, tmp_path: Path, monkeypatch, shift: float,
) -> None:
    path = tmp_path / "view.csv"
    _experimental_import(window, path)
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([path])
    _configure_theory_mapping(window, path)
    window._source_parse()
    _wait(window)
    window.process_page.theory_overlay.shift_spin.setValue(shift)
    raw_times = {key: stream.dataset.time.copy()
                 for key, stream in window.session.project_data.streams.items()}
    expected = {}
    for index, (key, plot) in enumerate(window._plot_widgets().items()):
        view = plot.plot_widget.getViewBox()
        view.setRange(xRange=(-2.25 + index, 2.75 + index),
                      yRange=(-10 - index, 10 + index), padding=0)
        if key == "temperature":
            view.enableAutoRange(axis=1, enable=.8)
        expected[key] = tuple(tuple(pair) for pair in view.viewRange())
    saved = window._plot_views_capture()
    project = tmp_path / "view.json"
    window._project_save_path(project)
    _wait(window)
    assert Project_Load(project).plot_views == saved
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    for _ in range(2):
        for key, plot in window._plot_widgets().items():
            window._workspace_select(key)
            QApplication.processEvents()
            view = plot.plot_widget.getViewBox()
            np.testing.assert_allclose(view.viewRange()[0], expected[key][0])
            if key != "temperature":
                np.testing.assert_allclose(view.viewRange()[1], expected[key][1])
                assert view.autoRangeEnabled() == [False, False]
            else:
                assert view.autoRangeEnabled() == [False, .8]
    for key, original in raw_times.items():
        np.testing.assert_array_equal(
            window.session.project_data.streams[key].dataset.time, original,
        )
    assert window.process_page.theory_overlay.shift_spin.value() == shift
    assert not window._test_errors


def test_linked_and_multiple_plot_axes_store_one_range(window: MainWindow) -> None:
    plots = window._plot_widgets()
    thrust = plots["thrust_analysis"].plot_widget.getViewBox()
    pressure = plots["chamber_pressure"].plot_widget.getViewBox()
    pressure.setXLink(thrust)
    plot = plots["temperature"].plot_widget.getPlotItem()
    right = pg.ViewBox()
    plot.scene().addItem(right)
    plot.showAxis("right")
    plot.getAxis("right").linkToView(right)
    right.setXLink(plot.vb)
    right.setRange(yRange=(100, 200), padding=0)
    thrust.setRange(xRange=(-5, 12), yRange=(-2, 2), padding=0)
    states = PlotViews_Capture(plots)
    assert states["chamber_pressure"]["x"].range is None
    assert states["chamber_pressure"]["x"].linked_to == "thrust_analysis/x"
    assert states["temperature"]["right:x"].linked_to == "temperature/x"
    assert states["temperature"]["right:y"].range == (100, 200)
    thrust.setRange(xRange=(0, 1), padding=0)
    right.setRange(yRange=(0, 1), padding=0)
    PlotViews_Restore(plots, states)
    np.testing.assert_allclose(thrust.viewRange()[0], [-5, 12])
    np.testing.assert_allclose(right.viewRange()[1], [100, 200])
    assert pressure.linkedView(0) is thrust
    assert right.linkedView(0) is plot.vb
    plot.scene().removeItem(right)


def test_shared_dimensions_invalidate_and_reach_both_calculators(
    window: MainWindow, tmp_path: Path,
) -> None:
    path = tmp_path / "dimensions.csv"
    _experimental_import(window, path)
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window._processing_apply()
    _wait(window)
    window.setup_page.set_motor_metadata({
        "propellant_mass_kg": .1, "total_motor_mass_kg": .8,
        "diameter_mm": 30, "length_mm": 120,
    })
    window._analysis_calculate()
    _wait(window)
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([path])
    _configure_theory_mapping(window, path)
    window._source_parse()
    _wait(window)
    theory = next(source for source in window.session.project_data.sources.values()
                  if source.source_kind == SourceKind.THEORETICAL)
    state = _source_result_calculate(window, window.analyze_page, theory.id)
    original_config = state.config
    processing = window.session.processing_result
    regions = dict(window.session.regions)
    for name, value in (("total_motor_mass_kg", "1.2"), ("diameter_mm", "40"),
                        ("length_mm", "160"), ("propellant_mass_kg", "")):
        window.setup_page.motor_edits[name].setText(value)
        assert window.session.analysis_result is None
        assert not window.session.source_analyses[state.config.key].completed
        window._analysis_calculate()
        _wait(window)
        state = _source_result_calculate(window, window.analyze_page, theory.id)
        shared = window.session.motor_parameters.to_dict()
        for result in (window.session.analysis_result, *state.results.values()):
            assert result.metadata["motor_parameters"] == shared
            mass = shared["propellant_mass_kg"]
            expected = result.metrics["total_impulse_ns"] / (mass * 9.80665) if mass else None
            assert result.metrics["specific_impulse_s"] == expected
        assert state.config.channels == original_config.channels
        assert state.config.interval == original_config.interval
        assert window.session.processing_result is processing
        assert window.session.regions == regions
    assert shared["propellant_mass_kg"] is None
    assert not window._test_errors



def test_legacy_theory_conflicts_reopen_with_missing_experimental_mass(
    window: MainWindow, tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "legacy-conflict.csv"
    _experimental_import(window, path)
    window.setup_page.set_motor_metadata({"total_motor_mass_kg": .8})
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([path])
    _configure_theory_mapping(window, path)
    window._source_parse()
    _wait(window)
    theory = next(source for source in window.session.project_data.sources.values()
                  if source.source_kind == SourceKind.THEORETICAL)
    state = _source_result_calculate(window, window.analyze_page, theory.id)
    project = tmp_path / "legacy-conflict.json"
    window._project_save_path(project)
    _wait(window)
    payload = json.loads(project.read_text(encoding="utf-8"))
    config = payload["source_analyses"][state.config.key]["config"]
    config.pop("mass_source")
    config.update(propellant_mass_kg=.25, total_motor_mass_kg=9,
                  diameter_mm=90, length_mm=900)
    project.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(project), ""))
    window._project_new()
    window._project_open_dialog()
    _wait(window)
    restored = window.session.source_analyses[state.config.key]
    assert restored.completed and restored.config.mass_source == "project"
    assert restored.config.propellant_mass_kg is None
    assert restored.config.legacy_physical_parameters == {
        "propellant_mass_kg": .25, "total_motor_mass_kg": 9,
        "diameter_mm": 90, "length_mm": 900,
    }
    result = next(iter(restored.results.values()))
    assert result.metrics["specific_impulse_s"] is None
    assert result.metrics["total_impulse_ns"] == 8000
    assert result.metadata["motor_parameters"] == {
        "propellant_mass_kg": None, "total_motor_mass_kg": .8,
        "diameter_mm": None, "length_mm": None,
    }
    assert window.statusBar().currentMessage() == window.translations.translate(
        "source_analysis.legacy_parameters_kept",
    )
    window._project_save_path(project)
    _wait(window)
    assert Project_Load(project).source_analyses[state.config.key].config == restored.config
    assert not window._test_errors
