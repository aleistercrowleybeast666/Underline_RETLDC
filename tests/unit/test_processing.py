import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.pipeline import Processing_Passthrough
from underline_retldc.core.region_detection import Burn_DetectCandidates
from underline_retldc.core.units import G0_STANDARD_M_S2
from underline_retldc.plugin_api.common import TaskContext


def test_vertical_compensation_recovers_known_thrust_and_preserves_input(
    bundled_registry,
) -> None:
    time = np.linspace(0.0, 10.0, 1001)
    ignition = 3.0
    burnout = 7.0
    pre_baseline = 10.0 + 0.2 * time
    post_baseline = 8.0 + 0.1 * time
    baseline_start = 10.0 + 0.2 * ignition
    baseline_end = 8.0 + 0.1 * burnout
    burn_baseline = baseline_start + (baseline_end - baseline_start) * (
        (time - ignition) / (burnout - ignition)
    )
    baseline = np.where(
        time < ignition,
        pre_baseline,
        np.where(time > burnout, post_baseline, burn_baseline),
    )
    thrust = np.where(
        (time >= ignition) & (time <= burnout),
        20.0 * np.sin(np.pi * (time - ignition) / (burnout - ignition)),
        0.0,
    )
    measured = baseline + thrust
    dataset = Dataset(
        time=time,
        channels={
            "force_calibrated": Channel(
                id="force_calibrated",
                quantity="force",
                unit="N",
                values=measured,
                role="calibrated",
            )
        },
    )
    before = dataset.channel("force_calibrated").values.copy()
    result = bundled_registry.get(
        "builtin.processor.vertical_linear_baseline"
    ).process(
        dataset,
        {
            "enabled": True,
            "input_channel_id": "force_calibrated",
            "sign": 1,
            "regions": {
                "pre": [0.0, 2.5],
                "burn": [ignition, burnout],
                "post": [7.5, 10.0],
            },
            # Legacy project values are ignored; this estimate is not a pass/fail gate.
            "expected_propellant_mass_kg": 999.0,
        },
        TaskContext(),
    )

    np.testing.assert_allclose(dataset.channel("force_calibrated").values, before)
    np.testing.assert_allclose(
        result.dataset.channel("thrust_corrected").values, thrust, atol=1e-10
    )
    expected_mass_change = abs(baseline_start - baseline_end) / G0_STANDARD_M_S2
    assert np.isclose(result.metadata["equivalent_mass_change_kg"], expected_mass_change)
    assert result.metadata["equivalent_mass_change_usage"] == "manual_reference_only"
    assert result.diagnostics == ()


def test_vertical_compensation_sign_is_explicit(bundled_registry) -> None:
    time = np.linspace(0.0, 6.0, 61)
    positive_thrust = np.where((time >= 2.0) & (time <= 4.0), 5.0, 0.0)
    measured = 10.0 - positive_thrust
    dataset = Dataset(
        time=time,
        channels={
            "force_calibrated": Channel(
                "force_calibrated", "force", "N", measured, "calibrated"
            )
        },
    )
    result = bundled_registry.get(
        "builtin.processor.vertical_linear_baseline"
    ).process(
        dataset,
        {
            "input_channel_id": "force_calibrated",
            "sign": -1,
            "regions": {"pre": [0.0, 1.5], "burn": [2.0, 4.0], "post": [4.5, 6.0]},
        },
        TaskContext(),
    )
    np.testing.assert_allclose(
        result.dataset.channel("thrust_corrected").values, positive_thrust, atol=1e-10
    )


def test_burn_detection_returns_multiple_ranked_candidates() -> None:
    time = np.linspace(0.0, 20.0, 2001)
    force = np.zeros_like(time)
    force[(time >= 2.0) & (time <= 2.5)] = 3.0
    force[(time >= 10.0) & (time <= 13.0)] = 12.0
    candidates = Burn_DetectCandidates(time, force)
    assert len(candidates) >= 2
    assert 9.9 <= candidates[0].start <= 10.1
    assert 12.9 <= candidates[0].end <= 13.1
    assert candidates[0].score > candidates[1].score


def test_processing_passthrough_creates_new_processed_channel() -> None:
    dataset = Dataset(
        time=[0.0, 1.0, 2.0],
        channels={
            "force_calibrated": Channel(
                "force_calibrated", "force", "N", [1.0, 2.0, 3.0], "calibrated"
            )
        },
    )
    result = Processing_Passthrough(dataset)
    assert "thrust_processed" not in dataset.channels
    np.testing.assert_allclose(
        result.dataset.channel("thrust_processed").values,
        dataset.channel("force_calibrated").values,
    )
    assert result.metadata["processor_id"] is None
