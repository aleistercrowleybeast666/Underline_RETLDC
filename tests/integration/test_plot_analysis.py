from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
from pyqtgraph.exporters import CSVExporter
from PySide6.QtWidgets import QApplication

from underline_retldc.core.project import ProjectDocument
from underline_retldc.gui.analysis_widgets import AnalysisPlotWidget
from underline_retldc.gui.plot_svg import PlotSVGExporter
from underline_retldc.gui.plot_view import PlotViews_Capture, PlotViews_Restore
from underline_retldc.i18n.service import TranslationService


@pytest.fixture
def plot():
    app = QApplication.instance() or QApplication([])
    widget = AnalysisPlotWidget(TranslationService("en_US"), regions_movable=True)
    widget.resize(900, 550)
    widget.set_empty_state(None)
    widget.show()
    item = widget.plot_widget.getPlotItem()
    item.setDownsampling(ds=1, auto=False)
    item.setClipToView(False)
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("unit,scale", [("N", 1), ("kN", .001), ("MPa", 1e-6), ("K", 1)])
def test_fft_math_units_switch_export_and_view_restore(plot, unit, scale) -> None:
    time = np.arange(1000) / 1000
    values = scale * (2 + 6 * np.cos(2 * np.pi * 50 * time))
    plot.set_axis(x_label="Time", y_label="Measurement", y_unit=unit)
    series = [plot.add_series(time + shift, values, scientific_time=time,
                              name=name, theoretical=theory)
              for shift, name, theory in [(0, "experiment", False), (1.75, "theory", True),
                                          (-2.25, "theory negative shift", True)]]
    control = plot.plot_widget.getPlotItem().ctrl
    control.fftCheck.setChecked(True)
    assert plot.bottom_axis.labelUnits == "Hz"
    assert plot.left_axis.labelUnits == unit
    assert "|rFFT|/N" in plot.left_axis.labelText
    assert "Power" not in control.fftCheck.text()
    for curve in series:
        x, y = curve.getData()
        assert x[50] == pytest.approx(50)
        assert y[50] == pytest.approx(3 * scale)
        assert y[0] == pytest.approx(2 * scale)
    svg = bytes(PlotSVGExporter(plot.plot_widget.getPlotItem()).export(toBytes=True))
    assert b"Frequency" in svg and b"Hz" in svg and b"|rFFT|/N" in svg
    for log in (True, False):
        control.logXCheck.setChecked(log)
        control.logYCheck.setChecked(log)
        assert plot.bottom_axis.labelUnits == "Hz"
        for curve in series:
            x, y = curve.getData()
            index = 49 if log else 50
            assert x[index] == pytest.approx(np.log10(50) if log else 50)
            assert y[index] == pytest.approx(np.log10(3 * scale) if log else 3 * scale)
    control.subtractMeanCheck.setChecked(True)
    control.logXCheck.setChecked(True)
    control.logYCheck.setChecked(True)
    view = ProjectDocument(plot_views=PlotViews_Capture({"test": plot}))
    restored = ProjectDocument.from_dict(view.to_dict())
    control.fftCheck.setChecked(False)
    control.subtractMeanCheck.setChecked(False)
    control.logXCheck.setChecked(False)
    control.logYCheck.setChecked(False)
    assert plot.bottom_axis.labelUnits == "s"
    PlotViews_Restore({"test": plot}, restored.plot_views)
    assert control.fftCheck.isChecked() and control.subtractMeanCheck.isChecked()
    assert control.logXCheck.isChecked() and control.logYCheck.isChecked()
    assert plot.bottom_axis.labelUnits == "Hz"
    plot._translations.set_locale("zh_CN")
    assert plot.bottom_axis.labelText == "频率"
    assert "模值" in plot.left_axis.labelText
    control.fftCheck.setChecked(False)
    control.logXCheck.setChecked(False)
    control.logYCheck.setChecked(False)
    control.subtractMeanCheck.setChecked(False)
    for curve in series:
        np.testing.assert_array_equal(curve.getOriginalDataset()[1], values)


def test_active_input_cropped_before_fft_and_csv_stays_full(plot, tmp_path: Path) -> None:
    time = np.arange(4000) / 1000
    values = np.where(time < 2, 100 * np.cos(2 * np.pi * 90 * time),
                      6 * np.cos(2 * np.pi * 50 * time))
    exp = plot.add_series(time, values, name="experiment")
    theory = plot.add_series(time + 100, values, name="theory", theoretical=True,
                             scientific_time=time, active_interval=(2, 3.999))
    negative = plot.add_series(time - 10, values, name="theory negative", theoretical=True,
                               scientific_time=time, active_interval=(2, 3.999))
    plot.set_regions({"active_test": (2, 3.999)})
    plot.set_axis(x_label="Time", y_label="Force", y_unit="N")
    control = plot.plot_widget.getPlotItem().ctrl
    control.fftCheck.setChecked(True)
    full = exp.getData()[1].copy()
    plot.analysis_scope_check.setChecked(True)
    for curve in (exp, theory, negative):
        frequency, magnitude = curve.getData()
        assert len(frequency) == 1001
        assert frequency[np.argmax(magnitude)] == pytest.approx(50)
        assert np.max(magnitude) == pytest.approx(3)
        np.testing.assert_array_equal(curve.getOriginalDataset()[1], values)
    assert not plot.active_region.isVisible()
    control.fftCheck.setChecked(False)
    assert plot.active_region.isVisible()
    np.testing.assert_array_equal(exp.getData()[0], time[2000:])
    plot.plot_widget.setXRange(2.2, 2.4, padding=0)
    plot.analysis_scope_check.setChecked(False)
    np.testing.assert_array_equal(exp.getData()[0], time)
    QApplication.processEvents()
    bounds = plot.plot_widget.getViewBox().viewRange()[0]
    assert bounds[0] <= 0 and bounds[1] >= time[-1]
    plot.analysis_scope_check.setChecked(True)
    target = tmp_path / "original.csv"
    CSVExporter(plot.plot_widget.getPlotItem()).export(str(target))
    with target.open(encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    assert len(rows) == 4001
    control.fftCheck.setChecked(True)
    plot.analysis_scope_check.setChecked(False)
    np.testing.assert_allclose(exp.getData()[1], full)
    plot.set_regions({"active_test": (20, 21)})
    plot.analysis_scope_check.setChecked(True)
    assert exp.getData() == (None, None)
    assert exp.analysis_notice == "samples"
    assert theory.analysis_notice == ""


@pytest.mark.parametrize("mode", ["subtractMeanCheck", "derivativeCheck", "phasemapCheck"])
def test_existing_derived_modes_receive_selected_samples(plot, mode) -> None:
    time, values = np.arange(6, dtype=float), np.array([0, 0, 1, 4, 9, 16.])
    curve = plot.add_series(time, values, name="source")
    plot.set_regions({"active_test": (2, 4)})
    plot.analysis_scope_check.setChecked(True)
    np.testing.assert_array_equal(curve.getData()[0], [2, 3, 4])
    getattr(plot.plot_widget.getPlotItem().ctrl, mode).setChecked(True)
    x, y = curve.getData()
    if mode == "subtractMeanCheck":
        np.testing.assert_allclose(y, values[2:5] - np.mean(values[2:5]))
    else:
        np.testing.assert_array_equal(y, [3, 5])
        np.testing.assert_array_equal(x, [1, 4] if mode == "phasemapCheck" else [2, 3])
    plot.set_regions({"active_test": (1, 4)})
    assert curve.getData()[1].size == (4 if mode == "subtractMeanCheck" else 3)
    np.testing.assert_array_equal(curve.getOriginalDataset()[1], values)


@pytest.mark.parametrize("mode", ["derivativeCheck", "phasemapCheck"])
def test_fft_remains_frequency_data_with_other_native_options_selected(plot, mode) -> None:
    time = np.arange(1000) / 1000
    values = 6 * np.cos(2 * np.pi * 50 * time)
    curve = plot.add_series(time, values, name="source")
    control = plot.plot_widget.getPlotItem().ctrl
    getattr(control, mode).setChecked(True)
    control.fftCheck.setChecked(True)
    frequency, magnitude = curve.getData()
    assert frequency[50] == pytest.approx(50)
    assert magnitude[50] == pytest.approx(3)
    assert plot.bottom_axis.labelUnits == "Hz"
    control.fftCheck.setChecked(False)
    assert getattr(control, mode).isChecked()
    assert curve.getData()[0].size == 999


def test_scoped_time_display_preserves_missing_clock_and_fft_rejects_it(plot) -> None:
    time = np.array([0., np.nan, 2., 3.])
    values = np.array([1., 2., 3., 4.])
    curve = plot.add_series(time, values, name="missing clock")
    plot.set_regions({"active_test": (0, 2)})
    plot.analysis_scope_check.setChecked(True)
    np.testing.assert_array_equal(curve.getData()[0], time[:3])
    plot.plot_widget.getPlotItem().ctrl.fftCheck.setChecked(True)
    assert curve.analysis_notice == "timestamps"
    assert curve.getData() == (None, None)


def test_scoped_fft_ignores_bad_values_outside_interval(plot) -> None:
    time = np.arange(5, dtype=float)
    values = np.array([np.nan, 3., 0., -3., 0.])
    curve = plot.add_series(time, values, name="outside gap")
    plot.set_regions({"active_test": (1, 4)})
    plot.analysis_scope_check.setChecked(True)
    plot.plot_widget.getPlotItem().ctrl.fftCheck.setChecked(True)
    assert curve.analysis_notice == ""
    np.testing.assert_allclose(curve.getData()[1], np.abs(np.fft.rfft(values[1:]) / 4))


@pytest.mark.parametrize("time,values,reason", [
    ([0], [1], "samples"),
    ([0, 1, 2], [1, np.nan, 1], "gaps"),
    ([0, .9, 2], [1, 2, 1], "nonuniform"),
    ([0, 0, 1], [1, 2, 1], "timestamps"),
])
def test_fft_rejects_invalid_input_without_interpolation(plot, time, values, reason) -> None:
    curve = plot.add_series(np.array(time), np.array(values), name="invalid")
    plot.plot_widget.getPlotItem().ctrl.fftCheck.setChecked(True)
    assert curve.analysis_notice == reason
    assert curve.getData() == (None, None)
    assert plot.plot_widget.getPlotItem().titleLabel.text
    plot.plot_widget.getPlotItem().ctrl.fftCheck.setChecked(False)
    np.testing.assert_array_equal(curve.getData()[1], values)
