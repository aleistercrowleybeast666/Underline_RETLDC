from __future__ import annotations

import xml.dom.minidom as xml
from xml.etree import ElementTree as ET

import numpy as np
import pyqtgraph as pg
import pytest
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from underline_retldc.gui.plot_svg import PlotSVGExporter, correctCoordinates


@pytest.mark.parametrize("close", ["Z", "z"])
def test_svg_close_command_preserves_affine_geometry(close: str) -> None:
    document = xml.parseString(
        '<g><g transform="matrix(2,0,0,3,10,-4)" stroke-width="2">'
        f'<path d="M0,0 L2,0 L2,2 {close} M3,3 L4,4 {close}"/>'
        '</g></g>'
    )
    correctCoordinates(document.documentElement, [], None, {})
    group = document.getElementsByTagName("g")[1]
    path = document.getElementsByTagName("path")[0]
    assert not group.hasAttribute("transform")
    assert path.getAttribute("d").split() == [
        "M10.0,-4.0", "L14.0,-4.0", "L14.0,2.0", close,
        "M16.0,5.0", "L18.0,8.0", close,
    ]
    assert float(path.getAttribute("stroke-width")) == 4.0


def _orange_mask(image: QImage) -> np.ndarray:
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    pixels = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
        image.height(), image.bytesPerLine() // 4, 4,
    )[:, :image.width(), :3].astype(int)
    return (pixels[:, :, 0] > 200) & (pixels[:, :, 1] > 90) & (pixels[:, :, 1] < 190) \
        & (pixels[:, :, 2] < 100)


@pytest.mark.parametrize("width,scaling", [(600, False), (900, True)])
def test_svg_zoom_clipping_nan_gap_and_resizing(width: int, scaling: bool) -> None:
    app = QApplication.instance() or QApplication([])
    widget = pg.PlotWidget(background="w")
    widget.resize(900, 550)
    x = np.array([-2, 0, .5, 1, 1.5, 2, 4])
    y = np.array([50, 50, 50, np.nan, 50, 50, 50])
    curve = widget.plot(x, y, pen=pg.mkPen("#ff9f43", width=3), connect="finite")
    # Keep off-view samples in the rendering input: SVG clipping must hide them.
    curve.setClipToView(False)
    widget.setRange(xRange=(0, 2), yRange=(0, 150), padding=0)
    widget.show()
    app.processEvents()
    try:
        item = widget.getPlotItem()
        exporter = PlotSVGExporter(item)
        exporter.parameters()["width"] = width
        exporter.parameters()["scaling stroke"] = scaling
        data = exporter.export(toBytes=True)
        root = ET.fromstring(data)
        clips = root.findall(".//{*}clipPath")
        assert clips and all(node.findall(".//{*}path") for node in clips)
        renderer = QSvgRenderer(data)
        assert renderer.isValid()
        height = int(exporter.parameters()["height"])
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            renderer.render(painter)
        finally:
            painter.end()
        mask = _orange_mask(image)
        ys, xs = np.where(mask)
        assert len(xs) > width // 4
        source = item.sceneBoundingRect()
        view = item.vb.sceneBoundingRect()
        left = (view.left() - source.left()) * width / source.width()
        right = (view.right() - source.left()) * width / source.width()
        clip = next(node for node in clips if node.attrib["id"].startswith("ViewBox_"))
        points = [token[1:].split(",") for token in clip[0].attrib["d"].split()
                  if token.startswith(("M", "L"))]
        clip_x = [float(point[0]) for point in points]
        assert min(clip_x) == pytest.approx(left, abs=.01)
        assert max(clip_x) == pytest.approx(right, abs=.01)
        clipped_group = next(node for node in root.iter()
                             if node.attrib.get("clip-path") == f'url(#{clip.attrib["id"]})')
        assert any(node.attrib.get("id", "").startswith("PlotCurveItem_")
                   for node in clipped_group.iter())
        # Qt's renderer ignores clipPath; assert the SVG structure above and
        # compare raster geometry only inside the viewport. Browser QA checks clipping.
        mask[:, :round(left)] = False
        mask[:, round(right) + 1:] = False
        ys, xs = np.where(mask)
        center = item.vb.mapViewToScene(QPointF(1, 50))
        gap_x = round((center.x() - source.left()) * width / source.width())
        assert not mask[:, gap_x - 10:gap_x + 10].any()
        # Independent raster exporter must place both clipped segments similarly.
        png = ImageExporter(item)
        png.parameters()["width"] = width
        reference_y, reference_x = np.where(_orange_mask(png.export(toBytes=True)))
        assert abs(float(np.median(ys)) - float(np.median(reference_y))) <= 2
        assert abs(int(xs.min()) - int(reference_x.min())) <= 2
        assert abs(int(xs.max()) - int(reference_x.max())) <= 2
        np.testing.assert_array_equal(curve.getOriginalDataset()[0], x)
        np.testing.assert_array_equal(curve.getOriginalDataset()[1], y)
        assert not curve.curve._exportOpts
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()
