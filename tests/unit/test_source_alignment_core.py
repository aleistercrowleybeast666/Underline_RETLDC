from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project_data import ChannelReference, SourceDisplayTransform
from underline_retldc.core.source_alignment import SourceAlignment_Detect, SourceAlignment_Offset
from underline_retldc.core.source_analysis import SourceAnalysisInput


def _input(quantity: str, unit: str, values: list[float]) -> SourceAnalysisInput:
    dataset = Dataset([8, 9, 10, 11, 12], {
        "signal": Channel("signal", quantity, unit, values, "raw"),
    }, source_id="theory", stream_id="stream", time_offset_s=2.0)
    return SourceAnalysisInput(ChannelReference("theory", "stream", "signal"),
                               dataset, "signal", "signal")


def test_detection_uses_scientific_clock_own_polarity_and_roundtrips() -> None:
    pressure = _input("pressure", "MPa", [0, 1, 2, 1, 0])
    original = pressure.dataset.time.copy()
    detected = SourceAlignment_Detect((pressure,), polarity=-1)
    assert detected and detected.role == "chamber_pressure" and detected.polarity == 1
    assert detected.regions.burn.to_list() == [11.0, 13.0]
    assert SourceAlignment_Offset(1.4, detected) == pytest.approx(-9.6)
    transform = SourceDisplayTransform(shift_s=-9.6, detected_test=detected)
    assert SourceDisplayTransform.from_dict(transform.to_dict()) == transform
    np.testing.assert_array_equal(pressure.dataset.time, original)
    thrust = _input("force", "N", [0, -1, -2, -1, 0])
    detected = SourceAlignment_Detect((thrust,), role="thrust", polarity=-1)
    assert detected and detected.polarity == -1 and detected.regions.burn.start == 11.0


@pytest.mark.parametrize("values", [[0, 0, 0, 0, 0], [np.nan] * 5, [0, np.nan, 1, np.nan, 0]])
def test_unusable_theory_returns_no_interval(values: list[float]) -> None:
    item = _input("force", "N", values)
    assert SourceAlignment_Detect((item,)) is None


@pytest.mark.parametrize("unit", ["raw", "count", "ADC", "MPa"])
def test_nonphysical_or_conflicting_force_units_cannot_supply_alignment(unit: str) -> None:
    assert SourceAlignment_Detect((_input("force", unit, [0, 1, 2, 1, 0]),)) is None


def test_ambiguous_channels_require_explicit_reference_and_bad_cache_is_rejected() -> None:
    item = _input("force", "N", [0, 1, 2, 1, 0])
    other = replace(item, reference=ChannelReference("theory", "other-stream", "signal"))
    assert SourceAlignment_Detect((item, other)) is None
    detected = SourceAlignment_Detect((item, other), preferred=other.reference)
    assert detected and detected.reference == other.reference
    payload = SourceDisplayTransform(detected_test=detected).to_dict()
    payload["detected_test"]["regions"]["burn"] = [float("nan"), 13.0]
    with pytest.raises(ValueError, match="finite"):
        SourceDisplayTransform.from_dict(payload)
