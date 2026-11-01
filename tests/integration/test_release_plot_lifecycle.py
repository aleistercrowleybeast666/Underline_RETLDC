from __future__ import annotations

import gc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from typing import Any

import pytest
import shiboken6
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication
from test_theory_overlay import window as window

from underline_retldc.app import release_smoke
from underline_retldc.gui.main_window import MainWindow


def test_release_plot_export_parameters_retire_on_gui_thread(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise actual PNG/CSV/SVG paths before the next parse worker's collection."""
    gui_thread = get_ident()
    retired: list[tuple[str, int]] = []
    created: list[str] = []
    exporter_type = release_smoke.ImageExporter

    def observed_exporter(item: Any) -> ImageExporter:
        exporter = exporter_type(item)
        for parameter in [exporter.parameters(), *exporter.parameters().children()]:
            name = f"{len(created)}:{parameter.name()}"
            created.append(name)
            parameter.destroyed.connect(
                lambda _obj=None, label=name: retired.append((label, get_ident())),
                Qt.ConnectionType.DirectConnection,
            )
        return exporter

    monkeypatch.setattr(release_smoke, "ImageExporter", observed_exporter)
    diagnostics = SimpleNamespace(
        phase_stream=SimpleNamespace(name=str(tmp_path / "phases.jsonl")),
        phase=lambda *_args, **_kwargs: None,
    )
    release_smoke.ReleaseSmoke_BoundedPlotCheck(window, diagnostics)
    # Normal event-loop return must retire resources before unrelated computation.
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(gc.collect).result(timeout=10)
    assert len(created) == 12  # Two real ImageExporters, each root + five child parameters.
    assert sorted(label for label, _thread in retired) == sorted(created)
    assert {thread for _label, thread in retired} == {gui_thread}


def test_temporary_export_retires_on_failure_and_rejects_worker(window: MainWindow) -> None:
    item = window.process_page.analysis_plot.plot_widget.getPlotItem()
    with (
        pytest.raises(RuntimeError, match="export failure"),
        release_smoke._temporary_image_exporter(item) as exporter,
    ):
        parameters = exporter.parameters()
        children = parameters.children()
        raise RuntimeError("export failure")
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(parameters)
    assert all(not shiboken6.isValid(child) for child in children)

    def attempt_from_worker() -> None:
        # Rejection must happen before dereferencing an item or constructing Qt resources.
        with release_smoke._temporary_image_exporter(None):
            pytest.fail("worker export was accepted")

    with (
        ThreadPoolExecutor(max_workers=1) as executor,
        pytest.raises(RuntimeError, match="GUI thread"),
    ):
        executor.submit(attempt_from_worker).result(timeout=10)
