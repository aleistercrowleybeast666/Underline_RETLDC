from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.motor_parameters import MOTOR_PHYSICAL_FIELDS, MotorPhysicalParameters
from underline_retldc.core.project_data import ChannelReference


@dataclass(frozen=True, slots=True)
class SourceAnalysisConfig:
    """Independent scientific input/configuration; contains no display-clock transform."""

    source_id: str
    workspace_id: str
    channels: tuple[ChannelReference, ...] = ()
    interval: tuple[float, float] | None = None  # None explicitly means full record.
    propellant_mass_kg: float | None = None
    input_stage: str = "calibrated"
    polarity: int = 1
    processor: Mapping[str, Any] | None = None
    pre: tuple[float, float] | None = None
    post: tuple[float, float] | None = None
    mass_source: str = "source"  # Legacy/configured source value; new GUI drafts use "project".
    legacy_physical_parameters: Mapping[str, float | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id or not self.workspace_id:
            raise ValueError("Source analysis requires Source and workspace IDs")
        if self.workspace_id not in {
            "thrust_analysis", "chamber_pressure", "temperature", "data_explorer",
        }:
            raise ValueError("Unsupported source calculation workspace")
        channels = tuple(self.channels)
        if any(item.source_id != self.source_id for item in channels):
            raise ValueError("Source analysis cannot mix Channels from different Sources")
        if len({item.stable_id for item in channels}) != len(channels):
            raise ValueError("Source analysis Channels must be unique")
        object.__setattr__(self, "channels", channels)
        if self.input_stage not in {"calibrated", "project_processed"}:
            raise ValueError("Unsupported source analysis input stage")
        if self.mass_source not in {"source", "project"}:
            raise ValueError("Source analysis mass_source must be source or project")
        if not isinstance(self.legacy_physical_parameters, Mapping):
            raise ValueError("Legacy physical parameters must be an object")
        MotorPhysicalParameters.from_metadata(self.legacy_physical_parameters)
        if isinstance(self.polarity, bool) or self.polarity not in {-1, 1}:
            raise ValueError("Source analysis polarity must be +1 or -1")
        for key in ("interval", "pre", "post"):
            value = getattr(self, key)
            if value is not None:
                if not isinstance(value, (tuple, list)) or len(value) != 2:
                    raise ValueError(f"Source analysis {key} must contain start/end")
                try:
                    pair = tuple(float(item) for item in value)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError(f"Source analysis {key} must be numeric") from exc
                if not all(math.isfinite(item) for item in pair):
                    raise ValueError(f"Source analysis {key} must be finite")
                object.__setattr__(self, key, pair)
        if self.propellant_mass_kg is not None:
            try:
                mass = float(self.propellant_mass_kg)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Source propellant mass must be numeric or null") from exc
            if not math.isfinite(mass):
                raise ValueError("Source propellant mass must be finite")
            object.__setattr__(self, "propellant_mass_kg", mass)
        if self.processor is not None:
            if not isinstance(self.processor, Mapping):
                raise ValueError("Source Processor reference must be an object")
            for key in ("id", "version", "api_version", "config"):
                if key not in self.processor:
                    raise ValueError(f"Source Processor reference is missing {key}")
            if not isinstance(self.processor["config"], Mapping):
                raise ValueError("Source Processor config must be an object")

    @property
    def key(self) -> str:
        return f"{self.source_id}/{self.workspace_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "workspace_id": self.workspace_id,
            "channels": [item.to_dict() for item in self.channels],
            "interval": list(self.interval) if self.interval is not None else None,
            "propellant_mass_kg": self.propellant_mass_kg,
            "input_stage": self.input_stage,
            "polarity": self.polarity,
            "processor": dict(self.processor) if self.processor is not None else None,
            "pre": list(self.pre) if self.pre is not None else None,
            "post": list(self.post) if self.post is not None else None,
            "mass_source": self.mass_source,
            "legacy_physical_parameters": dict(self.legacy_physical_parameters),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SourceAnalysisConfig:
        if not payload.get("source_id") or not payload.get("workspace_id"):
            raise ValueError("Source analysis requires Source and workspace IDs")
        channels = payload.get("channels", [])
        if not isinstance(channels, (tuple, list)) or any(
            not isinstance(item, Mapping) for item in channels
        ):
            raise ValueError("Source analysis channels must be an array of references")
        legacy = payload.get("legacy_physical_parameters", {})
        if not isinstance(legacy, Mapping):
            raise ValueError("Legacy physical parameters must be an object")
        return cls(
            source_id=str(payload["source_id"]),
            workspace_id=str(payload["workspace_id"]),
            channels=tuple(ChannelReference.from_dict(item) for item in channels),
            interval=payload.get("interval"),
            propellant_mass_kg=payload.get("propellant_mass_kg"),
            input_stage=str(payload.get("input_stage", "calibrated")),
            polarity=payload.get("polarity", 1),
            processor=payload.get("processor"),
            pre=payload.get("pre"),
            post=payload.get("post"),
            mass_source=str(payload.get("mass_source", "source")),
            legacy_physical_parameters={
                **dict(legacy),
                **{name: payload[name] for name in MOTOR_PHYSICAL_FIELDS
                   if name != "propellant_mass_kg" and name in payload},
            },
        )


def SourceAnalysis_UseSharedMotor(
    config: SourceAnalysisConfig, parameters: MotorPhysicalParameters,
) -> SourceAnalysisConfig:
    legacy = dict(config.legacy_physical_parameters)
    if (config.mass_source == "source"
            and config.propellant_mass_kg is not None
            and config.propellant_mass_kg != parameters.propellant_mass_kg):
        legacy.setdefault("propellant_mass_kg", config.propellant_mass_kg)
    return replace(
        config, mass_source="project", propellant_mass_kg=parameters.propellant_mass_kg,
        legacy_physical_parameters=legacy,
    )


@dataclass(frozen=True, slots=True)
class SourceAnalysisInput:
    reference: ChannelReference
    dataset: Dataset
    channel_id: str
    label: str
    processing_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceAnalysisDocument:
    config: SourceAnalysisConfig
    completed: bool = False
    calculator: Mapping[str, Any] = field(default_factory=dict)
    results: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "completed": self.completed,
            "calculator": dict(self.calculator),
            "results": dict(self.results),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SourceAnalysisDocument:
        config = payload.get("config")
        completed = payload.get("completed", False)
        calculator = payload.get("calculator", {})
        results = payload.get("results", {})
        if not isinstance(config, Mapping) or not isinstance(completed, bool):
            raise ValueError("Source analysis config/completed fields are invalid")
        if not isinstance(calculator, Mapping) or not isinstance(results, Mapping):
            raise ValueError("Source analysis calculator/results must be objects")
        return cls(
            SourceAnalysisConfig.from_dict(config), completed, dict(calculator), dict(results)
        )
