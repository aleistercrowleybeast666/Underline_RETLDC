from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import ArrayLike, NDArray

G0_STANDARD_M_S2 = 9.80665
UNKNOWN_SI_UNIT = "unknown_si"


class UnitSource(StrEnum):
    """Provenance of a Channel's scientific data-unit interpretation."""

    PLUGIN_DECLARED = "plugin_declared"
    DEFAULT_SI = "default_si"
    USER_OVERRIDE = "user_override"
    CALIBRATION_OUTPUT = "calibration_output"
    UNKNOWN = "unknown"


class UnitDisplayMode(StrEnum):
    """How compatible physical values are presented without changing Project data."""

    ENGINEERING = "engineering"
    SI_SCIENTIFIC = "si_scientific"


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    symbol: str
    dimension: str | None
    scale_to_si: float = 1.0
    offset_to_si: float = 0.0
    engineering: bool = True

    def to_si(self, values: NDArray[np.float64]) -> NDArray[np.float64]:
        return values * self.scale_to_si + self.offset_to_si

    def from_si(self, values: NDArray[np.float64]) -> NDArray[np.float64]:
        return (values - self.offset_to_si) / self.scale_to_si


@dataclass(frozen=True, slots=True)
class QuantityDefinition:
    dimension: str
    canonical_si: str
    default_display_unit: str


@dataclass(frozen=True, slots=True)
class UnitResolution:
    unit: str
    source: UnitSource
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None


_UNIT_DEFINITIONS: dict[str, UnitDefinition] = {
    "s": UnitDefinition("s", "time"),
    "ms": UnitDefinition("ms", "time", 1.0e-3),
    "us": UnitDefinition("us", "time", 1.0e-6),
    "N": UnitDefinition("N", "force"),
    "kN": UnitDefinition("kN", "force", 1.0e3),
    "Pa": UnitDefinition("Pa", "pressure"),
    "kPa": UnitDefinition("kPa", "pressure", 1.0e3),
    "MPa": UnitDefinition("MPa", "pressure", 1.0e6),
    "bar": UnitDefinition("bar", "pressure", 1.0e5),
    "psi": UnitDefinition("psi", "pressure", 6_894.757293168),
    "K": UnitDefinition("K", "temperature"),
    "°C": UnitDefinition("°C", "temperature", 1.0, 273.15),
    "kg": UnitDefinition("kg", "mass"),
    "g": UnitDefinition("g", "mass", 1.0e-3),
    "m": UnitDefinition("m", "length"),
    "mm": UnitDefinition("mm", "length", 1.0e-3),
    "m²": UnitDefinition("m²", "area"),
    "mm²": UnitDefinition("mm²", "area", 1.0e-6),
    "m³": UnitDefinition("m³", "volume"),
    "mm³": UnitDefinition("mm³", "volume", 1.0e-9),
    "m/s": UnitDefinition("m/s", "velocity"),
    "m/s²": UnitDefinition("m/s²", "acceleration"),
    "kg/s": UnitDefinition("kg/s", "mass_flow"),
    "m³/s": UnitDefinition("m³/s", "volume_flow"),
    "kg/m³": UnitDefinition("kg/m³", "density"),
    "Hz": UnitDefinition("Hz", "frequency"),
    "rad/s": UnitDefinition("rad/s", "angular_velocity"),
    "N·m": UnitDefinition("N·m", "torque"),
    "J": UnitDefinition("J", "energy"),
    "W": UnitDefinition("W", "power"),
    "V": UnitDefinition("V", "voltage"),
    "1": UnitDefinition("1", "dimensionless"),
    "raw": UnitDefinition("raw", None, engineering=False),
    "count": UnitDefinition("count", None, engineering=False),
    "ADC": UnitDefinition("ADC", None, engineering=False),
    UNKNOWN_SI_UNIT: UnitDefinition(UNKNOWN_SI_UNIT, None, engineering=False),
}

_UNIT_ALIASES: dict[str, str] = {
    "sec": "s",
    "newton": "N",
    "kn": "kN",
    "kpa": "kPa",
    "mpa": "MPa",
    "c": "°C",
    "degc": "°C",
    "celsius": "°C",
    "m2": "m²",
    "m^2": "m²",
    "mm2": "mm²",
    "mm^2": "mm²",
    "m3": "m³",
    "m^3": "m³",
    "mm3": "mm³",
    "mm^3": "mm³",
    "m/s^2": "m/s²",
    "m/s2": "m/s²",
    "m3/s": "m³/s",
    "m^3/s": "m³/s",
    "kg/m3": "kg/m³",
    "kg/m^3": "kg/m³",
    "n*m": "N·m",
    "n.m": "N·m",
    "dimensionless": "1",
    "counts": "count",
    "adc": "ADC",
}

_QUANTITY_DEFINITIONS: dict[str, QuantityDefinition] = {
    "time": QuantityDefinition("time", "s", "s"),
    "force": QuantityDefinition("force", "N", "N"),
    "thrust": QuantityDefinition("force", "N", "N"),
    "pressure": QuantityDefinition("pressure", "Pa", "MPa"),
    "chamber_pressure": QuantityDefinition("pressure", "Pa", "MPa"),
    "temperature": QuantityDefinition("temperature", "K", "°C"),
    "mass": QuantityDefinition("mass", "kg", "kg"),
    "length": QuantityDefinition("length", "m", "mm"),
    "burned_web": QuantityDefinition("length", "m", "mm"),
    "area": QuantityDefinition("area", "m²", "mm²"),
    "burn_area": QuantityDefinition("area", "m²", "mm²"),
    "volume": QuantityDefinition("volume", "m³", "m³"),
    "velocity": QuantityDefinition("velocity", "m/s", "m/s"),
    "acceleration": QuantityDefinition("acceleration", "m/s²", "m/s²"),
    "mass_flow": QuantityDefinition("mass_flow", "kg/s", "kg/s"),
    "volume_flow": QuantityDefinition("volume_flow", "m³/s", "m³/s"),
    "density": QuantityDefinition("density", "kg/m³", "kg/m³"),
    "frequency": QuantityDefinition("frequency", "Hz", "Hz"),
    "angular_velocity": QuantityDefinition("angular_velocity", "rad/s", "rad/s"),
    "torque": QuantityDefinition("torque", "N·m", "N·m"),
    "energy": QuantityDefinition("energy", "J", "J"),
    "power": QuantityDefinition("power", "W", "W"),
    "voltage": QuantityDefinition("voltage", "V", "V"),
    "strain": QuantityDefinition("dimensionless", "1", "1"),
    "ratio": QuantityDefinition("dimensionless", "1", "1"),
    "coefficient": QuantityDefinition("dimensionless", "1", "1"),
    "kn": QuantityDefinition("dimensionless", "1", "1"),
}

DEFAULT_DISPLAY_UNITS: Mapping[str, str] = {
    "force": "N",
    "pressure": "MPa",
    "temperature": "°C",
    "length": "mm",
    "area": "mm²",
    "mass": "kg",
}


def Quantity_Normalize(quantity: str) -> str:
    return str(quantity).strip().lower().replace(" ", "_")


def Quantity_Definition(quantity: str) -> QuantityDefinition | None:
    return _QUANTITY_DEFINITIONS.get(Quantity_Normalize(quantity))


def Quantity_CanonicalSIUnit(quantity: str) -> str | None:
    definition = Quantity_Definition(quantity)
    return definition.canonical_si if definition is not None else None


def Quantity_Dimension(quantity: str) -> str | None:
    definition = Quantity_Definition(quantity)
    return definition.dimension if definition is not None else None


def Unit_Normalize(unit: str) -> str:
    value = str(unit).strip()
    if value in _UNIT_DEFINITIONS:
        return value
    return _UNIT_ALIASES.get(value.casefold(), value)


def Unit_Definition(unit: str) -> UnitDefinition | None:
    return _UNIT_DEFINITIONS.get(Unit_Normalize(unit))


def UnitSource_Normalize(source: UnitSource | str | None) -> UnitSource | None:
    if source is None or str(source).strip() == "":
        return None
    if isinstance(source, UnitSource):
        return source
    aliases = {
        "parser": UnitSource.PLUGIN_DECLARED,
        "plugin": UnitSource.PLUGIN_DECLARED,
        "si_default": UnitSource.DEFAULT_SI,
        "project_override": UnitSource.USER_OVERRIDE,
        "user": UnitSource.USER_OVERRIDE,
        "calibration": UnitSource.CALIBRATION_OUTPUT,
    }
    normalized = str(source).strip().lower()
    try:
        return UnitSource(normalized)
    except ValueError:
        return aliases.get(normalized, UnitSource.UNKNOWN)


def UnitDisplayMode_Normalize(mode: UnitDisplayMode | str | None) -> UnitDisplayMode:
    if isinstance(mode, UnitDisplayMode):
        return mode
    try:
        return UnitDisplayMode(str(mode or "").strip().lower())
    except ValueError:
        return UnitDisplayMode.ENGINEERING


def Unit_Resolve(
    quantity: str,
    unit: str | None,
    source: UnitSource | str | None = None,
) -> UnitResolution:
    normalized_source = UnitSource_Normalize(source)
    if unit is not None and str(unit).strip():
        normalized_unit = Unit_Normalize(str(unit))
        return UnitResolution(
            normalized_unit,
            normalized_source or UnitSource.PLUGIN_DECLARED,
        )
    canonical = Quantity_CanonicalSIUnit(quantity)
    if canonical is not None:
        return UnitResolution(canonical, normalized_source or UnitSource.DEFAULT_SI)
    return UnitResolution(
        UNKNOWN_SI_UNIT,
        normalized_source or UnitSource.UNKNOWN,
        "unit.unknown_quantity_missing_unit",
        "Plugin did not declare a unit for an unknown quantity. Please verify the unit.",
    )


def Unit_IsEngineering(unit: str) -> bool:
    definition = Unit_Definition(unit)
    return bool(definition is not None and definition.engineering)


def Unit_IsPhysicalForQuantity(quantity: str, unit: str) -> bool:
    quantity_dimension = Quantity_Dimension(quantity)
    definition = Unit_Definition(unit)
    return bool(
        quantity_dimension is not None
        and definition is not None
        and definition.engineering
        and definition.dimension == quantity_dimension
    )


def Unit_AreConvertible(source_unit: str, destination_unit: str) -> bool:
    source = Unit_Definition(source_unit)
    destination = Unit_Definition(destination_unit)
    return bool(
        source is not None
        and destination is not None
        and source.engineering
        and destination.engineering
        and source.dimension is not None
        and source.dimension == destination.dimension
    )


def Unit_ConvertValues(
    values: ArrayLike,
    source_unit: str,
    destination_unit: str,
) -> NDArray[np.float64]:
    source_symbol = Unit_Normalize(source_unit)
    destination_symbol = Unit_Normalize(destination_unit)
    source = Unit_Definition(source_symbol)
    destination = Unit_Definition(destination_symbol)
    if source_symbol == destination_symbol:
        converted = np.array(values, dtype=np.float64, copy=True)
    elif not Unit_AreConvertible(source_symbol, destination_symbol):
        raise ValueError(
            f"Units {source_symbol!r} and {destination_symbol!r} are not convertible"
        )
    else:
        assert source is not None and destination is not None
        array = np.asarray(values, dtype=np.float64)
        converted = destination.from_si(source.to_si(array))
        converted = np.array(converted, dtype=np.float64, copy=True)
    converted.setflags(write=False)
    return converted


def Unit_ConvertValue(value: float, source_unit: str, destination_unit: str) -> float:
    return float(Unit_ConvertValues([value], source_unit, destination_unit)[0])


def Unit_DefaultDisplayUnit(quantity: str, data_unit: str) -> str:
    definition = Quantity_Definition(quantity)
    if definition is None:
        return Unit_Normalize(data_unit)
    candidate = definition.default_display_unit
    return candidate if Unit_AreConvertible(data_unit, candidate) else Unit_Normalize(data_unit)


def Unit_DisplayUnitResolve(
    quantity: str,
    data_unit: str,
    *,
    override: str | None = None,
    preferences: Mapping[str, str] | None = None,
    display_mode: UnitDisplayMode | str = UnitDisplayMode.ENGINEERING,
) -> str:
    if UnitDisplayMode_Normalize(display_mode) is UnitDisplayMode.SI_SCIENTIFIC:
        canonical = Quantity_CanonicalSIUnit(quantity)
        if canonical is not None and Unit_AreConvertible(data_unit, canonical):
            return canonical
        return Unit_Normalize(data_unit)
    if override:
        candidate = Unit_Normalize(override)
        if not Unit_AreConvertible(data_unit, candidate) and candidate != Unit_Normalize(
            data_unit
        ):
            raise ValueError(
                f"Display unit {candidate!r} is not compatible with data unit {data_unit!r}"
            )
        return candidate
    quantity_key = Quantity_Normalize(quantity)
    quantity_definition = Quantity_Definition(quantity_key)
    dimension = quantity_definition.dimension if quantity_definition is not None else None
    preference_map = dict(DEFAULT_DISPLAY_UNITS)
    preference_map.update(dict(preferences or {}))
    candidate = preference_map.get(quantity_key)
    if candidate is None and dimension is not None:
        candidate = preference_map.get(dimension)
    if candidate and Unit_AreConvertible(data_unit, candidate):
        return Unit_Normalize(candidate)
    return Unit_DefaultDisplayUnit(quantity, data_unit)


def Unit_ValueFormat(
    value: float | None,
    *,
    display_mode: UnitDisplayMode | str = UnitDisplayMode.ENGINEERING,
    precision: int = 8,
) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    if UnitDisplayMode_Normalize(display_mode) is UnitDisplayMode.SI_SCIENTIFIC:
        return f"{float(value):.{max(1, precision - 1)}e}"
    return f"{float(value):.{max(1, precision)}g}"


def Unit_ChoicesForQuantity(
    quantity: str, *, include_non_engineering: bool = True
) -> tuple[str, ...]:
    dimension = Quantity_Dimension(quantity)
    values = [
        definition.symbol
        for definition in _UNIT_DEFINITIONS.values()
        if definition.dimension == dimension and definition.engineering
    ]
    if include_non_engineering:
        values.extend(("raw", "count", "ADC"))
    return tuple(dict.fromkeys(values))


def Quantity_KnownIds() -> tuple[str, ...]:
    return tuple(_QUANTITY_DEFINITIONS)


def Unit_KnownSymbols() -> tuple[str, ...]:
    return tuple(_UNIT_DEFINITIONS)
