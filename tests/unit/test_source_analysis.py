from dataclasses import replace

import numpy as np
import pytest

from underline_retldc.app.source_analysis import SourceAnalysis_Calculate
from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project import ProjectDocument, ProjectSourceState, ProjectStreamState
from underline_retldc.core.project_data import ChannelReference
from underline_retldc.core.source_analysis import (
    SourceAnalysisConfig,
    SourceAnalysisDocument,
    SourceAnalysisInput,
)
from underline_retldc.plugin_api.common import TaskContext


def _input(quantity="force", unit="kN", values=(0, 1, 2, 0), time=(8, 9, 11, 13),
           channel_id="f", source_id="theory") -> SourceAnalysisInput:
    dataset = Dataset(time, {channel_id: Channel(channel_id, quantity, unit, values, "raw")},
                      source_id=source_id, stream_id=f"{source_id}_stream", time_offset_s=2)
    reference = ChannelReference(source_id, dataset.stream_id, channel_id)
    return SourceAnalysisInput(reference, dataset, channel_id, channel_id)


def _thrust(item, bundled_registry, **parameters):
    config = SourceAnalysisConfig(item.reference.source_id, "thrust_analysis",
                                  (item.reference,), **parameters)
    return SourceAnalysis_Calculate(config, (item,), TaskContext(),
                                    analyzer=bundled_registry.get("builtin.analyzer.thrust"))


def test_source_thrust_actual_clock_units_mass_and_immutable_samples(bundled_registry):
    item = _input()
    state = _thrust(item, bundled_registry)
    result = state.results[item.reference.stable_id]
    assert result.metrics["total_impulse_ns"] == 5500
    assert result.metrics["time_to_peak_s"] == 3
    assert result.metrics["specific_impulse_s"] is None
    assert result.metadata["interval"] == [10, 15]
    assert not result.metadata["display_transform_applied"]
    assert "source_analysis.propellant_mass_missing" in {d.code for d in result.diagnostics}
    for mass in (0, -1, 0.25):
        calculated = _thrust(item, bundled_registry, propellant_mass_kg=mass)
        metrics = calculated.results[item.reference.stable_id].metrics
        assert metrics["total_impulse_ns"] == 5500
        expected = 5500 / (mass * 9.80665) if mass > 0 else None
        assert metrics["specific_impulse_s"] == expected
    negative = _thrust(item, bundled_registry, polarity=-1, interval=(11, 13))
    assert negative.results[item.reference.stable_id].metrics["total_impulse_ns"] == -3000
    np.testing.assert_array_equal(item.dataset.time, [8, 9, 11, 13])
    np.testing.assert_array_equal(item.dataset.channel("f").values, [0, 1, 2, 0])
    assert not item.dataset.time.flags.writeable
    assert not item.dataset.channel("f").values.flags.writeable


def test_source_compensation_uses_final_output_and_own_baseline(bundled_registry):
    item = _input(unit="N", values=(5, 5, 5, 1005, 2005, 1005, 5, 5, 5),
                  time=tuple(range(9)))
    processor = bundled_registry.get("builtin.processor.vertical_linear_baseline")
    config = SourceAnalysisConfig("theory", "thrust_analysis", (item.reference,),
                                  interval=(4, 8), pre=(2, 3), post=(9, 10),
                                  processor={"id": processor.descriptor.plugin_id,
                                             "version": "1.0.0", "api_version": "1",
                                             "config": {}})
    state = SourceAnalysis_Calculate(config, (item,), TaskContext(), processor=processor,
                                    analyzer=bundled_registry.get("builtin.analyzer.thrust"))
    result = state.results[item.reference.stable_id]
    assert result.metrics["total_impulse_ns"] == pytest.approx(4000)
    assert result.metrics["specific_impulse_s"] is None
    assert result.metadata["channel_id"] == "thrust_processed"
    assert set(item.dataset.channels) == {"f"}
    with pytest.raises(ValueError, match="unavailable"):
        SourceAnalysis_Calculate(config, (item,), TaskContext())


@pytest.mark.parametrize("workspace,quantity,unit,values,expected", [
    ("chamber_pressure", "pressure", "MPa", (0, 1, 2, 0), 2_000_000),
    ("temperature", "temperature", "°C", (20, 21, 22, 23), 296.15),
    ("data_explorer", "length", "mm", (0, 1, 2, 0), .002),
])
def test_source_statistics_reuse_existing_definitions(workspace, quantity, unit, values, expected):
    item = _input(quantity, unit, values)
    config = SourceAnalysisConfig("theory", workspace, (item.reference,), interval=(11, 15))
    state = SourceAnalysis_Calculate(config, (item,), TaskContext())
    result = state.results[item.reference.stable_id]
    assert result.metrics["active_maximum"] == pytest.approx(expected)
    if workspace == "temperature":
        assert result.metrics["full_maximum_time_s"] == 15
    if workspace == "chamber_pressure":
        assert result.metrics["active_time_to_maximum_s"] == 2
        assert result.metrics["active_mean"] == 1_250_000


def test_source_temperature_multiple_channels_and_source_reference_isolation():
    first = _input("temperature", "K", (293, 294, 295, 296), channel_id="t1")
    second = _input("temperature", "°C", (30, 31, 32, 33), channel_id="t2")
    config = SourceAnalysisConfig("theory", "temperature", (first.reference, second.reference))
    result = SourceAnalysis_Calculate(config, (first, second), TaskContext())
    assert len(result.results) == 2
    assert result.results[second.reference.stable_id].metrics["full_maximum"] == 306.15
    other = _input(source_id="experiment")
    with pytest.raises(ValueError, match="mix Channels"):
        SourceAnalysisConfig("theory", "temperature", (other.reference,))
    with pytest.raises(ValueError, match="Select"):
        SourceAnalysis_Calculate(config, (first,), TaskContext())


@pytest.mark.parametrize("values,time,unit,interval,message", [
    ((), (), "N", None, "No finite"),
    ((np.nan, np.nan), (0, 1), "N", None, "No finite"),
    ((1, 2), (0, 1), "ADC", None, "Quantity/Unit"),
    ((1, 2), (0, 1), "Pa", None, "Quantity/Unit"),
    ((1, 2, 3), (0, 0, 1), "N", None, "strictly increasing"),
    ((1, 2), (0, 1), "N", (4, 5), "no finite samples"),
    ((1, 2), (0, 1), "N", (1, 0), "start < end"),
])
def test_source_calculation_invalid_inputs(values, time, unit, interval, message, bundled_registry):
    item = _input(unit=unit, values=values, time=time)
    with pytest.raises(ValueError, match=message):
        _thrust(item, bundled_registry, interval=interval)


def test_source_nan_samples_keep_existing_finite_integration_and_diagnostic(bundled_registry):
    item = _input(unit="N", values=(0, 10, np.nan, 0), time=(0, 1, 2, 3))
    result = _thrust(item, bundled_registry).results[item.reference.stable_id]
    assert result.metrics["total_impulse_ns"] == 15
    assert "source_analysis.non_finite_samples" in {d.code for d in result.diagnostics}
    assert np.isnan(item.dataset.channel("f").values[2])


def test_source_project_documents_preserve_completed_draft_and_independent_calibration(
    bundled_registry,
):
    item = _input()
    completed = _thrust(item, bundled_registry, propellant_mass_kg=.2).document()
    draft = SourceAnalysisDocument(replace(completed.config, workspace_id="data_explorer"))
    document = ProjectDocument(
        sources=(ProjectSourceState("theory", "D:/theory.csv"),),
        streams=(ProjectStreamState("theory_stream", "theory"),),
        calibrated_stream_ids=("theory_stream",),
        source_analyses={completed.config.key: completed, draft.config.key: draft},
        workflow_state={"parsed": True, "calibrated": False, "processed": False,
                        "analyzed": False},
    )
    loaded = ProjectDocument.from_dict(document.to_dict())
    assert loaded == document
    assert not loaded.workflow_state["analyzed"]
    assert loaded.source_analyses[completed.config.key].completed
    assert not loaded.source_analyses[draft.config.key].completed
    legacy = document.to_dict()
    legacy.pop("source_analyses")
    legacy.pop("calibrated_stream_ids")
    assert ProjectDocument.from_dict(legacy).source_analyses == {}
    assert ProjectDocument.from_dict(legacy).calibrated_stream_ids is None
    for kwargs in ({"interval": (0, np.inf)}, {"propellant_mass_kg": np.nan}):
        with pytest.raises(ValueError, match="finite"):
            replace(completed.config, **kwargs)
