from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

CALIBRATION_SCHEMA = "underline-retldc-calibration/1"
IDENTITY_CALIBRATION_ID = "builtin.calibration.identity"


class CalibrationSelectionSource(StrEnum):
    PROJECT = "project"
    USER_PROFILE = "user_profile"
    FACTORY_DEFAULT = "factory_default"


@dataclass(frozen=True, slots=True)
class CalibrationSelection:
    plugin_id: str = IDENTITY_CALIBRATION_ID
    parameters: Mapping[str, Any] = field(default_factory=dict)
    output_quantity: str | None = None
    output_unit: str | None = None
    source: CalibrationSelectionSource = CalibrationSelectionSource.FACTORY_DEFAULT
    profile_name: str | None = None


def Calibration_SelectionResolve(
    *,
    project: CalibrationSelection | None = None,
    matched_profile: CalibrationDocument | None = None,
) -> CalibrationSelection:
    """Resolve Project > matched user profile > factory Identity without using Unit."""
    if project is not None:
        return project
    if matched_profile is not None:
        return CalibrationSelection(
            plugin_id=matched_profile.model_id,
            parameters=dict(matched_profile.parameters),
            output_quantity=matched_profile.quantity,
            output_unit=matched_profile.output_unit,
            source=CalibrationSelectionSource.USER_PROFILE,
            profile_name=matched_profile.name,
        )
    return CalibrationSelection()


def Calibration_DefaultSelections(
    channel_ids: list[str] | tuple[str, ...],
) -> dict[str, CalibrationSelection]:
    """Every new Channel receives Identity, independent of quantity or unit."""
    return {str(channel_id): CalibrationSelection() for channel_id in channel_ids}


@dataclass(frozen=True, slots=True)
class CalibrationDocument:
    name: str
    quantity: str
    input_unit: str
    output_unit: str
    model_id: str
    model_version: str
    parameters: Mapping[str, Any]
    sensor: Mapping[str, Any] = field(default_factory=dict)
    notes: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("quantity", "input_unit", "output_unit", "model_id", "model_version"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"Calibration {field_name} must not be empty")
        for key in ("K", "B"):
            if key in self.parameters and not math.isfinite(float(self.parameters[key])):
                raise ValueError(f"Calibration parameter {key} must be finite")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": CALIBRATION_SCHEMA,
            "name": self.name,
            "quantity": self.quantity,
            "input_unit": self.input_unit,
            "output_unit": self.output_unit,
            "model": {
                "id": self.model_id,
                "version": self.model_version,
                "parameters": dict(self.parameters),
            },
            "sensor": dict(self.sensor),
            "notes": self.notes,
        }
        payload.update(dict(self.metadata))
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CalibrationDocument:
        if payload.get("schema") != CALIBRATION_SCHEMA:
            raise ValueError(f"Unsupported calibration schema: {payload.get('schema')!r}")
        model = payload.get("model")
        if not isinstance(model, Mapping):
            raise ValueError("Calibration model must be an object")
        known = {
            "schema",
            "name",
            "quantity",
            "input_unit",
            "output_unit",
            "model",
            "sensor",
            "notes",
        }
        return cls(
            name=str(payload.get("name", "")),
            quantity=str(payload["quantity"]),
            input_unit=str(payload["input_unit"]),
            output_unit=str(payload["output_unit"]),
            model_id=str(model["id"]),
            model_version=str(model["version"]),
            parameters=dict(model.get("parameters", {})),
            sensor=dict(payload.get("sensor", {})),
            notes=str(payload.get("notes", "")),
            metadata={key: value for key, value in payload.items() if key not in known},
        )


def Calibration_Save(document: CalibrationDocument, destination: Path) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)


def Calibration_Load(source: Path) -> CalibrationDocument:
    try:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load calibration file {source}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("Calibration JSON root must be an object")
    return CalibrationDocument.from_dict(payload)
