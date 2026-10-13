from __future__ import annotations

from threading import Event

from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_theory_overlay import window as window

from underline_retldc.gui.main_window import MainWindow
from underline_retldc.plugin_api.common import TaskContext


def test_close_waits_for_worker_without_delivering_gui_callback(window: MainWindow) -> None:
    started, release = Event(), Event()
    delivered: list[str] = []

    def operation(context: TaskContext) -> str:
        started.set()
        assert release.wait(5)
        return "late result"

    window.show()
    handle = window._task_start("closing probe", operation, delivered.append)
    assert started.wait(2)
    try:
        assert not window.close()  # Closing must defer while the worker still owns its data.
        assert window._task_start("late task", lambda _context: None, delivered.append) is None
        assert window.isVisible()
    finally:
        release.set()
        window.task_manager.shutdown(wait=True, cancel_pending=True)
    for _ in range(20):
        QApplication.processEvents()
        QTest.qWait(10)
        if not window.isVisible():
            break
    assert handle.done
    assert not window.isVisible()
    assert delivered == []
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_close_cancels_pending_auto_import(window: MainWindow) -> None:
    delivered: list[str] = []
    window._auto_preview_timer.timeout.connect(lambda: delivered.append("preview"))
    window._auto_parse_timer.timeout.connect(lambda: delivered.append("parse"))
    window._auto_preview_timer.start(0)
    window._auto_parse_timer.start(0)
    assert window.close()
    QApplication.processEvents()
    assert delivered == []
    assert window._active_task is None
