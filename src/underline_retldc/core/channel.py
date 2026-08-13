from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class Channel:
    id: str
    quantity: str
    unit: str
    values: NDArray[np.float64] | ArrayLike
    role: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Channel id must not be empty")
        if not self.quantity.strip():
            raise ValueError("Channel quantity must not be empty")
        if not self.unit.strip():
            raise ValueError("Channel unit must not be empty")
        if not self.role.strip():
            raise ValueError("Channel role must not be empty")
        values = np.asarray(self.values, dtype=np.float64)
        if values.ndim != 1:
            raise ValueError("Channel values must be one-dimensional")
        immutable_values = np.array(values, dtype=np.float64, copy=True)
        immutable_values.setflags(write=False)
        object.__setattr__(self, "values", immutable_values)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def with_values(
        self,
        *,
        channel_id: str,
        values: ArrayLike,
        role: str,
        quantity: str | None = None,
        unit: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Channel:
        return Channel(
            id=channel_id,
            quantity=quantity or self.quantity,
            unit=unit or self.unit,
            values=values,
            role=role,
            metadata=dict(metadata or {}),
        )

