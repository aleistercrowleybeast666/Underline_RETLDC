from pathlib import Path

import pytest

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.primary_channels import (
    PrimaryChannels_AutoBind,
    PrimaryChannels_Candidates,
    PrimaryChannels_Validate,
)
from underline_retldc.core.project import ProjectDocument
from underline_retldc.core.project_data import (
    ChannelReference,
    PrimaryChannelBindings,
    ProjectData,
    Source,
    Stream,
)


def _project_data(channels: dict[str, Channel]) -> ProjectData:
    source = Source("source_1", Path("fixture.csv"))
    stream = Stream(
        "stream_1",
        source.id,
        Dataset(time=[0.0, 1.0], channels=channels),
    )
    return ProjectData({source.id: source}, {stream.id: stream})


def _channel(
    channel_id: str,
    quantity: str,
    semantic_role: str | None = None,
) -> Channel:
    unit = {"force": "N", "pressure": "Pa", "temperature": "K"}.get(
        quantity,
        "1",
    )
    return Channel(
        channel_id,
        quantity,
        unit,
        [1.0, 2.0],
        "raw",
        semantic_role=semantic_role,
    )


def test_primary_channels_use_roles_then_unique_quantity_without_guessing() -> None:
    unique = _project_data({"load_a": _channel("load_a", "force")})
    assert PrimaryChannels_AutoBind(unique).thrust == ChannelReference(
        "source_1",
        "stream_1",
        "load_a",
    )

    role_wins = _project_data(
        {
            "load_a": _channel("load_a", "force"),
            "load_b": _channel("load_b", "force", "thrust"),
        }
    )
    assert PrimaryChannels_AutoBind(role_wins).thrust.channel_id == "load_b"

    ambiguous = _project_data(
        {
            "load_a": _channel("load_a", "force"),
            "load_b": _channel("load_b", "force"),
        }
    )
    assert PrimaryChannels_AutoBind(ambiguous).thrust is None


def test_pressure_temperature_and_other_routing_are_binding_driven() -> None:
    project_data = _project_data(
        {
            "pc": _channel("pc", "pressure", "chamber_pressure"),
            "tc_1": _channel("tc_1", "temperature", "temperature"),
            "tc_2": _channel("tc_2", "temperature", "temperature"),
            "other_pressure": _channel("other_pressure", "pressure", "auxiliary"),
        }
    )
    bindings = PrimaryChannels_AutoBind(project_data)
    assert bindings.chamber_pressure is not None
    assert bindings.chamber_pressure.channel_id == "pc"
    assert {item.channel_id for item in bindings.temperature_channels} == {
        "tc_1",
        "tc_2",
    }
    assert {
        item.channel_id
        for item in PrimaryChannels_Candidates(project_data, dimension="pressure")
    } == {"pc"}
    with pytest.raises(ValueError, match="chamber-pressure"):
        PrimaryChannels_Validate(
            project_data,
            PrimaryChannelBindings(
                chamber_pressure=ChannelReference(
                    "source_1",
                    "stream_1",
                    "other_pressure",
                )
            ),
        )


def test_manual_primary_bindings_survive_project_round_trip() -> None:
    bindings = PrimaryChannelBindings(
        thrust=ChannelReference("source_a", "stream_a", "load_cell_A"),
        chamber_pressure=ChannelReference("source_a", "stream_a", "pc_A"),
        temperature_channels=(
            ChannelReference("source_b", "stream_b", "tc_1"),
            ChannelReference("source_b", "stream_b", "tc_2"),
        ),
    )
    restored = ProjectDocument.from_dict(
        ProjectDocument(primary_channels=bindings).to_dict()
    )
    assert restored.primary_channels == bindings
    assert restored.primary_channels_explicit
