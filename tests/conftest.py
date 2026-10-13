import gc
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from underline_retldc.core.registry import PluginLoadResult, PluginRegistry
from underline_retldc.plugins.loader import PluginDiscoveryRoot, PluginLoader

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def bundled_registry() -> PluginRegistry:
    root = Path(__file__).resolve().parents[1] / "plugins"
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (PluginDiscoveryRoot(root, "bundled"),)
    )
    assert records
    assert all(record.result is PluginLoadResult.LOADED for record in records)
    return registry


@pytest.fixture(autouse=True)
def _gui_windows_release() -> Iterator[None]:
    """Dispose test-owned windows so global theme changes do not revisit old pages."""
    # Previous fixture frames can keep Python signal cycles alive beyond Qt deletion.
    # Reclaim them here, on the main thread and before any next-test worker starts.
    gc.collect()
    yield
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from underline_retldc.gui.main_window import MainWindow

    application = QApplication.instance()
    if application is not None:
        for widget in application.topLevelWidgets():
            if isinstance(widget, MainWindow):
                # A failed/time-limited test can leave a live worker. Finish cancellation
                # before deleting its owner or constructing the next window.
                widget.task_manager.shutdown(wait=True, cancel_pending=True)
                widget.close()
                widget.deleteLater()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        application.processEvents()
    gc.collect()
