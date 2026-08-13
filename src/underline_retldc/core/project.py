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

PROJECT_SCHEMA = "underline-retldc-project/1"


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
class ProjectDocument:
    source_path: str | None = None
    source_hash: str | None = None
    parser: PluginReference | None = None
    calibration: PluginReference | None = None
    processors: tuple[PluginReference, ...] = field(default_factory=tuple)
    regions: Mapping[str, tuple[float, float] | list[float]] = field(default_factory=dict)
    analyzer: PluginReference | None = None
    motor_metadata: Mapping[str, Any] = field(default_factory=dict)
    export_settings: Mapping[str, Any] = field(default_factory=dict)
    workflow_state: Mapping[str, bool] = field(default_factory=dict)
    locale: str = "zh_CN"
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
    software_version: str = __version__

    def to_dict(self) -> dict[str, Any]:
        source = None
        if self.source_path is not None or self.source_hash is not None:
            source = {"path": self.source_path, "sha256": self.source_hash}
        return {
            "schema": PROJECT_SCHEMA,
            "software_version": self.software_version,
            "source": source,
            "parser": self.parser.to_dict() if self.parser is not None else None,
            "calibration": (
                self.calibration.to_dict() if self.calibration is not None else None
            ),
            "processors": [item.to_dict() for item in self.processors],
            "regions": {key: list(value) for key, value in self.regions.items()},
            "analyzer": self.analyzer.to_dict() if self.analyzer is not None else None,
            "motor_metadata": dict(self.motor_metadata),
            "export_settings": dict(self.export_settings),
            "workflow_state": dict(self.workflow_state),
            "locale": self.locale,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ProjectDocument:
        if payload.get("schema") != PROJECT_SCHEMA:
            raise ValueError(f"Unsupported project schema: {payload.get('schema')!r}")
        source = payload.get("source")
        if source is not None and not isinstance(source, Mapping):
            raise ValueError("Project source must be an object or null")
        regions_payload = payload.get("regions", {})
        if not isinstance(regions_payload, Mapping):
            raise ValueError("Project regions must be an object")
        regions: dict[str, tuple[float, float]] = {}
        if regions_payload:
            for key in ("pre", "burn", "post"):
                value = regions_payload.get(key)
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise ValueError(f"Project region {key!r} must contain start/end")
                start, end = float(value[0]), float(value[1])
                if start >= end:
                    raise ValueError(f"Project region {key!r} is invalid")
                regions[key] = (start, end)

        processors_payload = payload.get("processors", [])
        if not isinstance(processors_payload, (list, tuple)):
            raise ValueError("Project processors must be an array")
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
            processors=tuple(
                PluginReference.from_dict(item) for item in processors_payload
            ),
            regions=regions,
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
