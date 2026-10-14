from __future__ import annotations

import csv
import gc
from pathlib import Path

import numpy as np
import pyqtgraph as pg
import pytest
from pyqtgraph.exporters import CSVExporter, ImageExporter, SVGExporter
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from underline_retldc.gui.analysis_widgets import AnalysisPlotWidget
from underline_retldc.i18n.plot_qt import PLOT_QT_MESSAGES
from underline_retldc.i18n.service import TranslationService


@pytest.fixture
def plot() -> tuple[AnalysisPlotWidget, TranslationService]:
    app = QApplication.instance() or QApplication([])
    service = TranslationService("en_US")
    widget = AnalysisPlotWidget(service, regions_movable=True)
    widget.resize(900, 550)
    widget.set_empty_state("")
    widget.plot_widget.plot([0, 1, 2, 3], [0, 100, np.nan, 0], name="experiment [N]")
    widget.plot_widget.plot([.5, 1.5, 2.5], [0, 120, 0], name="theory [N]",
                            pen=pg.mkPen("#ff9f43", style=pg.QtCore.Qt.PenStyle.DashLine))
    assert app is not None
    yield widget, service
    widget._plot_ui_localizer.scene.exportDialog.close()
    widget.close()
    widget.deleteLater()
    QApplication.processEvents()


def _select_exporter(plot: AnalysisPlotWidget, exporter_type: type):
    dialog = plot.plot_widget.scene().exportDialog
    dialog.updateItemList(select=plot.plot_widget.getPlotItem())
    index = next(index for index in range(dialog.ui.formatList.count())
                 if dialog.ui.formatList.item(index).expClass == exporter_type)
    dialog.ui.formatList.setCurrentRow(index)
    return dialog, dialog.currentExporter


def test_plot_qt_catalog_and_axis_widgets_preserve_state(plot) -> None:
    widget, service = plot
    item = widget.plot_widget.getPlotItem()
    view = item.vb
    view.setRange(xRange=(-2, 9), yRange=(-5, 150), padding=0)
    view.enableAutoRange(axis=1, enable=.8)
    item.ctrl.downsampleSpin.setValue(3)
    item.ctrl.autoDownsampleCheck.setChecked(False)
    item.ctrl.fftCheck.setChecked(True)
    menu = view.menu
    menu.updateState()
    menu.ctrl[0].minText.setText("-2.125")
    menu.ctrl[0].maxText.setText("9.75")
    before = view.getState()
    control_values = item.stateGroup.state()
    for locale in ("zh_CN", "en_US", "zh_CN", "en_US"):
        service.set_locale(locale)
        QApplication.processEvents()
        gc.collect()
        chinese = locale == "zh_CN"
        assert menu.viewAll.text() == ("适应全部数据" if chinese else "View All")
        assert item.ctrlMenu.title() == ("绘图选项" if chinese else "Plot Options")
        assert item.ctrl.logXCheck.text() == ("X 轴对数显示" if chinese else "Log X")
        assert widget.plot_widget.scene().contextMenu[0].text() == (
            "导出当前图…" if chinese else "Export..."
        )
        assert menu.ctrl[0].minText.text() == "-2.125"
        assert menu.ctrl[0].maxText.text() == "9.75"
        state = view.getState()
        for key in ("autoRange", "mouseMode", "mouseEnabled", "xInverted", "yInverted"):
            assert state[key] == before[key]
        assert item.stateGroup.state() == control_values
        assert QCoreApplication.translate("QPlatformTheme", "Save") == (
            "保存" if chinese else "Save"
        )
    keys = {key for _context, _source, key in PLOT_QT_MESSAGES}
    assert all(service.translate(key) != key for key in keys)
    assert QCoreApplication.translate("Unrelated", "View All") == "View All"


def test_export_dialog_locale_preserves_format_and_csv_values(plot, tmp_path: Path) -> None:
    widget, service = plot
    dialog, exporter = _select_exporter(widget, CSVExporter)
    params = exporter.parameters()
    params["separator"] = "tab"
    params["precision"] = 8
    params["columnMode"] = "(x,y,y,y) for all plots"
    english = tmp_path / "english.tsv"
    exporter.export(str(english))
    for locale in ("zh_CN", "en_US", "zh_CN"):
        service.set_locale(locale)
        QApplication.processEvents()
        assert dialog.currentExporter is exporter
        assert params["separator"] == "tab"
        assert params["precision"] == 8
        assert params["columnMode"] == "(x,y,y,y) for all plots"
        assert params.param("separator").name() == "separator"
        selected = next(iter(params.param("separator").items)).widget.currentText()
        assert selected == ("制表符" if locale == "zh_CN" else "tab")
        label = next(iter(params.param("separator").items)).displayLabel.text()
        assert label == selected
        assert params.name() == "params"
        assert params.title() == ("参数" if locale == "zh_CN" else "Parameter")
        assert dialog.ui.formatList.currentItem().expClass == CSVExporter
    assert params.param("precision").title() == "小数位数上限"
    assert dialog.ui.exportBtn.text() == "导出当前图"
    assert dialog.ui.itemTree.topLevelItem(0).text(0) == "整个场景"
    chinese = tmp_path / "chinese.tsv"
    exporter.export(str(chinese))
    assert chinese.read_bytes() == english.read_bytes()
    rows = list(csv.reader(chinese.open(encoding="utf-8"), delimiter="\t"))
    assert rows[0] == ["experiment [N]_x", "experiment [N]_y", "theory [N]_y"]
    assert rows[2] == ["1.", "100.", "120."]
    params["columnMode"] = "(x,y) per plot"
    separate = tmp_path / "separate.tsv"
    exporter.export(str(separate))
    rows = list(csv.reader(separate.open(encoding="utf-8"), delimiter="\t"))
    assert rows[0] == ["experiment [N]_x", "experiment [N]_y", "theory [N]_x", "theory [N]_y"]
    assert rows[1][2] == "0.5"


def test_image_and_svg_exports_keep_overlay_arrays_and_options(plot, tmp_path: Path) -> None:
    widget, service = plot
    original = [item.getOriginalDataset() for item in widget.plot_widget.listDataItems()]
    dialog, exporter = _select_exporter(widget, ImageExporter)
    exporter.parameters()["width"] = 600
    exporter.parameters()["invertValue"] = True
    options = {child.name(): child.value() for child in exporter.parameters().children()}
    service.set_locale("zh_CN")
    assert dialog.currentExporter is exporter
    assert {child.name(): child.value() for child in exporter.parameters().children()} == options
    assert exporter.parameters().param("invertValue").title() == "明暗反转"
    dialog.selectBox.hide()
    image = exporter.export(toBytes=True)
    assert not image.isNull() and image.width() == 600
    assert image.save(str(tmp_path / "overlay.png"))
    dialog, svg = _select_exporter(widget, SVGExporter)
    assert svg.parameters().param("scaling stroke").title() == "缩放线宽"
    dialog.selectBox.hide()
    # Qt 6.11.1 emits paths the upstream 0.14 SVG coordinate parser cannot read.
    # Keep the format and match the unadapted renderer's failure rather than mask it.
    with pytest.raises(ValueError) as baseline:
        SVGExporter(widget.plot_widget.getPlotItem()).export(toBytes=True)
    with pytest.raises(ValueError) as localized:
        svg.export(toBytes=True)
    assert str(localized.value) == str(baseline.value)
    for item, expected in zip(widget.plot_widget.listDataItems(), original, strict=True):
        actual = item.getOriginalDataset()
        np.testing.assert_array_equal(actual[0], expected[0])
        np.testing.assert_array_equal(actual[1], expected[1])
