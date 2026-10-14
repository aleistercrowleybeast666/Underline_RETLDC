from __future__ import annotations

import pytest

from underline_retldc.core.motor_parameters import MotorPhysicalParameters
from underline_retldc.core.source_analysis import (
    SourceAnalysis_UseSharedMotor,
    SourceAnalysisConfig,
)


def test_shared_motor_overrides_mass_and_retains_legacy_trace() -> None:
    config = SourceAnalysisConfig("theory", "thrust_analysis", propellant_mass_kg=.25,
                                  interval=(10, 20), polarity=-1)
    shared = MotorPhysicalParameters(.1, .9, 40, 120)
    resolved = SourceAnalysis_UseSharedMotor(config, shared)
    assert resolved.propellant_mass_kg == .1 and resolved.mass_source == "project"
    assert resolved.legacy_physical_parameters == {"propellant_mass_kg": .25}
    assert resolved.interval == config.interval and resolved.polarity == config.polarity
    empty = SourceAnalysis_UseSharedMotor(resolved, MotorPhysicalParameters())
    assert empty.propellant_mass_kg is None
    assert empty.legacy_physical_parameters == resolved.legacy_physical_parameters
    assert SourceAnalysisConfig.from_dict(empty.to_dict()) == empty
    assert MotorPhysicalParameters.from_metadata({}).to_dict() == {
        "propellant_mass_kg": None, "total_motor_mass_kg": None,
        "diameter_mm": None, "length_mm": None,
    }


@pytest.mark.parametrize("value", [True, "invalid", float("nan"), float("inf")])
def test_invalid_motor_parameter_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        MotorPhysicalParameters(total_motor_mass_kg=value)


def test_legacy_dimensions_are_retained_as_trace_only() -> None:
    config = SourceAnalysisConfig.from_dict({
        "source_id": "theory", "workspace_id": "thrust_analysis",
        "total_motor_mass_kg": 9, "diameter_mm": 90, "length_mm": 900,
    })
    resolved = SourceAnalysis_UseSharedMotor(config, MotorPhysicalParameters(.1, 1, 30, 100))
    assert resolved.legacy_physical_parameters == {
        "total_motor_mass_kg": 9, "diameter_mm": 90, "length_mm": 900,
    }
