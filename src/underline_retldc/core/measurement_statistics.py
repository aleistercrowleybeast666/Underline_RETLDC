from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True, slots=True)
class MeasurementStatistics:
    test_start_value: float | None
    active_minimum: float | None
    active_mean: float | None
    active_maximum: float | None
    active_time_to_maximum_s: float | None
    full_minimum: float | None
    full_mean: float | None
    full_maximum: float | None
    full_maximum_time_s: float | None


def MeasurementStatistics_Calculate(
    project_time: ArrayLike,
    values: ArrayLike,
    active_interval: tuple[float, float] | None,
) -> MeasurementStatistics:
    time = np.asarray(project_time, dtype=np.float64)
    signal = np.asarray(values, dtype=np.float64)
    if time.ndim != 1 or signal.ndim != 1 or time.shape != signal.shape:
        raise ValueError("Measurement statistics require aligned one-dimensional arrays")
    finite = np.isfinite(time) & np.isfinite(signal)
    finite_time = time[finite]
    finite_signal = signal[finite]
    if finite_signal.size:
        full_max_index = int(np.argmax(finite_signal))
        full_minimum = float(np.min(finite_signal))
        full_mean = Measurement_TimeAverage(finite_time, finite_signal)
        full_maximum = float(finite_signal[full_max_index])
        full_maximum_time = float(finite_time[full_max_index])
    else:
        full_minimum = None
        full_mean = None
        full_maximum = None
        full_maximum_time = None

    test_start_value: float | None = None
    active_minimum: float | None = None
    active_mean: float | None = None
    active_maximum: float | None = None
    active_time_to_maximum: float | None = None
    if active_interval is not None:
        start, end = map(float, active_interval)
        if not np.isfinite(start) or not np.isfinite(end) or start >= end:
            raise ValueError("Active measurement interval must have finite start < end")
        if finite_signal.size:
            nearest = int(np.argmin(np.abs(finite_time - start)))
            test_start_value = float(finite_signal[nearest])
        active_mask = finite & (time >= start) & (time <= end)
        active_time = time[active_mask]
        active_signal = signal[active_mask]
        if active_signal.size:
            active_max_index = int(np.argmax(active_signal))
            active_minimum = float(np.min(active_signal))
            active_mean = Measurement_TimeAverage(active_time, active_signal, duration=end - start)
            active_maximum = float(active_signal[active_max_index])
            active_time_to_maximum = float(active_time[active_max_index] - start)

    return MeasurementStatistics(
        test_start_value=test_start_value,
        active_minimum=active_minimum,
        active_mean=active_mean,
        active_maximum=active_maximum,
        active_time_to_maximum_s=active_time_to_maximum,
        full_minimum=full_minimum,
        full_mean=full_mean,
        full_maximum=full_maximum,
        full_maximum_time_s=full_maximum_time,
    )


def Measurement_TimeAverage(
    time: np.ndarray,
    values: np.ndarray,
    *,
    duration: float | None = None,
) -> float | None:
    """Integrate retained samples without sorting or inventing interval endpoints."""
    if time.size < 2 or np.any(np.diff(time) <= 0):
        return None
    span = float(time[-1] - time[0]) if duration is None else float(duration)
    if not np.isfinite(span) or span <= 0:
        return None
    return float(np.trapezoid(values, time) / span)
