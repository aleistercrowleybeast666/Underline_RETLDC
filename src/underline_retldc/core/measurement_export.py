from __future__ import annotations

from collections.abc import Iterable

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.units import Quantity_Dimension


def Measurement_ChannelsSelect(
    dataset: Dataset,
    *,
    dimension: str,
    semantic_roles: Iterable[str] = (),
) -> tuple[Channel, ...]:
    """Select semantic measurement channels without consulting names or source headers."""
    roles = frozenset(str(role) for role in semantic_roles)
    candidates = tuple(
        channel
        for channel in dataset.channels.values()
        if Quantity_Dimension(channel.quantity) == dimension
        and channel.semantic_role != "auxiliary"
        and (not roles or channel.semantic_role in roles)
    )
    preferred = tuple(
        channel
        for channel in candidates
        if channel.role in {"calibrated", "processed"}
    )
    return preferred or candidates
