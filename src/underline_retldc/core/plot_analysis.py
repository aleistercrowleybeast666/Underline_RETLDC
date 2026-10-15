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
    """Select existing samples in scientific time before any display transform."""
    mask = np.ones(time.shape, dtype=bool)
    if fft and not np.all(np.isfinite(time)):
        # A missing clock value cannot safely be assigned to either side of a cut.
        return mask, "timestamps"
    if active_only:
        if interval is None or not all(np.isfinite(interval)) or interval[0] >= interval[1]:
            return np.zeros(time.shape, dtype=bool), "interval"
        mask = (time >= interval[0]) & (time <= interval[1])
        indices = np.flatnonzero(mask)
        if indices.size:
            span = slice(indices[0], indices[-1] + 1)
            mask[span] |= ~np.isfinite(time[span])  # Preserve internal display gaps.
    selected_time, selected_values = time[mask], values[mask]
    if selected_time.size < 2:
        return mask, "samples"
    steps = np.diff(selected_time)
    if np.any(steps <= 0):
        return mask, "timestamps"
    if fft and not np.all(np.isfinite(selected_values)):
        return mask, "gaps"
    return mask, ""


def PlotAnalysis_FFTNotice(time: NDArray[np.float64]) -> str:
    """Describe native FFT interpolation for already validated clocks; never block it."""
    steps = np.diff(time)
    # Match pyqtgraph 0.14's actual decision, including its first-interval reference.
    if not np.any(np.abs(steps - steps[0]) > abs(steps[0]) / 1000.0):
        return ""
    if float(np.max(steps)) > 2.0 * float(np.median(steps)):
        return "resampled_gaps"
    return "resampled"
