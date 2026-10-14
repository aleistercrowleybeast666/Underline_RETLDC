from __future__ import annotations

from collections.abc import Mapping
from itertools import count
from typing import Any
from weakref import WeakSet

import pyqtgraph as pg
from pyqtgraph.exporters import CSVExporter
from pyqtgraph.GraphicsScene.exportDialog import ExportDialog
from PySide6.QtCore import QLibraryInfo, QObject, QSignalBlocker, Qt, QThread, QTranslator
from PySide6.QtWidgets import QApplication, QComboBox, QWidgetAction

from underline_retldc.i18n.plot_qt import PLOT_QT_MESSAGES
from underline_retldc.i18n.service import TranslationService


class PlotQtTranslator(QTranslator):
    """Use the upstream Qt translation hooks; leave unrecognized text to Qt."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.service: TranslationService | None = None
        self.keys = {(context, source): key for context, source, key in PLOT_QT_MESSAGES}

    def isEmpty(self) -> bool:
        return False

    def translate(
        self, context: str, sourceText: str, disambiguation: str | None = None, n: int = -1,
    ) -> str | None:
        key = self.keys.get((context, sourceText))
        if key is None or self.service is None:
            # A null QString permits Qt's next translator/source fallback. An
            # empty Python string is a valid blank translation in PySide6.
            return None
        return self.service.translate(key, sourceText)


class PlotQtTranslations(QObject):
    """Application-owned Qt catalogs, following the application's one UI locale."""

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self.app = app
        self.translator = PlotQtTranslator(self)
        self.qt_base = QTranslator(self)
        self.qt_base.load(
            "qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
        )
        self.service: TranslationService | None = None

    def bind(self, service: TranslationService) -> None:
        if QThread.currentThread() != self.app.thread():
            raise RuntimeError("Plot translation binding must run on the GUI thread")
        if self.service is service:
            return
        if self.service is not None:
            self.service.locale_changed.disconnect(self.refresh)
        self.service = service
        self.translator.service = service
        service.locale_changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args: object) -> None:
        if QThread.currentThread() != self.app.thread():
            raise RuntimeError("Plot translation updates must run on the GUI thread")
        self.app.removeTranslator(self.translator)
        self.app.removeTranslator(self.qt_base)
        if self.service is not None and self.service.locale == "zh_CN":
            self.app.installTranslator(self.qt_base)
        self.app.installTranslator(self.translator)


def PlotQtTranslations_Ensure(service: TranslationService) -> None:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Plot UI translation requires QApplication")
    owner = getattr(app, "_retldc_plot_translations", None)
    if owner is None:
        owner = PlotQtTranslations(app)
        app._retldc_plot_translations = owner
    owner.bind(service)


def _text(service: TranslationService, context: str, source: str) -> str:
    key = next((key for ctx, text, key in PLOT_QT_MESSAGES
                if ctx == context and text == source), None)
    return service.translate(key, source) if key is not None else source


def _submenu_for_widget(menu: Any, widget: Any) -> Any | None:
    for action in menu.actions():
        child = action.menu()
        if child is not None and any(
            isinstance(entry, QWidgetAction) and entry.defaultWidget() == widget
            for entry in child.actions()
        ):
            return child
    return None


class PlotCSVExporter(CSVExporter):
    """Reset upstream 0.14's per-export column index so repeated shared-X keeps X."""

    def export(self, fileName: str | None = None) -> None:
        self.index_counter = count(start=0)
        super().export(fileName)


class LocalizedPlotExportDialog(ExportDialog):
    """Instance adapter for upstream hardcoded labels and display-only list limits."""

    def __init__(self, scene: Any, service: TranslationService, owner: Any) -> None:
        self.translations = service
        self._bool_connections: WeakSet[Any] = WeakSet()
        super().__init__(scene)
        # It is a separate window, but must be destroyed with its plot owner.
        # Scene-only Python references otherwise leave a live dialog with a dead scene.
        self.setParent(owner, Qt.WindowType.Window)
        service.locale_changed.connect(self.retranslate)
        self.retranslate()

    def updateItemList(self, select: Any = None) -> None:
        super().updateItemList(select)
        self._items_retranslate()

    def exportFormatChanged(self, item: Any, previous: Any) -> None:
        if item is not None and item.expClass == CSVExporter:
            exporter = PlotCSVExporter(item=self.ui.itemTree.currentItem().gitem)
            self.ui.paramTree.setParameters(exporter.parameters())
            self.currentExporter = exporter
            self.ui.copyBtn.setEnabled(exporter.allowCopy)
        else:
            super().exportFormatChanged(item, previous)
        self._parameters_retranslate()

    def show(self, item: Any = None) -> None:
        super().show(item)
        self.retranslate()

    def retranslate(self, *_args: object) -> None:
        self.ui.retranslateUi(self)
        self.ui.paramTree.setHeaderLabels([
            _text(self.translations, "PlotExport", "Parameter"),
            _text(self.translations, "PlotExport", "Value"),
        ])
        self._items_retranslate()
        for index in range(self.ui.formatList.count()):
            item = self.ui.formatList.item(index)
            item.setText(_text(self.translations, "Exporter", item.expClass.Name))
            if item.expClass.Name == "CSV of original plot data":
                item.setToolTip(self.translations.translate("plot.export.csv_tip"))
        self._parameters_retranslate()

    def _items_retranslate(self) -> None:
        def visit(item: Any) -> None:
            if item.gitem == self.scene:
                source = "Entire Scene"
            elif isinstance(item.gitem, pg.PlotItem):
                source = "Plot"
            elif isinstance(item.gitem, pg.ViewBox):
                source = "ViewBox"
            else:
                source = None
            if source is not None:
                item.setText(0, _text(self.translations, "PlotExport", source))
            for index in range(item.childCount()):
                visit(item.child(index))

        for index in range(self.ui.itemTree.topLevelItemCount()):
            visit(self.ui.itemTree.topLevelItem(index))

    def _parameters_retranslate(self) -> None:
        exporter = self.currentExporter
        if exporter is None or exporter.parameters() is None:
            return
        if (not type(exporter).__module__.startswith("pyqtgraph.exporters.")
                and not isinstance(exporter, PlotCSVExporter)):
            return
        if exporter.parameters().name() == "params":
            exporter.parameters().setOpts(title=_text(self.translations, "PlotExport", "Parameter"))
        for parameter in exporter.parameters().children():
            name = parameter.name()
            title = _text(self.translations, "Exporter", name)
            if title != name or any(ctx == "Exporter" and source == name
                                    for ctx, source, _key in PLOT_QT_MESSAGES):
                parameter.setOpts(title=title)
            if name == "scaling stroke":
                parameter.setOpts(tip=self.translations.translate("plot.export.svg_stroke_tip"))
            elif name == "columnMode":
                parameter.setOpts(tip=self.translations.translate("plot.export.csv_tip"))
            if name in {"separator", "columnMode"}:
                limits = parameter.opts.get("limits", ())
                values = tuple(limits.values()) if isinstance(limits, Mapping) else tuple(limits)
                if all(value in {"comma", "tab", "(x,y) per plot", "(x,y,y,y) for all plots"}
                       for value in values):
                    current = parameter.value()
                    items = tuple(parameter.items)
                    blockers = [QSignalBlocker(item.widget) for item in items
                                if isinstance(item.widget, QComboBox)]
                    try:
                        parameter.setLimits({
                            _text(self.translations, "PlotExport", value): value for value in values
                        })
                        for item in items:
                            item.setValue(current)
                            item.updateDisplayLabel()
                    finally:
                        del blockers
            if parameter.opts.get("type") == "bool" and parameter not in self._bool_connections:
                parameter.sigValueChanged.connect(self._bool_labels_refresh)
                self._bool_connections.add(parameter)
        self._bool_labels_refresh()

    def _bool_labels_refresh(self, *_args: object) -> None:
        exporter = self.currentExporter
        if exporter is None or exporter.parameters() is None:
            return
        for parameter in exporter.parameters().children():
            if parameter.opts.get("type") == "bool":
                for item in parameter.items:
                    item.displayLabel.setText(
                        _text(self.translations, "PlotExport", str(parameter.value())),
                    )


class PlotUiLocalizer(QObject):
    """Keep upstream controls/actions intact; refresh their presentation in place."""

    def __init__(self, plot: Any, service: TranslationService, parent: QObject) -> None:
        super().__init__(parent)
        self.plot = plot
        self.translations = service
        self.scene = plot.scene()
        self._menu_objects: list[Any] = []

        def retain(menu: Any) -> None:
            self._menu_objects.append(menu)
            for action in menu.actions():
                self._menu_objects.append(action)
                if isinstance(action, QWidgetAction):
                    self._menu_objects.append(action.defaultWidget())
                if action.menu() is not None:
                    retain(action.menu())

        retain(plot.getPlotItem().ctrlMenu)
        retain(plot.getPlotItem().vb.menu)
        self.scene.exportDialog = LocalizedPlotExportDialog(self.scene, service, plot)
        service.locale_changed.connect(self.retranslate)
        self.retranslate()

    def retranslate(self, *_args: object) -> None:
        service = self.translations
        item = self.plot.getPlotItem()
        control = item.ctrl
        control.retranslateUi(control.transformGroup.parentWidget())
        item.ctrlMenu.setTitle(_text(service, "PlotItem", "Plot Options"))
        for source, group in (
            ("Transforms", control.transformGroup), ("Downsample", control.decimateGroup),
            ("Average", control.averageGroup), ("Alpha", control.alphaGroup),
            ("Grid", control.gridGroup), ("Points", control.pointsGroup),
        ):
            menu = _submenu_for_widget(item.ctrlMenu, group)
            if menu is not None:
                menu.setTitle(_text(service, "PlotItem", source))
        menu = item.vb.menu
        menu.setTitle(_text(service, "ViewBox", "ViewBox options"))
        menu.viewAll.setText(_text(service, "ViewBox", "View All"))
        for axis, ui in zip("XY", menu.ctrl, strict=True):
            bounds = (ui.minText.text(), ui.maxText.text())
            blockers = [QSignalBlocker(ui.minText), QSignalBlocker(ui.maxText)]
            try:
                ui.retranslateUi(ui.mouseCheck.parentWidget())
                ui.minText.setText(bounds[0])
                ui.maxText.setText(bounds[1])
            finally:
                del blockers
            child = _submenu_for_widget(menu, ui.mouseCheck.parentWidget())
            if child is not None:
                child.setTitle(f"{axis} {_text(service, 'ViewBox', 'axis')}")
        for action, source in zip(menu.mouseModes, ("3 button", "1 button"), strict=True):
            action.setText(_text(service, "ViewBox", source))
        for action in menu.actions():
            child = action.menu()
            if child is not None and all(mode in child.actions() for mode in menu.mouseModes):
                child.setTitle(_text(service, "ViewBox", "Mouse Mode"))
        for action in self.scene.contextMenu:
            action.setText(_text(service, "GraphicsScene", "Export..."))
        self.scene.exportDialog.retranslate()
