from __future__ import annotations

from dataclasses import dataclass

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project_data import ChannelReference
from underline_retldc.core.units import (
    Quantity_Dimension,
    Unit_AreConvertible,
    Unit_IsPhysicalForQuantity,
)


@dataclass(frozen=True, slots=True)
class DisplayCurve:
    reference: ChannelReference
    dataset: Dataset
    channel_id: str
    label: str

    @property
    def channel(self) -> Channel:
        return self.dataset.channel(self.channel_id)


def CurveDisplay_IsCompatible(channel: Channel, target: Channel, display_unit: str) -> bool:
    """Check both measurement meaning and physical units before sharing a plot axis."""
    dimension = Quantity_Dimension(channel.quantity)
    same_quantity = (
        dimension == Quantity_Dimension(target.quantity)
        if dimension is not None
        else channel.quantity == target.quantity
    )
    return (
        same_quantity
        and Unit_IsPhysicalForQuantity(channel.quantity, channel.data_unit)
        and Unit_IsPhysicalForQuantity(target.quantity, target.data_unit)
        and Unit_AreConvertible(channel.data_unit, display_unit)
    )
