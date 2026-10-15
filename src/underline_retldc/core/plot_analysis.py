from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def PlotAnalysis_Select(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    *,
    active_only: bool,
    interval: tuple[float, float] | None,
    fft: bool,
) -> tuple[NDArray[np.bool_], str]:
    """Select existing samples in scientific time; never interpolate or bridge gaps."""
    mask = np.ones(time.shape, dtype=bool)
    if active_only:
        if interval is None or not all(np.isfinite(interval)) or interval[0] >= interval[1]:
            return np.zeros(time.shape, dtype=bool), "interval"
        mask = (time >= interval[0]) & (time <= interval[1])
    selected_time, selected_values = time[mask], values[mask]
    if selected_time.size < 2:
        return mask, "samples"
    if not np.all(np.isfinite(selected_time)):
        return mask, "timestamps"
    steps = np.diff(selected_time)
    if np.any(steps <= 0):
        return mask, "timestamps"
    if fft:
        if not np.all(np.isfinite(selected_values)):
            return mask, "gaps"
        # Same 0.1% uniformity boundary as pyqtgraph 0.14.0, but reject rather
        # than letting its _fourierTransform silently interpolate nonuniform data.
        if np.any(np.abs(steps - steps[0]) > abs(steps[0]) / 1000.0):
            return mask, "nonuniform"
    return mask, ""
