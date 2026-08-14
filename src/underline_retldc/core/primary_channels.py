from __future__ import annotations

from collections.abc import Iterable

from underline_retldc.core.project_data import (
    ChannelReference,
    PrimaryChannelBindings,
    ProjectData,
)
from underline_retldc.core.units import Quantity_Dimension


def PrimaryChannels_Candidates(
    project_data: ProjectData,
    *,
    dimension: str,
) -> tuple[ChannelReference, ...]:
    return tuple(
        reference
        for reference in project_data.channel_references()
        if project_data.channel(reference).role == "raw"
        and project_data.channel(reference).semantic_role != "auxiliary"
        and Quantity_Dimension(project_data.channel(reference).quantity) == dimension
    )


def _single_recommendation(
    project_data: ProjectData,
    candidates: Iterable[ChannelReference],
    *,
    semantic_role: str,
) -> ChannelReference | None:
    available = tuple(candidates)
    role_matches = tuple(
        reference
        for reference in available
        if project_data.channel(reference).semantic_role == semantic_role
    )
    if len(role_matches) == 1:
        return role_matches[0]
    if len(role_matches) > 1:
        return None
    return available[0] if len(available) == 1 else None


def PrimaryChannels_AutoBind(project_data: ProjectData) -> PrimaryChannelBindings:
    thrust = _single_recommendation(
        project_data,
        PrimaryChannels_Candidates(project_data, dimension="force"),
        semantic_role="thrust",
    )
    pressure = _single_recommendation(
        project_data,
        PrimaryChannels_Candidates(project_data, dimension="pressure"),
        semantic_role="chamber_pressure",
    )
    temperatures = PrimaryChannels_Candidates(project_data, dimension="temperature")
    return PrimaryChannelBindings(
        thrust=thrust,
        chamber_pressure=pressure,
        temperature_channels=temperatures,
    )


def PrimaryChannels_ReferenceIsValid(
    project_data: ProjectData,
    reference: ChannelReference,
    *,
    dimension: str,
) -> bool:
    try:
        channel = project_data.channel(reference)
    except KeyError:
        return False
    return (
        channel.role == "raw"
        and channel.semantic_role != "auxiliary"
        and Quantity_Dimension(channel.quantity) == dimension
    )


def PrimaryChannels_Validate(
    project_data: ProjectData,
    bindings: PrimaryChannelBindings,
) -> None:
    if bindings.thrust is not None and not PrimaryChannels_ReferenceIsValid(
        project_data, bindings.thrust, dimension="force"
    ):
        raise ValueError("Primary thrust reference is missing or is not a force Channel")
    if (
        bindings.chamber_pressure is not None
        and not PrimaryChannels_ReferenceIsValid(
            project_data, bindings.chamber_pressure, dimension="pressure"
        )
    ):
        raise ValueError(
            "Primary chamber-pressure reference is missing or is not a pressure Channel"
        )
    for reference in bindings.temperature_channels:
        if not PrimaryChannels_ReferenceIsValid(
            project_data, reference, dimension="temperature"
        ):
            raise ValueError(
                "Selected temperature reference is missing or is not a temperature Channel"
            )
