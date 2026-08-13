from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Any

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic


class PluginType(StrEnum):
    PARSER = "parser"
    CALIBRATION = "calibration"
    PROCESSOR = "processor"
    ANALYZER = "analyzer"
    EXPORTER = "exporter"


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    plugin_id: str
    plugin_type: PluginType
    version: str
    api_version: str
    name: str
    description: str
    translation_key: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("plugin_id", "version", "api_version", "name"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"Plugin descriptor {field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class ProbeContext:
    max_bytes: int = 65_536
    max_records: int = 100


@dataclass(frozen=True, slots=True)
class ProbeResult:
    confidence: float
    reason: str
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Probe confidence must be between zero and one")


class TaskCancelledError(RuntimeError):
    pass


@dataclass(slots=True)
class TaskContext:
    cancellation_event: Event = field(default_factory=Event)
    progress_callback: Callable[[float, str], None] | None = None

    def raise_if_cancelled(self) -> None:
        if self.cancellation_event.is_set():
            raise TaskCancelledError("Task was cancelled")

    def report_progress(self, progress: float, message: str = "") -> None:
        if self.progress_callback is not None:
            self.progress_callback(min(1.0, max(0.0, float(progress))), message)


@dataclass(frozen=True, slots=True)
class ParseResult:
    dataset: Dataset
    diagnostics: tuple[Diagnostic, ...] | list[Diagnostic] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    dataset: Dataset
    output_channel_ids: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] | list[Diagnostic] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    metrics: Mapping[str, float | int | str | None]
    diagnostics: tuple[Diagnostic, ...] | list[Diagnostic] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": dict(self.metrics),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ExportResult:
    destination: Path
    diagnostics: tuple[Diagnostic, ...] | list[Diagnostic] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "metadata", dict(self.metadata))

