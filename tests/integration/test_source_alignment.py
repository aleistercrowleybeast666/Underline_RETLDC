from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QStyle, QStyleOptionSlider
from test_theory_overlay import _configure_mapping, _experimental_import, _wait
from test_theory_overlay import window as window

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project_data import Source, SourceKind, Stream
from underline_retldc.gui.main_window import MainWindow


def _import_pair(window: MainWindow, path: Path) -> str:
    _experimental_import(window, path / "experiment.csv")
    theory = path / "theory.csv"
    theory.write_text("time,f,p,t,web\n8,0,0,20,0\n9,1000,1000000,21,1\n"
                      "10,2000,2000000,22,2\n11,1000,1000000,23,3\n12,0,0,24,4\n",
                      encoding="utf-8")
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([theory])
    _configure_mapping(window, theory, ["N", "Pa", "°C", "mm"])
    window._source_parse()
    _wait(window)
    assert not window._test_errors
    return next(source.id for source in window.session.project_data.sources.values()
                if source.source_kind == SourceKind.THEORETICAL)


def test_test_start_alignment_shared_slider_roles_and_reopen(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    theory_id = _import_pair(window, tmp_path)
    window.process_page.detect_button.click()
    _wait(window)
    detection = window.session.project_data.sources[theory_id].display_transform.detected_test
    assert detection is not None
    assert detection.regions.burn.start == 9.0
    assert window.session.regions["active_test"] == [1.0, 3.0]
    # Simulates the same signal that a manual experimental marker edit sends.
    manual = {"pre": None, "active_test": [1.4, 3.2], "post": None}
    window._regions_store(manual)
    window.process_page.apply_button.click()
    _wait(window)
    window.analyze_page.calculate_button.click()
    _wait(window)
    result = window.session.analysis_result
    processing = window.session.processing_result
    source = window.session.project_data.sources[theory_id]
    original = source.path.read_bytes()
    streams = tuple(window.session.project_data.streams.values())
    clocks = [item.dataset.time.copy() for item in streams]
    page = window.analyze_page
    control = page.source_analysis
    assert [control.source_combo.itemText(i) for i in range(2)] == ["Experimental", "Theoretical"]
    assert control.source_combo.count() == 2
    control.source_combo.setCurrentIndex(1)
    page.calculate_button.click()
    _wait(window)
    profile = control.selected_state()
    assert profile and profile.completed
    assert next(iter(profile.results.values())).metrics["total_impulse_ns"] == 4000.0
    controls = [item.theory_overlay for item in
                (window.process_page, *window._measurement_pages())]
    overlay = controls[0]
    overlay.align_button.click()
    _wait(window)
    assert overlay.shift_spin.value() == pytest.approx(-7.6)
    for _ in range(3):
        controls[-1].align_button.click()
        assert overlay.shift_spin.value() == pytest.approx(-7.6)
    # Real Qt handle drag, followed by a numeric edit. Other pages emit no write-back.
    window.show()
    window._workspace_select("thrust_analysis")
    window.thrust_analysis_page.shell.controls_scroll.ensureWidgetVisible(overlay.shift_slider)
    QApplication.processEvents()
    mirrors = [QSignalSpy(item.display_changed) for item in controls[1:]]
    slider = overlay.shift_slider
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    handle = slider.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                          QStyle.SubControl.SC_SliderHandle, slider)
    QTest.mousePress(slider, Qt.MouseButton.LeftButton, pos=handle.center())
    QTest.mouseMove(slider, handle.center() + QPoint(35, 0), delay=30)
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=handle.center() + QPoint(35, 0))
    assert slider.value() != round(-7.6 / overlay._slider_span * 10000)
    shifted = overlay.shift_spin.value()
    assert all(item.shift_spin.value() == shifted for item in controls)
    overlay.shift_spin.setValue(2.125)
    assert all(item.shift_spin.value() == 2.125 for item in controls)
    assert all(spy.count() == 0 for spy in mirrors)
    assert window.session.analysis_result is result
    assert window.session.processing_result is processing
    assert window.session.source_analyses[profile.config.key] is profile
    assert window.session.regions == manual
    assert window.session.segmentation_manually_modified
    for stream, clock in zip(streams, clocks, strict=True):
        np.testing.assert_array_equal(stream.dataset.time, clock)
    saved = tmp_path / "alignment.json"
    window._project_save_path(saved)
    _wait(window)
    window._project_new()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(saved), ""))
    window._project_open_dialog()
    _wait(window)
    transform = window.session.project_data.sources[theory_id].display_transform
    assert transform.shift_s == 2.125
    assert transform.detected_test == detection
    assert window.session.regions == manual
    assert window.session.segmentation_manually_modified
    overlay.align_button.click()
    assert overlay.shift_spin.value() == pytest.approx(-7.6)
    overlay.reset_button.click()
    assert all(item.shift_spin.value() == 0.0 for item in controls)
    assert source.path.read_bytes() == original
    assert not window._test_errors


def test_missing_and_unusable_alignment_are_scoped_not_experiment_edits(
    window: MainWindow, tmp_path: Path,
) -> None:
    _experimental_import(window, tmp_path / "experiment.csv")
    overlay = window.process_page.theory_overlay
    overlay.align_button.click()
    assert "No theory" in overlay.alignment_notice.text()
    source = Source("empty-theory", tmp_path / "unused.csv", source_kind=SourceKind.THEORETICAL)
    dataset = Dataset([8, 9, 10, 11], {"f": Channel("f", "force", "N", [0, 0, 0, 0], "raw")})
    window.session.project_data = window.session.project_data.with_source_stream(
        source, Stream("empty-stream", source.id, dataset),
    )
    window._measurement_workspaces_update()
    overlay.align_button.click()
    assert "experimental test interval" in overlay.alignment_notice.text()
    manual = {"pre": None, "active_test": [1, 3], "post": None}
    window._regions_store(manual)
    overlay.shift_spin.setValue(3.0)
    overlay.align_button.click()
    _wait(window)
    assert "No usable theory" in overlay.alignment_notice.text()
    assert overlay.shift_spin.value() == 3.0
    assert window.session.regions == manual
    assert not window._test_errors


def test_different_theory_files_share_one_offset_and_keep_channel_mapping(
    window: MainWindow, tmp_path: Path,
) -> None:
    theory_id = _import_pair(window, tmp_path)
    source = Source("second-theory", tmp_path / "other.csv", source_kind=SourceKind.THEORETICAL)
    dataset = Dataset([20, 21, 22], {"p": Channel("p", "pressure", "MPa", [0, 4, 0], "raw")})
    window.session.project_data = window.session.project_data.with_source_stream(
        source, Stream("second-stream", source.id, dataset),
    )
    window._measurement_workspaces_update()
    pressure = window.chamber_pressure_page
    pressure.theory_overlay.curve_combo.setCurrentIndex(1)
    pressure.theory_overlay.shift_spin.setValue(-4.25)
    assert all(item.display_transform.shift_s == -4.25
               for item in window.session.project_data.sources.values()
               if item.source_kind == SourceKind.THEORETICAL)
    assert window.process_page.theory_overlay.shift_spin.value() == -4.25
    control = pressure.source_analysis
    control.source_combo.setCurrentIndex(1)
    assert control.source_id() == theory_id
    assert control.source_combo.count() == 2
    assert control.record_combo.count() == 2
    control.record_combo.setCurrentIndex(control.record_combo.findData(source.id))
    pressure.calculate_button.click()
    _wait(window)
    assert control.selected_state().config.source_id == source.id
    control.record_combo.setCurrentIndex(control.record_combo.findData(theory_id))
    pressure.calculate_button.click()
    _wait(window)
    assert control.selected_state().config.source_id == theory_id
    assert not window._test_errors


def test_closing_import_page_cancels_pending_layout_callback(window: MainWindow) -> None:
    window.show()
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
