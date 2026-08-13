import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.units import G0_STANDARD_M_S2
from underline_retldc.plugin_api.common import TaskContext


def _dataset() -> Dataset:
    return Dataset(
        time=np.array([0.0, 1.0, 2.0]),
        channels={
            "thrust_processed": Channel(
                "thrust_processed", "thrust", "N", [0.0, 10.0, 0.0], "processed"
            )
        },
    )


def test_thrust_metrics_use_trapezoidal_actual_time(bundled_registry) -> None:
    result = bundled_registry.get("builtin.analyzer.thrust").analyze(
        _dataset(),
        {"channel_id": "thrust_processed", "ignition": 0.0, "burnout": 2.0},
        TaskContext(),
    )
    assert result.metrics["peak_thrust_n"] == 10.0
    assert result.metrics["average_thrust_n"] == 5.0
    assert result.metrics["burn_duration_s"] == 2.0
    assert result.metrics["total_impulse_ns"] == 10.0
    assert result.metrics["time_to_peak_s"] == 1.0
    assert result.metrics["specific_impulse_s"] is None


def test_specific_impulse_uses_propellant_mass(bundled_registry) -> None:
    result = bundled_registry.get("builtin.analyzer.thrust").analyze(
        _dataset(),
        {
            "channel_id": "thrust_processed",
            "ignition": 0.0,
            "burnout": 2.0,
            "propellant_mass_kg": 2.0,
        },
        TaskContext(),
    )
    assert np.isclose(result.metrics["specific_impulse_s"], 10.0 / (2.0 * G0_STANDARD_M_S2))
