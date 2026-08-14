import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.pipeline import (
    Calibration_Apply,
    Calibration_OutputChannelId,
    Processing_Passthrough,
)
from underline_retldc.core.region_detection import Burn_DetectCandidates
from underline_retldc.core.units import G0_STANDARD_M_S2
from underline_retldc.plugin_api.common import TaskContext


def test_dynamic_primary_thrust_id_flows_through_processing_analysis_and_export(
    tmp_path,
    bundled_registry,
) -> None:
    time = np.linspace(0.0, 10.0, 101)
    thrust = np.where((time >= 3.0) & (time <= 7.0), 8.0, 0.0)
    raw = Channel(
        "load_cell_A",
        "force",
        "raw",
        thrust,
        "raw",
        semantic_role="thrust",
    )
    dataset = Dataset(time=time, channels={raw.id: raw})
    output_id = Calibration_OutputChannelId(raw)
    assert output_id == "load_cell_A_calibrated"
    assert output_id != "force_calibrated"
    calibrated = Calibration_Apply(
        dataset,
        bundled_registry.get("builtin.calibration.linear"),
        input_channel_id=raw.id,
        output_channel_id=output_id,
        quantity="force",
        unit="N",
        parameters={"K": 1.0, "B": 0.0},
    )
    processor = bundled_registry.get("builtin.processor.vertical_linear_baseline")
    processing = processor.process(
        calibrated,
        {
            "input_channel_id": output_id,
            "enabled": True,
            "sign": 1,
            "regions": {
                "pre": [0.0, 2.0],
                "burn": [3.0, 7.0],
                "post": [8.0, 10.0],
            },
        },
        TaskContext(),
    )
    assert processing.dataset.channel("thrust_processed").metadata[
        "source_channel_id"
    ] == "thrust_corrected"
    analyzer = bundled_registry.get("builtin.analyzer.thrust")
    analysis = analyzer.analyze(
        processing.dataset,
        {
            "channel_id": "thrust_processed",
            "ignition": 3.0,
            "burnout": 7.0,
            "propellant_mass_kg": None,
        },
        TaskContext(),
    )
    assert analysis.metrics["peak_thrust_n"] == 8.0
    destination = tmp_path / "thrust_data_EN.csv"
    bundled_registry.get("builtin.exporter.csv").export(
        destination,
        processing.dataset,
        analysis,
        {
            "channel_ids": ["thrust_processed"],
            "burn_only": True,
            "shift_time": True,
            "ignition": 3.0,
            "burnout": 7.0,
            "output_locale": "en_US",
        },
        TaskContext(),
    )
    assert destination.is_file()


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
    result = Processing_Passthrough(
        dataset,
        input_channel_id="force_calibrated",
    )
    assert "thrust_processed" not in dataset.channels
    np.testing.assert_allclose(
        result.dataset.channel("thrust_processed").values,
        dataset.channel("force_calibrated").values,
    )
    assert result.metadata["processor_id"] is None


def test_missing_pre_and_post_assume_zero_and_analysis_continues(
    bundled_registry,
) -> None:
    time = np.linspace(0.0, 4.0, 41)
    measured = np.where((time >= 1.0) & (time <= 3.0), 8.0, 0.0)
    dataset = Dataset(
        time,
        {
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
            "sign": 1,
            "regions": {"pre": None, "burn": [1.0, 3.0], "post": None},
        },
        TaskContext(),
    )
    assert result.metadata["baseline_start"] == 0.0
    assert result.metadata["baseline_end"] == 0.0
    assert result.metadata["baseline_pre_source"] == "assumed_zero"
    assert result.metadata["baseline_post_source"] == "assumed_zero"
    assert result.metadata["equivalent_mass_change_kg"] is None
    assert {
        "processing.pre_baseline_assumed_zero",
        "processing.post_baseline_assumed_zero",
        "processing.equivalent_mass_unavailable_assumed_baseline",
    } <= {item.code for item in result.diagnostics}
    np.testing.assert_allclose(
        result.dataset.channel("thrust_processed").values, measured
    )


def test_activity_detection_marks_clipped_boundaries() -> None:
    time = np.linspace(0.0, 10.0, 101)
    start_clipped_signal = np.where(time <= 3.0, 5.0, 0.0)
    start_candidates = Burn_DetectCandidates(time, start_clipped_signal)
    assert start_candidates and start_candidates[0].start_clipped
    assert not start_candidates[0].end_clipped

    end_clipped_signal = np.where(time >= 7.0, 5.0, 0.0)
    end_candidates = Burn_DetectCandidates(time, end_clipped_signal)
    assert end_candidates and end_candidates[0].end_clipped
    assert not end_candidates[0].start_clipped
