from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from pyqtgraph.graphicsItems.PlotDataItem import PlotDataset
from PySide6.QtCore import Signal

from underline_retldc.core.plot_analysis import PlotAnalysis_Select


class AnalysisPlotDataItem(pg.PlotDataItem):
    """Bounded adapter for pyqtgraph 0.14 mappings; original CSV arrays stay intact."""

    notice_changed = Signal()

    def __init__(
        self, time: NDArray[np.float64], values: NDArray[np.float64], *,
        scientific_time: NDArray[np.float64], interval: tuple[float, float] | None,
        active_only: bool, theoretical: bool, **kwargs: object,
    ) -> None:
        self.scientific_time = np.asarray(scientific_time)
        self.analysis_interval = interval
        self.active_only = active_only
        self.theoretical = theoretical
        self.analysis_notice = ""
        super().__init__(time, values, **kwargs)

    def set_analysis_scope(self, active_only: bool, interval: tuple[float, float] | None) -> None:
        self.active_only, self.analysis_interval = active_only, interval
        self._datasetMapped = self._datasetDisplay = None
        self.updateItems(styleUpdate=False)
        self.informViewBoundsChanged()

    def _notice_set(self, notice: str) -> None:
        if notice != self.analysis_notice:
            self.analysis_notice = notice
            self.notice_changed.emit()

    def _getDisplayDataset(self) -> PlotDataset | None:
        original = self._dataset
        derived = any(self.opts[key] for key in (
            "fftMode", "derivativeMode", "phasemapMode", "subtractMeanMode",
        ))
        if original is None or not (derived or self.active_only):
            self._notice_set("")
            return super()._getDisplayDataset()
        if self._datasetMapped is not None:
            return super()._getDisplayDataset()
        mask, notice = PlotAnalysis_Select(
            self.scientific_time, original.y, active_only=self.active_only,
            interval=self.analysis_interval, fft=self.opts["fftMode"],
        )
        self._notice_set(notice)
        if notice:
            return None
        # Only native display mapping sees this selected input. The original dataset
        # is restored even on errors; CSVExporter.getOriginalDataset stays full-record.
        time = self.scientific_time if self.opts["fftMode"] else original.x
        self._dataset = PlotDataset(time[mask], original.y[mask])
        try:
            return super()._getDisplayDataset()
        finally:
            self._dataset = original
