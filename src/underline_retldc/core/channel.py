from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from underline_retldc.core.units import (
    Unit_ConvertValues,
    Unit_DisplayUnitResolve,
    Unit_Resolve,
    UnitDisplayMode,
    UnitSource,
)


@dataclass(frozen=True, slots=True)
class Channel:
    id: str
    quantity: str
    unit: str | None
    values: NDArray[np.float64] | ArrayLike
    role: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    unit_source: UnitSource | str | None = None
    display_unit: str | None = None
    semantic_role: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Channel id must not be empty")
        if not self.quantity.strip():
            raise ValueError("Channel quantity must not be empty")
        if not self.role.strip():
            raise ValueError("Channel role must not be empty")
        resolution = Unit_Resolve(self.quantity, self.unit, self.unit_source)
        values = np.asarray(self.values, dtype=np.float64)
        if values.ndim != 1:
            raise ValueError("Channel values must be one-dimensional")
        immutable_values = np.array(values, dtype=np.float64, copy=True)
        immutable_values.setflags(write=False)
        object.__setattr__(self, "values", immutable_values)
        metadata = dict(self.metadata)
        if resolution.diagnostic_code is not None:
            metadata.setdefault("unit_diagnostic_code", resolution.diagnostic_code)
            metadata.setdefault("unit_diagnostic_message", resolution.diagnostic_message)
        object.__setattr__(self, "unit", resolution.unit)
        object.__setattr__(self, "unit_source", resolution.source)
        display_unit = (
            Unit_DisplayUnitResolve(
                self.quantity,
                resolution.unit,
                override=self.display_unit,
            )
            if self.display_unit
            else None
        )
        object.__setattr__(self, "display_unit", display_unit)
        object.__setattr__(self, "semantic_role", self.semantic_role or None)
        object.__setattr__(self, "name", self.name or self.id)
        object.__setattr__(self, "metadata", MappingProxyType(metadata))

    @property
    def data_unit(self) -> str:
        assert self.unit is not None
        return self.unit

    def effective_display_unit(
        self,
        preferences: Mapping[str, str] | None = None,
        *,
        display_mode: UnitDisplayMode | str = UnitDisplayMode.ENGINEERING,
    ) -> str:
        return Unit_DisplayUnitResolve(
            self.quantity,
            self.data_unit,
            override=self.display_unit,
            preferences=preferences,
            display_mode=display_mode,
        )

    def display_values(
        self,
        display_unit: str | None = None,
        *,
        preferences: Mapping[str, str] | None = None,
        display_mode: UnitDisplayMode | str = UnitDisplayMode.ENGINEERING,
    ) -> NDArray[np.float64]:
        target = display_unit or self.effective_display_unit(
            preferences,
            display_mode=display_mode,
        )
        return Unit_ConvertValues(self.values, self.data_unit, target)

    def with_unit_interpretation(
        self,
        *,
        quantity: str | None = None,
        data_unit: str | None = None,
        display_unit: str | None = None,
        semantic_role: str | None = None,
        unit_source: UnitSource | str = UnitSource.USER_OVERRIDE,
    ) -> Channel:
        """Return a metadata reinterpretation without changing any recorded value."""
        return Channel(
            id=self.id,
            name=self.name,
            quantity=quantity or self.quantity,
            unit=data_unit or self.data_unit,
            values=self.values,
            role=self.role,
            metadata=self.metadata,
            unit_source=unit_source,
            display_unit=display_unit,
            semantic_role=(
                self.semantic_role if semantic_role is None else semantic_role
            ),
        )

    def with_values(
        self,
        *,
        channel_id: str,
        values: ArrayLike,
        role: str,
        quantity: str | None = None,
        unit: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        unit_source: UnitSource | str | None = None,
        display_unit: str | None = None,
        semantic_role: str | None = None,
        name: str | None = None,
    ) -> Channel:
        return Channel(
            id=channel_id,
            quantity=quantity or self.quantity,
            unit=unit or self.data_unit,
            values=values,
            role=role,
            metadata=dict(metadata or {}),
            unit_source=unit_source or self.unit_source,
            display_unit=(self.display_unit if display_unit is None else display_unit),
            semantic_role=(
                self.semantic_role if semantic_role is None else semantic_role
            ),
            name=name or channel_id,
        )
