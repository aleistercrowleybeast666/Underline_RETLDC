from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from underline_retldc.core.diagnostics import Diagnostic
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType


class PluginLoadResult(StrEnum):
    LOADED = "loaded"
    MANIFEST_ERROR = "manifest_error"
    API_MISMATCH = "api_mismatch"
    IMPORT_ERROR = "import_error"
    INITIALIZATION_ERROR = "initialization_error"
    DESCRIPTOR_MISMATCH = "descriptor_mismatch"
    DUPLICATE_ID = "duplicate_id"


@dataclass(frozen=True, slots=True)
class PluginRecord:
    descriptor: PluginDescriptor | None
    result: PluginLoadResult
    source: str
    source_kind: str = "unknown"
    plugin: Any | None = None
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
    manifest_plugin_id: str | None = None

    @property
    def plugin_id(self) -> str:
        if self.descriptor is not None:
            return self.descriptor.plugin_id
        return self.manifest_plugin_id or "unknown"


class PluginRegistry:
    def __init__(self) -> None:
        self._records: list[PluginRecord] = []
        self._plugins: dict[str, Any] = {}

    def register(
        self,
        plugin: Any,
        *,
        source: str,
        source_kind: str = "unknown",
    ) -> PluginRecord:
        descriptor = getattr(plugin, "descriptor", None)
        if not isinstance(descriptor, PluginDescriptor):
            raise TypeError("Plugin descriptor is missing or invalid")
        if descriptor.plugin_id in self._plugins:
            record = PluginRecord(
                descriptor=descriptor,
                result=PluginLoadResult.DUPLICATE_ID,
                source=source,
                source_kind=source_kind,
                plugin=None,
            )
            self._records.append(record)
            return record
        self._plugins[descriptor.plugin_id] = plugin
        record = PluginRecord(
            descriptor=descriptor,
            result=PluginLoadResult.LOADED,
            source=source,
            source_kind=source_kind,
            plugin=plugin,
        )
        self._records.append(record)
        return record

    def add_record(self, record: PluginRecord) -> None:
        self._records.append(record)

    def get(self, plugin_id: str) -> Any:
        try:
            return self._plugins[plugin_id]
        except KeyError as exc:
            raise KeyError(f"Plugin {plugin_id!r} is not loaded") from exc

    def plugins(self, plugin_type: PluginType | None = None) -> tuple[Any, ...]:
        plugins = tuple(self._plugins.values())
        if plugin_type is None:
            return plugins
        return tuple(item for item in plugins if item.descriptor.plugin_type is plugin_type)

    @property
    def records(self) -> tuple[PluginRecord, ...]:
        return tuple(self._records)
