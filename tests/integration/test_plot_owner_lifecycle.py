from __future__ import annotations

from threading import get_ident

import pytest
import shiboken6
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication
from test_theory_overlay import window as window

from underline_retldc.gui.main_window import MainWindow
from underline_retldc.gui.source_analysis_widget import SourceAnalysisWidget
from underline_retldc.plugin_api.common import TaskContext


def test_failed_task_window_retires_plot_menus_with_native_owner(window: MainWindow) -> None:
    """A retained failure traceback must not retain live GUI menus after owner deletion."""
    plot = window.process_page.analysis_plot.plot_widget
    item = plot.getPlotItem()
    menus = (item.ctrlMenu, item.vb.menu)
    assert all(menu.isWindow() for menu in menus)
    assert all(menu.windowFlags() & Qt.WindowType.Popup for menu in menus)
    retired: list[int] = []
    gui_thread = get_ident()
    for menu in menus:
        menu.destroyed.connect(
            lambda _object=None: retired.append(get_ident()), Qt.ConnectionType.DirectConnection,
        )

    def operation(_context: TaskContext) -> None:
        raise RuntimeError(type(window).__name__)

    handle = window.task_manager.submit("retained window failure", operation)
    with pytest.raises(RuntimeError, match="MainWindow"):
        handle.wait(timeout=5)
    assert handle.exception is not None
    window.task_manager.shutdown(wait=True, cancel_pending=True)
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    # Keep the real handle, traceback, window and menu wrappers alive deliberately.
    # Native retirement must follow the GUI owner, not Python cycle collection.
    assert not shiboken6.isValid(window)
    assert all(not shiboken6.isValid(menu) for menu in menus)
    assert retired == [gui_thread, gui_thread]


def test_hidden_source_editors_retire_even_when_python_wrappers_survive(window: MainWindow) -> None:
    editors = window.findChildren(SourceAnalysisWidget)
    assert editors
    hidden_panels = [editor.parameter_scroll for editor in editors]
    assert all(not panel.isVisible() for panel in hidden_panels)
    window.task_manager.shutdown(wait=True, cancel_pending=True)
    window.close()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert all(not shiboken6.isValid(editor) for editor in editors)
    assert all(not shiboken6.isValid(panel) for panel in hidden_panels)

