from __future__ import annotations

import numpy as np
import pytest

from underline_retldc.core.measurement_statistics import MeasurementStatistics_Calculate


def test_pressure_mean_uses_actual_time_and_preserves_peak() -> None:
    time = np.array([0.0, 1.0, 4.0])
    pressure = np.array([0.0, 12.0, 0.0])
    result = MeasurementStatistics_Calculate(time, pressure, (0.0, 4.0))
    assert result.active_mean == pytest.approx(6.0)
    assert result.full_mean == pytest.approx(6.0)
    assert result.active_maximum == 12.0
    np.testing.assert_array_equal(pressure, [0.0, 12.0, 0.0])


def test_interval_mean_uses_selected_duration_without_endpoint_interpolation() -> None:
    result = MeasurementStatistics_Calculate(
        [0.0, 1.0, 2.0, 4.0], [0.0, 10.0, 10.0, 0.0], (0.5, 3.0)
    )
    assert result.active_mean == pytest.approx(4.0)
    assert result.active_maximum == 10.0


def test_mean_is_unavailable_without_two_ordered_samples() -> None:
    single = MeasurementStatistics_Calculate([0.0], [3.0], (0.0, 1.0))
    assert single.active_mean is None
    assert single.full_mean is None
    invalid = MeasurementStatistics_Calculate([0.0, 2.0, 1.0], [3.0] * 3, (0.0, 2.0))
    assert invalid.active_mean is None
