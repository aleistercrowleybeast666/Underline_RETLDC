from __future__ import annotations

from dataclasses import dataclass

from underline_retldc.core.channel import Channel
from underline_retldc.core.units import Quantity_Dimension


@dataclass(frozen=True, slots=True)
class WorkspaceChannelCapability:
    """User-facing measurement category backed by a real analysis workspace."""

    capability_id: str
    workspace_id: str
    display_key: str
    quantity: str
    semantic_role: str
    multiple_allowed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "capability_id",
            "workspace_id",
            "display_key",
            "quantity",
            "semantic_role",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"Workspace capability {field_name} must not be empty")

    @property
    def dimension(self) -> str | None:
        return Quantity_Dimension(self.quantity)

    def matches_channel(self, channel: Channel) -> bool:
        if channel.semantic_role == "auxiliary":
            return False
        if channel.semantic_role == self.semantic_role:
            return True
        return Quantity_Dimension(channel.quantity) == self.dimension


class WorkspaceChannelCapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, WorkspaceChannelCapability] = {}

    def register(self, capability: WorkspaceChannelCapability) -> None:
        if capability.capability_id in self._capabilities:
            raise ValueError(
                f"Workspace capability {capability.capability_id!r} is already registered"
            )
        self._capabilities[capability.capability_id] = capability

    def get(self, capability_id: str) -> WorkspaceChannelCapability:
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise KeyError(
                f"Workspace capability {capability_id!r} is not registered"
            ) from exc

    @property
    def capabilities(self) -> tuple[WorkspaceChannelCapability, ...]:
        return tuple(self._capabilities.values())

    def mapping_type(
        self,
        *,
        quantity: str | None,
        semantic_role: str | None,
    ) -> str | None:
        if semantic_role == "auxiliary":
            return None
        if semantic_role:
            role_matches = tuple(
                item
                for item in self._capabilities.values()
                if item.semantic_role == semantic_role
            )
            if len(role_matches) == 1:
                return role_matches[0].capability_id
        if quantity:
            dimension = Quantity_Dimension(quantity)
            quantity_matches = tuple(
                item
                for item in self._capabilities.values()
                if item.dimension == dimension
            )
            if len(quantity_matches) == 1:
                return quantity_matches[0].capability_id
        return None


def WorkspaceCapabilities_Default() -> WorkspaceChannelCapabilityRegistry:
    registry = WorkspaceChannelCapabilityRegistry()
    for capability in (
        WorkspaceChannelCapability(
            "thrust",
            "thrust_analysis",
            "mapping.type.thrust",
            "force",
            "thrust",
        ),
        WorkspaceChannelCapability(
            "chamber_pressure",
            "chamber_pressure",
            "mapping.type.chamber_pressure",
            "pressure",
            "chamber_pressure",
        ),
        WorkspaceChannelCapability(
            "temperature",
            "temperature",
            "mapping.type.temperature",
            "temperature",
            "temperature",
            multiple_allowed=True,
        ),
    ):
        registry.register(capability)
    return registry
