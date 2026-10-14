from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MOTOR_PHYSICAL_FIELDS = (
    "propellant_mass_kg", "total_motor_mass_kg", "diameter_mm", "length_mm",
)


@dataclass(frozen=True, slots=True)
class MotorPhysicalParameters:
    propellant_mass_kg: float | None = None
    total_motor_mass_kg: float | None = None
    diameter_mm: float | None = None
    length_mm: float | None = None

    def __post_init__(self) -> None:
        for name in MOTOR_PHYSICAL_FIELDS:
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool):
                raise ValueError(f"Motor parameter {name} must be numeric or null")
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"Motor parameter {name} must be numeric or null") from exc
            if not math.isfinite(number):
                raise ValueError(f"Motor parameter {name} must be finite")
            object.__setattr__(self, name, number)

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any]) -> MotorPhysicalParameters:
        return cls(**{name: metadata.get(name) for name in MOTOR_PHYSICAL_FIELDS})

    def to_dict(self) -> dict[str, float | None]:
        return {name: getattr(self, name) for name in MOTOR_PHYSICAL_FIELDS}
