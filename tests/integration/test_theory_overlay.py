from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
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
from underline_retldc.core.units import UnitDisplayMode
from underline_retldc.gui.main_window import MainWindow
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
    overlay.zero_button.click()
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
    assert state.display_transform.zero_start
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
                                  [-1.25, -.25, .75, 1.75, 3.75])
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
    window._source_display_changed(theory_source.id, SourceDisplayTransform(-2, True))
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
        overlay.zero_button.click()
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
