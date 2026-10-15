"""Application-local pyqtgraph 0.14 SVG compatibility adapter.

Retains upstream per-item reconstruction, clipping and coordinate transforms.
Qt 6.11 close-path tokens have no coordinates and must pass through unchanged.
No registration or mutation of pyqtgraph globals. Upstream names remain for diff review.
Source: pyqtgraph/exporters/SVGExporter.py, 0.14.0 (LF distribution file SHA-256)
5cbb8c90b6bed9ae14cd57ea7a7fcf70efb7662e6896267f9c23cf075445a0bc.

Copyright (c) 2012  University of North Carolina at Chapel Hill
Luke Campagnola    ('luke.campagnola@%s.com' % 'gmail')

The MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy of this software
and associated documentation files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import contextlib
import re
import xml.dom.minidom as xml
from typing import Any

import numpy as np
from pyqtgraph import debug
from pyqtgraph import functions as fn
from pyqtgraph.exporters import SVGExporter
from pyqtgraph.Qt import QtCore, QtGui, QtSvg, QtWidgets

translate = QtCore.QCoreApplication.translate


class PlotSVGExporter(SVGExporter):
    """Keep upstream parameters, using the local close-path-compatible renderer."""

    def export(
        self,
        fileName: str | None = None,
        toBytes: bool = False,
        copy: bool = False,
    ) -> bytes | None:
        app = QtWidgets.QApplication.instance()
        if app is None or QtCore.QThread.currentThread() != app.thread():
            raise RuntimeError("Plot SVG export must run on the GUI thread")
        if toBytes is False and copy is False and fileName is None:
            self.fileSaveDialog(
                filter=f"{translate('Exporter', 'Scalable Vector Graphics')} (*.svg)"
            )
            return

        ## Qt's SVG generator is not complete. (notably, it lacks clipping)
        ## Instead, we will use Qt to generate SVG for each item independently,
        ## then manually reconstruct the entire document.
        options = {ch.name(): ch.value() for ch in self.params.children()}
        options["background"] = self.params["background"]
        options["width"] = self.params["width"]
        options["height"] = self.params["height"]
        xml = generateSvg(self.item, options)
        if toBytes:
            return xml.encode("UTF-8")
        elif copy:
            md = QtCore.QMimeData()
            md.setData("image/svg+xml", QtCore.QByteArray(xml.encode("UTF-8")))
            QtWidgets.QApplication.clipboard().setMimeData(md)
        else:
            with open(fileName, "wb") as fh:
                fh.write(xml.encode("utf-8"))


# Includes space for extra attributes
xmlHeader = """\
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
 version="1.2" baseProfile="tiny"%s>
<title>pyqtgraph SVG export</title>
<desc>Generated with Qt and pyqtgraph</desc>
<style>
    image {
        image-rendering: crisp-edges;
        image-rendering: -moz-crisp-edges;
        image-rendering: pixelated;
    }
</style>
"""


def generateSvg(item: Any, options: dict[str, Any] | None = None) -> str:
    if options is None:
        options = {}
    try:
        node, defs = _generateItemSvg(item, options=options)
    finally:
        ## reset export mode for all items in the tree
        if isinstance(item, QtWidgets.QGraphicsScene):
            items = item.items()
        else:
            items = [item]
            for i in items:
                items.extend(i.childItems())
        for i in items:
            if hasattr(i, "setExportMode"):
                i.setExportMode(False)
    cleanXml(node)

    defsXml = "<defs>\n"
    for d in defs:
        defsXml += d.toprettyxml(indent="    ")
    defsXml += "</defs>\n"
    svgAttributes = f' viewBox ="0 0 {int(options["width"])} {int(options["height"])}"'
    c = options["background"]
    backgroundtag = (
        f'<rect width="100%" height="100%" fill="{c.name()}" fill-opacity="{c.alphaF()}" />\n'
    )
    return (
        (xmlHeader % svgAttributes)
        + backgroundtag
        + defsXml
        + node.toprettyxml(indent="    ")
        + "\n</svg>\n"
    )


def _generateItemSvg(
    item: Any,
    nodes: dict[str, Any] | None = None,
    root: Any = None,
    options: dict[str, Any] | None = None,
) -> tuple[Any, list[Any]] | None:
    """This function is intended to work around some issues with Qt's SVG generator
    and SVG in general.

    .. warning::
        This function, while documented, is not considered part of the public
        API. The reason for its documentation is for ease of referencing by
        :func:`~pyqtgraph.GraphicsItem.generateSvg`. There should be no need
        to call this function explicitly.

    1. Qt SVG does not implement clipping paths. This is absurd.
    The solution is to let Qt generate SVG for each item independently,
    then glue them together manually with clipping.  The format Qt generates
    for all items looks like this:

    .. code-block:: xml

        <g>
            <g transform="matrix(...)">
                one or more of: <path/> or <polyline/> or <text/>
            </g>
            <g transform="matrix(...)">
                one or more of: <path/> or <polyline/> or <text/>
            </g>
            . . .
        </g>

    2. There seems to be wide disagreement over whether path strokes
    should be scaled anisotropically.  Given that both inkscape and
    illustrator seem to prefer isotropic scaling, we will optimize for
    those cases.

    .. note::

        see: http://web.mit.edu/jonas/www/anisotropy/

    3. Qt generates paths using non-scaling-stroke from SVG 1.2, but
    inkscape only supports 1.1.

    Both 2 and 3 can be addressed by drawing all items in world coordinates.

    Parameters
    ----------
    item : :class:`~pyqtgraph.GraphicsItem`
        GraphicsItem to generate SVG of
    nodes : dict of str, optional
        dictionary keyed on graphics item names, values contains the
        XML elements, by default None
    root : :class:`~pyqtgraph.GraphicsItem`, optional
        root GraphicsItem, if none, assigns to `item`, by default None
    options : dict of str, optional
        Options to be applied to the generated XML, by default None

    Returns
    -------
    tuple
        tuple where first element is XML element, second element is
        a list of child GraphicItems XML elements
    """

    profiler = debug.Profiler()
    if options is None:
        options = {}

    if nodes is None:  ## nodes maps all node IDs to their XML element.
        ## this allows us to ensure all elements receive unique names.
        nodes = {}

    if root is None:
        root = item

    ## Skip hidden items
    if hasattr(item, "isVisible") and not item.isVisible():
        return None

    with contextlib.suppress(NotImplementedError, AttributeError):
        # If this item defines its own SVG generator, use that.
        return item.generateSvg(nodes)
    ## Generate SVG text for just this item (exclude its children; we'll handle them later)
    if isinstance(item, QtWidgets.QGraphicsScene):
        xmlStr = "<g>\n</g>\n"
        doc = xml.parseString(xmlStr)
        childs = [i for i in item.items() if i.parentItem() is None]
    elif item.__class__.paint == QtWidgets.QGraphicsItem.paint:
        xmlStr = "<g>\n</g>\n"
        doc = xml.parseString(xmlStr)
        childs = item.childItems()
    else:
        childs = item.childItems()

        tr = itemTransform(item, item.scene())
        # offset to corner of root item
        if isinstance(root, QtWidgets.QGraphicsScene):
            rootPos = QtCore.QPoint(0, 0)
        else:
            rootPos = root.scenePos()

        # handle rescaling from the export dialog
        if hasattr(root, "boundingRect"):
            resize_x = options["width"] / root.boundingRect().width()
            resize_y = options["height"] / root.boundingRect().height()
        else:
            resize_x = resize_y = 1
        tr2 = QtGui.QTransform(resize_x, 0, 0, resize_y, -rootPos.x(), -rootPos.y())
        tr = tr * tr2
        # tr = manipulate * tr * tr2

        arr = QtCore.QByteArray()
        buf = QtCore.QBuffer(arr)
        svg = QtSvg.QSvgGenerator()
        svg.setOutputDevice(buf)
        dpi = QtGui.QGuiApplication.primaryScreen().logicalDotsPerInchX()
        svg.setResolution(int(dpi))
        p = QtGui.QPainter()
        p.begin(svg)
        if hasattr(item, "setExportMode"):
            item.setExportMode(True, {"painter": p})
        try:
            p.setTransform(tr)
            opt = QtWidgets.QStyleOptionGraphicsItem()
            if item.flags() & QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption:
                opt.exposedRect = item.boundingRect()
            item.paint(p, opt, None)
        finally:
            p.end()
            ## Can't do this here--we need to wait until all children have painted as well.
            ## this is taken care of in generateSvg instead.
            # if hasattr(item, 'setExportMode'):
            #     item.setExportMode(False)
        doc = xml.parseString(arr.data())

    try:
        ## Get top-level group for this item
        g1 = doc.getElementsByTagName("g")[0]
        defs = doc.getElementsByTagName("defs")
        if len(defs) > 0:
            defs = [n for n in defs[0].childNodes if isinstance(n, xml.Element)]
    except IndexError:
        print(doc.toxml())
        raise
    profiler("render")
    ## Get rid of group transformation matrices by applying
    ## transformation to inner coordinates
    correctCoordinates(g1, defs, item, options)
    profiler("correct")

    ## decide on a name for this item
    baseName = item.__class__.__name__
    i = 1
    while True:
        name = f"{baseName}_{i}"
        if name not in nodes:
            break
        i += 1
    nodes[name] = g1
    g1.setAttribute("id", name)

    ## If this item clips its children, we need to take care of that.
    childGroup = g1  ## add children directly to this node unless we are clipping
    if (
        not isinstance(item, QtWidgets.QGraphicsScene)
        and item.flags() & item.GraphicsItemFlag.ItemClipsChildrenToShape
    ):
        ## Generate svg for just the path
        path = QtWidgets.QGraphicsPathItem(item.mapToScene(item.shape()))
        item.scene().addItem(path)
        try:
            pathNode = _generateItemSvg(path, root=root, options=options)[0].getElementsByTagName(
                "path"
            )[0]
            # assume <defs> for this path is empty.. possibly problematic.
        finally:
            item.scene().removeItem(path)

            ## and for the clipPath element
        clip = f"{name}_clip"
        clipNode = g1.ownerDocument.createElement("clipPath")
        clipNode.setAttribute("id", clip)
        clipNode.appendChild(pathNode)
        g1.appendChild(clipNode)

        childGroup = g1.ownerDocument.createElement("g")
        childGroup.setAttribute("clip-path", f"url(#{clip})")
        g1.appendChild(childGroup)
    profiler("clipping")

    ## Add all child items as sub-elements.
    childs.sort(key=lambda c: c.zValue())
    for ch in childs:
        csvg = _generateItemSvg(ch, nodes, root, options=options)
        if csvg is None:
            continue
        cg, cdefs = csvg
        childGroup.appendChild(
            cg
        )  ### this isn't quite right--some items draw below their parent (good enough for now)
        defs.extend(cdefs)

    profiler("children")
    return g1, defs


def correctCoordinates(
    node: Any,
    defs: list[Any],
    item: Any,
    options: dict[str, Any],
) -> None:
    # correct the defs in the linearGradient
    for d in defs:
        if d.tagName == "linearGradient":
            # reset "gradientUnits" attribute to SVG default value
            d.removeAttribute("gradientUnits")

            # replace with percentages
            for coord in ("x1", "x2", "y1", "y2"):
                if coord.startswith("x"):
                    denominator = item.boundingRect().width()
                else:
                    denominator = item.boundingRect().height()
                percentage = round(float(d.getAttribute(coord)) * 100 / denominator)
                d.setAttribute(coord, f"{percentage}%")

            # replace stops with percentages
            for child in filter(
                lambda e: isinstance(e, xml.Element) and e.tagName == "stop", d.childNodes
            ):
                offset = child.getAttribute("offset")
                try:
                    child.setAttribute("offset", f"{round(float(offset) * 100)}%")
                except ValueError:
                    # offset attribute could not be converted to float
                    # must be one of the other SVG accepted formats
                    continue

    ## Remove transformation matrices from <g> tags by applying matrix to coordinates inside.
    ## Each item is represented by a single top-level group with one or more groups inside.
    ## Each inner group contains one or more drawing primitives, possibly of different types.
    groups = node.getElementsByTagName("g")

    # Keep text in separate groups because its transform remains unchanged.
    groups2 = []
    for grp in groups:
        subGroups = [grp.cloneNode(deep=False)]
        textGroup = None
        for ch in grp.childNodes[:]:
            if isinstance(ch, xml.Element):
                if textGroup is None:
                    textGroup = ch.tagName == "text"
                if ch.tagName == "text":
                    if textGroup is False:
                        subGroups.append(grp.cloneNode(deep=False))
                        textGroup = True
                else:
                    if textGroup is True:
                        subGroups.append(grp.cloneNode(deep=False))
                        textGroup = False
            subGroups[-1].appendChild(ch)
        groups2.extend(subGroups)
        for sg in subGroups:
            node.insertBefore(sg, grp)
        node.removeChild(grp)
    groups = groups2

    for grp in groups:
        matrix = grp.getAttribute("transform")
        match = re.match(r"matrix\((.*)\)", matrix)
        if match is None:
            vals = [1, 0, 0, 1, 0, 0]
        else:
            vals = [float(a) for a in match.groups()[0].split(",")]
        tr = np.array([[vals[0], vals[2], vals[4]], [vals[1], vals[3], vals[5]]])

        removeTransform = False
        for ch in grp.childNodes:
            if not isinstance(ch, xml.Element):
                continue
            if ch.tagName == "polyline":
                removeTransform = True
                coords = np.array(
                    [
                        [float(a) for a in c.split(",")]
                        for c in ch.getAttribute("points").strip().split(" ")
                    ]
                )
                coords = fn.transformCoordinates(tr, coords, transpose=True)
                ch.setAttribute("points", " ".join([",".join([str(a) for a in c]) for c in coords]))
            elif ch.tagName == "path":
                removeTransform = True
                newCoords = ""
                oldCoords = ch.getAttribute("d").strip()
                if oldCoords == "":
                    continue
                for c in oldCoords.split():
                    # Z/z closes the subpath; it has no position to transform.
                    if c in {"Z", "z"}:
                        newCoords += c + " "
                        continue
                    x, y = c.split(",")
                    if x[0].isalpha():
                        t = x[0]
                        x = x[1:]
                    else:
                        t = ""
                    nc = fn.transformCoordinates(
                        tr, np.array([[float(x), float(y)]]), transpose=True
                    )
                    newCoords += t + str(nc[0, 0]) + "," + str(nc[0, 1]) + " "
                # If coords start with L instead of M, then the entire path will not be rendered.
                # Qt skips first points containing NaN on export.
                if newCoords[0] != "M":
                    newCoords = f"M{newCoords[1:]}"
                ch.setAttribute("d", newCoords)
            elif ch.tagName == "text":
                removeTransform = False
                # Leave text coordinates and their group transform unchanged.
                # c = np.array([
                #     [float(ch.getAttribute('x')), float(ch.getAttribute('y'))],
                #     [float(ch.getAttribute('font-size')), 0],
                #     [0,0]])
                # c = fn.transformCoordinates(tr, c, transpose=True)
                # ch.setAttribute('x', str(c[0,0]))
                # ch.setAttribute('y', str(c[0,1]))
                # fs = c[1]-c[2]
                # fs = (fs**2).sum()**0.5
                # ch.setAttribute('font-size', str(fs))

                ## Correct some font information
                families = ch.getAttribute("font-family").split(",")
                if len(families) == 1:
                    font = QtGui.QFont(families[0].strip('" '))
                    if font.styleHint() == font.StyleHint.SansSerif:
                        families.append("sans-serif")
                    elif font.styleHint() == font.StyleHint.Serif:
                        families.append("serif")
                    elif font.styleHint() == font.StyleHint.Courier:
                        families.append("monospace")
                    ch.setAttribute(
                        "font-family",
                        ", ".join([f if " " not in f else f'"{f}"' for f in families]),
                    )

            ## correct line widths if needed
            if (
                removeTransform
                and ch.getAttribute("vector-effect") != "non-scaling-stroke"
                and grp.getAttribute("stroke-width") != ""
            ):
                w = float(grp.getAttribute("stroke-width"))
                s = fn.transformCoordinates(tr, np.array([[w, 0], [0, 0]]), transpose=True)
                w = ((s[0] - s[1]) ** 2).sum() ** 0.5
                ch.setAttribute("stroke-width", str(w))

            # Remove non-scaling-stroke if requested
            if (
                options.get("scaling stroke") is True
                and ch.getAttribute("vector-effect") == "non-scaling-stroke"
            ):
                ch.removeAttribute("vector-effect")

        if removeTransform:
            grp.removeAttribute("transform")


def itemTransform(item: Any, root: Any) -> QtGui.QTransform:
    ## Return the transformation mapping item to root
    ## (actually to parent coordinate system of root)

    if item is root:
        tr = QtGui.QTransform()
        tr.translate(*item.pos())
        tr = tr * item.transform()
        return tr

    if item.flags() & item.GraphicsItemFlag.ItemIgnoresTransformations:
        pos = item.pos()
        parent = item.parentItem()
        if parent is not None:
            pos = itemTransform(parent, root).map(pos)
        tr = QtGui.QTransform()
        tr.translate(pos.x(), pos.y())
        tr = item.transform() * tr
    else:
        ## find next parent that is either the root item or
        ## an item that ignores its transformation
        nextRoot = item
        while True:
            nextRoot = nextRoot.parentItem()
            if nextRoot is None:
                nextRoot = root
                break
            if nextRoot is root or (
                nextRoot.flags() & nextRoot.GraphicsItemFlag.ItemIgnoresTransformations
            ):
                break

        if isinstance(nextRoot, QtWidgets.QGraphicsScene):
            tr = item.sceneTransform()
        else:
            tr = itemTransform(nextRoot, root) * item.itemTransform(nextRoot)[0]

    return tr


def cleanXml(node: Any) -> None:
    ## remove extraneous text; let the xml library do the formatting.
    hasElement = False
    nonElement = []
    for ch in node.childNodes:
        if isinstance(ch, xml.Element):
            hasElement = True
            cleanXml(ch)
        else:
            nonElement.append(ch)

    if hasElement:
        for ch in nonElement:
            node.removeChild(ch)
    elif node.tagName == "g":  ## remove childless groups
        node.parentNode.removeChild(node)
