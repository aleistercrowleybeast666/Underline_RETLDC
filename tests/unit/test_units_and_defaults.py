from pathlib import Path

import numpy as np
import pytest

from underline_retldc.core.calibration import (
    Calibration_DefaultSelections,
    Calibration_SelectionResolve,
    CalibrationDocument,
    CalibrationSelection,
    CalibrationSelectionSource,
)
from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.pipeline import Calibration_Apply
from underline_retldc.core.primary_channels import PrimaryChannels_AutoBind
from underline_retldc.core.project import (
    ChannelProjectState,
    PluginReference,
    Project_Load,
    Project_Save,
    ProjectDocument,
)
from underline_retldc.core.project_data import ProjectData, Source, Stream
from underline_retldc.core.region_detection import detect_activity_segments
from underline_retldc.core.segmentation import (
    Segmentation_SelectReference,
    Segmentation_SelectReferenceForRole,
)
from underline_retldc.core.units import (
    Unit_ValueFormat,
    UnitDisplayMode,
    UnitSource,
)
from underline_retldc.plugin_api.common import TaskContext


@pytest.mark.parametrize(
    ("quantity", "expected_unit"),
    [
        ("force", "N"),
        ("pressure", "Pa"),
        ("temperature", "K"),
        ("mass", "kg"),
        ("length", "m"),
        ("area", "m²"),
        ("volume", "m³"),
        ("kn", "1"),
    ],
)
def test_known_quantity_without_unit_uses_canonical_si(
    quantity: str, expected_unit: str
) -> None:
    channel = Channel("value", quantity, None, [1.0], "raw")
    assert channel.data_unit == expected_unit
    assert channel.unit_source is UnitSource.DEFAULT_SI


def test_explicit_parser_unit_wins_and_unknown_missing_unit_is_diagnosed() -> None:
    pressure = Channel("pc", "pressure", "MPa", [1.25], "raw")
    assert pressure.data_unit == "MPa"
    assert pressure.unit_source is UnitSource.PLUGIN_DECLARED

    custom = Channel("custom", "custom.vendor_signal", None, [3.0], "raw")
    dataset = Dataset([0.0], {custom.id: custom})
    assert custom.data_unit == "unknown_si"
    assert custom.unit_source is UnitSource.UNKNOWN
    assert {item.code for item in dataset.diagnostics} == {
        "unit.unknown_quantity_missing_unit"
    }


def test_data_unit_reinterpretation_and_display_conversion_are_independent() -> None:
    channel = Channel("pc", "pressure", "Pa", [1_000_000.0], "raw")
    displayed = channel.with_unit_interpretation(display_unit="MPa")
    np.testing.assert_array_equal(displayed.values, [1_000_000.0])
    np.testing.assert_allclose(displayed.display_values(), [1.0])
    assert displayed.data_unit == "Pa"

    reinterpreted = channel.with_unit_interpretation(data_unit="MPa")
    np.testing.assert_array_equal(reinterpreted.values, [1_000_000.0])
    assert reinterpreted.data_unit == "MPa"
    assert reinterpreted.unit_source is UnitSource.USER_OVERRIDE


def test_temperature_conversion_is_affine_and_does_not_change_raw_values() -> None:
    channel = Channel(
        "temperature",
        "temperature",
        "K",
        [273.15, 373.15],
        "raw",
        display_unit="°C",
    )
    np.testing.assert_allclose(channel.display_values(), [0.0, 100.0], atol=1.0e-12)
    np.testing.assert_array_equal(channel.values, [273.15, 373.15])


def test_si_scientific_display_uses_canonical_units_without_mutating_data() -> None:
    pressure = Channel("pc", "pressure", "MPa", [1.25], "raw")
    assert pressure.effective_display_unit({"pressure": "bar"}) == "bar"
    assert pressure.effective_display_unit(
        {"pressure": "bar"},
        display_mode=UnitDisplayMode.SI_SCIENTIFIC,
    ) == "Pa"
    np.testing.assert_allclose(
        pressure.display_values(display_mode=UnitDisplayMode.SI_SCIENTIFIC),
        [1.25e6],
    )
    np.testing.assert_array_equal(pressure.values, [1.25])

    temperature = Channel("tc", "temperature", "°C", [100.0], "raw")
    assert temperature.effective_display_unit(
        display_mode=UnitDisplayMode.SI_SCIENTIFIC
    ) == "K"
    np.testing.assert_allclose(
        temperature.display_values(display_mode=UnitDisplayMode.SI_SCIENTIFIC),
        [373.15],
    )
    assert Unit_ValueFormat(
        1_250_000.0,
        display_mode=UnitDisplayMode.SI_SCIENTIFIC,
    ) == "1.2500000e+06"


def test_every_new_channel_defaults_to_identity_independent_of_unit() -> None:
    selections = Calibration_DefaultSelections(("n", "mpa", "missing", "raw"))
    assert set(selections) == {"n", "mpa", "missing", "raw"}
    assert {
        selection.plugin_id for selection in selections.values()
    } == {"builtin.calibration.identity"}
    assert {
        selection.source for selection in selections.values()
    } == {CalibrationSelectionSource.FACTORY_DEFAULT}


def test_calibration_priority_is_project_then_profile_then_identity() -> None:
    profile = CalibrationDocument(
        name="LC-01",
        quantity="force",
        input_unit="raw",
        output_unit="N",
        model_id="builtin.calibration.linear",
        model_version="1.0.0",
        parameters={"K": 2.0, "B": 1.0},
        sensor={"sensor_id": "LC-01"},
    )
    matched = Calibration_SelectionResolve(matched_profile=profile)
    assert matched.source is CalibrationSelectionSource.USER_PROFILE
    assert matched.profile_name == "LC-01"

    project = CalibrationSelection(
        plugin_id="builtin.calibration.identity",
        source=CalibrationSelectionSource.PROJECT,
    )
    assert Calibration_SelectionResolve(project=project, matched_profile=profile) is project
    assert Calibration_SelectionResolve().plugin_id == "builtin.calibration.identity"


def test_linear_calibration_changes_output_unit_without_touching_raw(
    bundled_registry,
) -> None:
    raw = Channel("thrust_raw", "force", "raw", [0.0, 2.0, 4.0], "raw")
    dataset = Dataset([0.0, 1.0, 2.0], {raw.id: raw})
    calibrated = Calibration_Apply(
        dataset,
        bundled_registry.get("builtin.calibration.linear"),
        input_channel_id="thrust_raw",
        output_channel_id="force_calibrated",
        quantity="force",
        unit="N",
        parameters={"K": 3.0, "B": 1.0},
    )
    assert calibrated.channel("thrust_raw").data_unit == "raw"
    np.testing.assert_array_equal(calibrated.channel("thrust_raw").values, raw.values)
    output = calibrated.channel("force_calibrated")
    assert output.data_unit == "N"
    assert output.unit_source is UnitSource.CALIBRATION_OUTPUT
    np.testing.assert_allclose(output.values, [1.0, 7.0, 13.0])


def test_raw_force_can_be_segmented_but_has_no_fake_physical_metrics(
    bundled_registry,
) -> None:
    time = np.linspace(0.0, 4.0, 401)
    values = np.where((time >= 1.0) & (time <= 3.0), 10.0, 0.0)
    candidates = detect_activity_segments(time, values)
    assert candidates

    dataset = Dataset(
        time,
        {
            "thrust_processed": Channel(
                "thrust_processed", "force", "raw", values, "processed"
            )
        },
    )
    result = bundled_registry.get("builtin.analyzer.thrust").analyze(
        dataset,
        {
            "channel_id": "thrust_processed",
            "ignition": 1.0,
            "burnout": 3.0,
            "propellant_mass_kg": 1.0,
        },
        TaskContext(),
    )
    assert result.metrics["peak_value"] == 10.0
    assert result.metrics["peak_thrust_n"] is None
    assert result.metrics["total_impulse_ns"] is None
    assert result.metrics["specific_impulse_s"] is None
    assert {item.code for item in result.diagnostics} == {
        "analysis.force_unit_not_physical"
    }


def test_segmentation_prefers_semantic_chamber_pressure_even_when_raw() -> None:
    time = np.linspace(0.0, 4.0, 41)
    active = np.where((time >= 1.0) & (time <= 3.0), 5.0, 0.0)
    dataset = Dataset(
        time,
        {
            "other_pressure": Channel(
                "other_pressure", "pressure", "MPa", active, "raw"
            ),
            "pc": Channel(
                "pc",
                "pressure",
                "raw",
                active,
                "raw",
                semantic_role="chamber_pressure",
            ),
            "force": Channel(
                "force", "force", "N", active, "raw", semantic_role="thrust"
            ),
        },
    )
    project = ProjectData(
        {"source": Source("source", Path("source.txt"))},
        {"stream": Stream("stream", "source", dataset)},
    )
    project = project.with_primary_channels(PrimaryChannels_AutoBind(project))
    selected = Segmentation_SelectReference(project)
    assert selected is not None
    assert selected.reference.channel_id == "pc"
    assert selected.priority == "chamber_pressure"
    assert not selected.physical_unit
    pressure = Segmentation_SelectReferenceForRole(project, "chamber_pressure")
    thrust = Segmentation_SelectReferenceForRole(project, "thrust")
    assert pressure is not None and pressure.reference.channel_id == "pc"
    assert thrust is not None and thrust.reference.channel_id == "force"
    with pytest.raises(ValueError, match="Unsupported segmentation reference role"):
        Segmentation_SelectReferenceForRole(project, "temperature")


def test_project_time_offset_does_not_resample_local_data() -> None:
    dataset = Dataset(
        [0.0, 0.3, 0.9],
        {"value": Channel("value", "force", "N", [1.0, 2.0, 3.0], "raw")},
    )
    stream = Stream("stream", "source", dataset, time_offset_s=12.5)
    np.testing.assert_allclose(stream.dataset.project_time, [12.5, 12.8, 13.4])
    np.testing.assert_array_equal(stream.dataset.time, [0.0, 0.3, 0.9])


def test_project_round_trip_preserves_unit_override_and_calibration(tmp_path: Path) -> None:
    calibration = PluginReference(
        "builtin.calibration.identity",
        "1.0.0",
        "1",
        {"input_channel_id": "force", "data_unit": "kN"},
    )
    document = ProjectDocument(
        channels={
            "force": ChannelProjectState(
                "force",
                "force",
                "kN",
                "user_override",
                "N",
                "thrust",
                calibration,
                "force_calibrated",
            )
        }
    )
    destination = tmp_path / "units.retldc.json"
    Project_Save(document, destination)
    loaded = Project_Load(destination)
    assert loaded.channels["force"].data_unit == "kN"
    assert loaded.channels["force"].unit_source == "user_override"
    assert loaded.channels["force"].display_unit == "N"
    assert loaded.channels["force"].calibration == calibration
