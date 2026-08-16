from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from underline_retldc.app.version import __version__
from underline_retldc.core.diagnostics import Diagnostic
from underline_retldc.core.pipeline import ThrustPolarity_Normalize
from underline_retldc.core.project_data import PrimaryChannelBindings

PROJECT_SCHEMA = "underline-retldc-project/2"
PROJECT_LEGACY_SCHEMAS = ("underline-retldc-project/1",)


@dataclass(frozen=True, slots=True)
class PluginReference:
    id: str
    version: str
    api_version: str
    config: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "api_version": self.api_version,
            "config": dict(self.config),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PluginReference:
        return cls(
            id=str(payload["id"]),
            version=str(payload["version"]),
            api_version=str(payload["api_version"]),
            config=dict(payload.get("config", {})),
        )


@dataclass(frozen=True, slots=True)
class ProjectSourceState:
    source_id: str
    path: str
    sha256: str | None = None
    parser: PluginReference | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "path": self.path,
            "sha256": self.sha256,
            "parser": self.parser.to_dict() if self.parser is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ProjectSourceState:
        parser_payload = payload.get("parser")
        if parser_payload is not None and not isinstance(parser_payload, Mapping):
            raise ValueError("Project Source parser must be an object or null")
        return cls(
            source_id=str(payload["source_id"]),
            path=str(payload["path"]),
            sha256=(
                str(payload["sha256"])
                if payload.get("sha256") not in (None, "")
                else None
            ),
            parser=(
                PluginReference.from_dict(parser_payload)
                if isinstance(parser_payload, Mapping)
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ProjectStreamState:
    stream_id: str
    source_id: str
    time_offset_s: float = 0.0
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "source_id": self.source_id,
            "time_offset_s": self.time_offset_s,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ProjectStreamState:
        return cls(
            stream_id=str(payload["stream_id"]),
            source_id=str(payload["source_id"]),
            time_offset_s=float(payload.get("time_offset_s", 0.0)),
            name=(str(payload["name"]) if payload.get("name") else None),
        )


@dataclass(frozen=True, slots=True)
class ChannelProjectState:
    channel_id: str
    quantity: str
    data_unit: str
    unit_source: str
    display_unit: str | None = None
    semantic_role: str | None = None
    calibration: PluginReference | None = None
    output_channel_id: str | None = None
    source_id: str | None = None
    stream_id: str | None = None

    @property
    def persistent_key(self) -> str:
        if self.source_id is not None and self.stream_id is not None:
            return f"{self.source_id}/{self.stream_id}/{self.channel_id}"
        return self.channel_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "quantity": self.quantity,
            "data_unit": self.data_unit,
            "unit_source": self.unit_source,
            "source_id": self.source_id,
            "stream_id": self.stream_id,
            "display_unit": self.display_unit,
            "semantic_role": self.semantic_role,
            "calibration": (
                self.calibration.to_dict() if self.calibration is not None else None
            ),
            "output_channel_id": self.output_channel_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ChannelProjectState:
        calibration = payload.get("calibration")
        if calibration is not None and not isinstance(calibration, Mapping):
            raise ValueError("Channel calibration must be an object or null")
        return cls(
            channel_id=str(payload["channel_id"]),
            quantity=str(payload["quantity"]),
            data_unit=str(payload["data_unit"]),
            unit_source=str(payload["unit_source"]),
            source_id=(
                str(payload["source_id"])
                if payload.get("source_id") not in (None, "")
                else None
            ),
            stream_id=(
                str(payload["stream_id"])
                if payload.get("stream_id") not in (None, "")
                else None
            ),
            display_unit=(
                str(payload["display_unit"])
                if payload.get("display_unit") not in (None, "")
                else None
            ),
            semantic_role=(
                str(payload["semantic_role"])
                if payload.get("semantic_role") not in (None, "")
                else None
            ),
            calibration=(
                PluginReference.from_dict(calibration)
                if isinstance(calibration, Mapping)
                else None
            ),
            output_channel_id=(
                str(payload["output_channel_id"])
                if payload.get("output_channel_id") not in (None, "")
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ProjectDocument:
    source_path: str | None = None
    source_hash: str | None = None
    sources: tuple[ProjectSourceState, ...] = field(default_factory=tuple)
    streams: tuple[ProjectStreamState, ...] = field(default_factory=tuple)
    parser: PluginReference | None = None
    calibration: PluginReference | None = None
    processors: tuple[PluginReference, ...] = field(default_factory=tuple)
    regions: Mapping[str, tuple[float, float] | list[float] | None] = field(
        default_factory=dict
    )
    channels: Mapping[str, ChannelProjectState] = field(default_factory=dict)
    primary_channels: PrimaryChannelBindings = field(
        default_factory=PrimaryChannelBindings
    )
    primary_channels_explicit: bool = True
    thrust_polarity: int = 1
    processing_metadata: Mapping[str, Any] = field(default_factory=dict)
    analyzer: PluginReference | None = None
    motor_metadata: Mapping[str, Any] = field(default_factory=dict)
    export_settings: Mapping[str, Any] = field(default_factory=dict)
    workflow_state: Mapping[str, bool] = field(default_factory=dict)
    locale: str = "zh_CN"
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
    software_version: str = __version__

    def __post_init__(self) -> None:
        regions = dict(self.regions)
        if "active_test" not in regions and "burn" in regions:
            regions["active_test"] = regions["burn"]
        regions.pop("burn", None)
        object.__setattr__(self, "regions", regions)
        polarity = ThrustPolarity_Normalize(self.thrust_polarity)
        object.__setattr__(self, "thrust_polarity", polarity)

    def to_dict(self) -> dict[str, Any]:
        source = None
        if self.source_path is not None or self.source_hash is not None:
            source = {"path": self.source_path, "sha256": self.source_hash}
        return {
            "schema": PROJECT_SCHEMA,
            "software_version": self.software_version,
            "source": source,
            "sources": [item.to_dict() for item in self.sources],
            "streams": [item.to_dict() for item in self.streams],
            "parser": self.parser.to_dict() if self.parser is not None else None,
            "calibration": (
                self.calibration.to_dict() if self.calibration is not None else None
            ),
            "processors": [item.to_dict() for item in self.processors],
            "regions": {
                key: list(value) if value is not None else None
                for key, value in self.regions.items()
            },
            "channels": {
                key: value.to_dict() for key, value in self.channels.items()
            },
            "primary_channels": self.primary_channels.to_dict(),
            "thrust_polarity": self.thrust_polarity,
            "processing_metadata": dict(self.processing_metadata),
            "analyzer": self.analyzer.to_dict() if self.analyzer is not None else None,
            "motor_metadata": dict(self.motor_metadata),
            "export_settings": dict(self.export_settings),
            "workflow_state": dict(self.workflow_state),
            "locale": self.locale,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ProjectDocument:
        if payload.get("schema") not in (PROJECT_SCHEMA, *PROJECT_LEGACY_SCHEMAS):
            raise ValueError(f"Unsupported project schema: {payload.get('schema')!r}")
        source = payload.get("source")
        if source is not None and not isinstance(source, Mapping):
            raise ValueError("Project source must be an object or null")
        sources_payload = payload.get("sources", [])
        streams_payload = payload.get("streams", [])
        if not isinstance(sources_payload, (list, tuple)):
            raise ValueError("Project sources must be an array")
        if not isinstance(streams_payload, (list, tuple)):
            raise ValueError("Project streams must be an array")
        if any(not isinstance(item, Mapping) for item in sources_payload):
            raise ValueError("Every Project Source must be an object")
        if any(not isinstance(item, Mapping) for item in streams_payload):
            raise ValueError("Every Project Stream must be an object")
        sources = tuple(ProjectSourceState.from_dict(item) for item in sources_payload)
        streams = tuple(ProjectStreamState.from_dict(item) for item in streams_payload)
        source_ids = {item.source_id for item in sources}
        if len(source_ids) != len(sources):
            raise ValueError("Project Source IDs must be unique")
        stream_ids = {item.stream_id for item in streams}
        if len(stream_ids) != len(streams):
            raise ValueError("Project Stream IDs must be unique")
        if any(item.source_id not in source_ids for item in streams):
            raise ValueError("Project Stream refers to an unknown Source")
        regions_payload = payload.get("regions", {})
        if not isinstance(regions_payload, Mapping):
            raise ValueError("Project regions must be an object")
        regions: dict[str, tuple[float, float] | None] = {}
        if regions_payload:
            normalized_regions = dict(regions_payload)
            if "active_test" not in normalized_regions and "burn" in normalized_regions:
                normalized_regions["active_test"] = normalized_regions["burn"]
            for key in ("pre", "active_test", "post"):
                value = normalized_regions.get(key)
                if value is None and key != "active_test":
                    if key in regions_payload:
                        regions[key] = None
                    continue
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise ValueError(f"Project region {key!r} must contain start/end")
                start, end = float(value[0]), float(value[1])
                if start >= end:
                    raise ValueError(f"Project region {key!r} is invalid")
                regions[key] = (start, end)

        channels_payload = payload.get("channels", {})
        if not isinstance(channels_payload, Mapping):
            raise ValueError("Project channels must be an object")
        channels: dict[str, ChannelProjectState] = {}
        for channel_id, channel_payload in channels_payload.items():
            if not isinstance(channel_payload, Mapping):
                raise ValueError(f"Project Channel {channel_id!r} must be an object")
            state = ChannelProjectState.from_dict(channel_payload)
            if str(channel_id) not in {state.channel_id, state.persistent_key}:
                raise ValueError(f"Project Channel key {channel_id!r} does not match channel_id")
            channels[str(channel_id)] = state
        primary_channels_payload = payload.get("primary_channels")
        primary_channels_explicit = "primary_channels" in payload
        if primary_channels_payload is None:
            primary_channels = PrimaryChannelBindings()
        elif isinstance(primary_channels_payload, Mapping):
            primary_channels = PrimaryChannelBindings.from_dict(
                primary_channels_payload
            )
        else:
            raise ValueError("Project primary_channels must be an object")
        processing_metadata_payload = payload.get("processing_metadata", {})
        if not isinstance(processing_metadata_payload, Mapping):
            raise ValueError("Project processing_metadata must be an object")

        processors_payload = payload.get("processors", [])
        if not isinstance(processors_payload, (list, tuple)):
            raise ValueError("Project processors must be an array")
        if any(not isinstance(item, Mapping) for item in processors_payload):
            raise ValueError("Every Project Processor must be an object")
        processor_references: list[PluginReference] = []
        legacy_processor_sign: Any = None
        for index, item in enumerate(processors_payload):
            reference = PluginReference.from_dict(item)
            config = dict(reference.config)
            if (
                index == 0
                and reference.id == "builtin.processor.vertical_linear_baseline"
                and "sign" in config
            ):
                if legacy_processor_sign is None:
                    legacy_processor_sign = config["sign"]
                config.pop("sign", None)
                reference = PluginReference(
                    id=reference.id,
                    version=reference.version,
                    api_version=reference.api_version,
                    config=config,
                )
            processor_references.append(reference)
        thrust_polarity_value = payload.get(
            "thrust_polarity",
            legacy_processor_sign if legacy_processor_sign is not None else 1,
        )
        try:
            thrust_polarity = ThrustPolarity_Normalize(thrust_polarity_value)
        except ValueError as exc:
            raise ValueError("Project thrust_polarity must be +1 or -1") from exc
        motor_metadata_payload = payload.get("motor_metadata", {})
        if not isinstance(motor_metadata_payload, Mapping):
            raise ValueError("Project motor_metadata must be an object")
        export_settings_payload = payload.get("export_settings", {})
        if not isinstance(export_settings_payload, Mapping):
            raise ValueError("Project export_settings must be an object")
        parser_payload = payload.get("parser")
        calibration_payload = payload.get("calibration")
        analyzer_payload = payload.get("analyzer")
        workflow_state_payload = payload.get("workflow_state")
        if workflow_state_payload is None:
            workflow_state: dict[str, bool] = {
                "parsed": parser_payload is not None,
                "calibrated": calibration_payload is not None,
                "processed": bool(payload.get("processors")),
                "analyzed": analyzer_payload is not None,
            }
        elif isinstance(workflow_state_payload, Mapping):
            workflow_state = {}
            for key, value in workflow_state_payload.items():
                if not isinstance(value, bool):
                    raise ValueError(
                        f"Project workflow state {key!r} must be a boolean"
                    )
                workflow_state[str(key)] = value
        else:
            raise ValueError("Project workflow_state must be an object")
        for key, value in (
            ("parser", parser_payload),
            ("calibration", calibration_payload),
            ("analyzer", analyzer_payload),
        ):
            if value is not None and not isinstance(value, Mapping):
                raise ValueError(f"Project {key} must be an object or null")
        return cls(
            source_path=(
                None
                if source is None or source.get("path") in (None, "")
                else str(source["path"])
            ),
            source_hash=(
                None
                if source is None or source.get("sha256") in (None, "")
                else str(source["sha256"])
            ),
            sources=sources,
            streams=streams,
            parser=(
                PluginReference.from_dict(parser_payload)
                if isinstance(parser_payload, Mapping)
                else None
            ),
            calibration=(
                PluginReference.from_dict(calibration_payload)
                if isinstance(calibration_payload, Mapping)
                else None
            ),
            processors=tuple(processor_references),
            regions=regions,
            channels=channels,
            primary_channels=primary_channels,
            primary_channels_explicit=primary_channels_explicit,
            thrust_polarity=thrust_polarity,
            processing_metadata=dict(processing_metadata_payload),
            analyzer=(
                PluginReference.from_dict(analyzer_payload)
                if isinstance(analyzer_payload, Mapping)
                else None
            ),
            motor_metadata=dict(motor_metadata_payload),
            export_settings=dict(export_settings_payload),
            workflow_state=workflow_state,
            locale=str(payload.get("locale", "zh_CN")),
            diagnostics=tuple(
                Diagnostic.from_dict(item) for item in payload.get("diagnostics", [])
            ),
            software_version=str(payload.get("software_version", "unknown")),
        )


def Project_SourceHash(source: Path, *, block_size: int = 1_048_576) -> str:
    digest = hashlib.sha256()
    with Path(source).open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


class ProjectSourceResolveResult(StrEnum):
    FOUND = "found"
    RELOCATED = "relocated"
    NOT_CONFIGURED = "not_configured"
    MISSING = "missing"
    HASH_MISMATCH = "hash_mismatch"


class ProjectSourceHashMismatchError(ValueError):
    def __init__(self, expected_hash: str, actual_hash: str) -> None:
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            "Project source hash does not match; source data changed "
            f"(expected {expected_hash}, got {actual_hash})"
        )


@dataclass(frozen=True, slots=True)
class ProjectSourceResolution:
    result: ProjectSourceResolveResult
    path: Path | None = None
    actual_hash: str | None = None


def Project_SourceResolve(
    document: ProjectDocument,
    *,
    project_path: Path | None = None,
    relocated_source: Path | None = None,
) -> ProjectSourceResolution:
    if relocated_source is not None:
        candidate = Path(relocated_source)
        relocated = True
    elif document.source_path is None:
        return ProjectSourceResolution(ProjectSourceResolveResult.NOT_CONFIGURED)
    else:
        configured = Path(document.source_path)
        candidate = configured
        if not configured.is_absolute() and project_path is not None:
            candidate = Path(project_path).parent / configured
        relocated = False
    if not candidate.is_file():
        return ProjectSourceResolution(ProjectSourceResolveResult.MISSING, candidate)
    resolved = candidate.resolve()
    actual_hash = Project_SourceHash(resolved)
    if document.source_hash and actual_hash != document.source_hash:
        return ProjectSourceResolution(
            ProjectSourceResolveResult.HASH_MISMATCH,
            resolved,
            actual_hash,
        )
    return ProjectSourceResolution(
        ProjectSourceResolveResult.RELOCATED if relocated else ProjectSourceResolveResult.FOUND,
        resolved,
        actual_hash,
    )


def Project_DefaultExportDirectory(
    project_path: Path | None,
    *,
    source_path: Path | None = None,
    fallback_directory: Path | None = None,
) -> Path:
    if project_path is not None:
        path = Path(project_path)
        filename = path.name
        suffix = ".retldc.json"
        stem = filename[: -len(suffix)] if filename.lower().endswith(suffix) else path.stem
        return path.parent / f"{stem}_exports"
    if source_path is not None:
        source = Path(source_path)
        return source.parent / f"{source.stem}_exports"
    return Path(fallback_directory or Path.cwd()) / "Untitled_Project_exports"


def Project_Save(document: ProjectDocument, destination: Path) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)


def Project_Load(source: Path) -> ProjectDocument:
    try:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load project file {source}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("Project JSON root must be an object")
    return ProjectDocument.from_dict(payload)
