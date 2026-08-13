from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from underline_retldc.plugin_api.common import PluginType


@dataclass(frozen=True, slots=True)
class PluginManifest:
    plugin_id: str
    plugin_type: PluginType
    api_version: str
    version: str
    entry: str
    name: str
    description: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PluginManifest:
        required = ("plugin_id", "plugin_type", "api_version", "version", "entry", "name")
        missing = [key for key in required if not payload.get(key)]
        if missing:
            raise ValueError(f"Plugin manifest is missing: {', '.join(missing)}")
        entry = str(payload["entry"])
        if entry.count(":") != 1:
            raise ValueError("Plugin entry must use module:ClassName")
        return cls(
            plugin_id=str(payload["plugin_id"]),
            plugin_type=PluginType(str(payload["plugin_type"])),
            api_version=str(payload["api_version"]),
            version=str(payload["version"]),
            entry=entry,
            name=str(payload["name"]),
            description=str(payload.get("description", "")),
        )


def Manifest_Load(source: Path) -> PluginManifest:
    try:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read plugin manifest {source}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("Plugin manifest root must be an object")
    return PluginManifest.from_dict(payload)

