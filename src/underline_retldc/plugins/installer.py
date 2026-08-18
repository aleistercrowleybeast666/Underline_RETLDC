from __future__ import annotations

import errno
import os
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from underline_retldc.app.version import PLUGIN_API_VERSION
from underline_retldc.core.registry import PluginLoadResult, PluginRecord, PluginRegistry
from underline_retldc.plugin_api.common import PluginType, TaskContext
from underline_retldc.plugins.loader import PluginDiscoveryRoot, PluginLoader
from underline_retldc.plugins.manifest import Manifest_Load, PluginManifest

PLUGIN_TYPE_SUBDIRECTORY: Mapping[PluginType, str] = MappingProxyType(
    {
        PluginType.PARSER: "parsers",
        PluginType.CALIBRATION: "calibrations",
        PluginType.PROCESSOR: "processors",
        PluginType.ANALYZER: "analyzers",
        PluginType.EXPORTER: "exporters",
    }
)
# Backward-compatible public name used by earlier callers.
PLUGIN_CATEGORY_DIRECTORIES = PLUGIN_TYPE_SUBDIRECTORY
PLUGIN_ZIP_MAX_ENTRIES = 4096
PLUGIN_ZIP_MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_PLUGIN_ID_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?")
_PLUGIN_FOLDER_UNSAFE_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_PLUGIN_SCAN_EXCLUDED_NAMES = {".venv", ".git", "__pycache__"}


class PluginInstallStage(StrEnum):
    DISCOVERY = "discovery"
    MANIFEST_VALIDATION = "manifest_validation"
    CONFLICT_CHECK = "conflict_check"
    DESTINATION_RESOLUTION = "destination_resolution"
    EXTRACTION = "extraction"
    COPY = "copy"
    REGISTRY_REFRESH = "registry_refresh"
    LOAD_VERIFY = "load_verify"


class PluginInstallResult(StrEnum):
    APPLICATION = "application"
    USER_FALLBACK = "user_fallback"
    USER_EXISTING = "user_existing"


class PluginInstallRoot(StrEnum):
    APPLICATION = "application"
    USER = "user"


class PluginCandidateStatus(StrEnum):
    READY = "ready"
    EXISTING = "existing"
    EXISTING_MULTIPLE = "existing_multiple"
    NESTED_CONTAINER = "nested_container"
    SOURCE_DUPLICATE_ID = "source_duplicate_id"


class PluginInstallDecision(StrEnum):
    INSTALL = "install"
    REPLACE = "replace"
    SKIP = "skip"


class PluginInstallItemState(StrEnum):
    INSTALLED_AND_LOADED = "installed_and_loaded"
    INSTALLED_LOAD_FAILED = "installed_load_failed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class PluginExistingInstallation:
    path: Path
    manifest: PluginManifest
    result: PluginInstallResult
    root: Path


@dataclass(frozen=True, slots=True)
class PluginInstallIssue:
    source: Path
    stage: PluginInstallStage
    reason: str
    manifest_path: Path | None = None
    plugin_id: str | None = None
    plugin_type: PluginType | None = None
    target_path: Path | None = None
    existing_paths: tuple[Path, ...] = ()


class PluginInstallError(ValueError):
    def __init__(self, issue: PluginInstallIssue) -> None:
        self.issue = issue
        lines = [
            "Plugin installation failed",
            f"Source: {issue.source}",
            f"Stage: {issue.stage.value.upper()}",
        ]
        if issue.plugin_id:
            lines.append(f"Plugin ID: {issue.plugin_id}")
        if issue.plugin_type is not None:
            lines.append(f"Plugin type: {issue.plugin_type.value}")
        if issue.target_path is not None:
            lines.append(f"Target: {issue.target_path}")
        if issue.existing_paths:
            lines.append(
                "Existing plugin: " + ", ".join(str(path) for path in issue.existing_paths)
            )
        lines.append(f"Reason: {issue.reason}")
        super().__init__("\n".join(lines))


@dataclass(frozen=True, slots=True)
class PluginInstallCandidate:
    source_root: Path
    manifest_path: Path
    plugin_root: Path
    plugin_id: str
    plugin_type: PluginType
    version: str
    name: str
    api_version: str
    entry: str
    relative_path: str
    conflict_status: PluginCandidateStatus
    destination_category: str
    destination_preference: PluginInstallResult
    folder_name: str
    manifest: PluginManifest
    existing_plugins: tuple[PluginExistingInstallation, ...] = ()
    nested_descendants: tuple[str, ...] = ()

    @property
    def installable(self) -> bool:
        return self.conflict_status in {
            PluginCandidateStatus.READY,
            PluginCandidateStatus.EXISTING,
        }


@dataclass(slots=True)
class PluginInstallPackage:
    source: Path
    prepared_root: Path
    candidates: tuple[PluginInstallCandidate, ...]
    issues: tuple[PluginInstallIssue, ...]
    _temporary: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None


@dataclass(frozen=True, slots=True)
class PluginInstallOutcome:
    result: PluginInstallResult
    destination: Path
    manifest: PluginManifest
    replaced: bool = False

    @property
    def installed_root(self) -> PluginInstallRoot:
        if self.result is PluginInstallResult.APPLICATION:
            return PluginInstallRoot.APPLICATION
        return PluginInstallRoot.USER

    @property
    def installed_path(self) -> Path:
        return self.destination


@dataclass(frozen=True, slots=True)
class PluginInstallItemOutcome:
    candidate: PluginInstallCandidate
    state: PluginInstallItemState
    stage: PluginInstallStage
    message: str
    install_outcome: PluginInstallOutcome | None = None
    record: PluginRecord | None = None

    @property
    def loaded(self) -> bool:
        return self.state is PluginInstallItemState.INSTALLED_AND_LOADED


@dataclass(frozen=True, slots=True)
class PluginInstallBatchOutcome:
    items: tuple[PluginInstallItemOutcome, ...]
    registry: PluginRegistry

    @property
    def success_count(self) -> int:
        return sum(item.loaded for item in self.items)

    @property
    def failure_count(self) -> int:
        return sum(
            item.state
            in {
                PluginInstallItemState.FAILED,
                PluginInstallItemState.INSTALLED_LOAD_FAILED,
            }
            for item in self.items
        )

    @property
    def skipped_count(self) -> int:
        return sum(item.state is PluginInstallItemState.SKIPPED for item in self.items)


class PluginAlreadyExistsError(FileExistsError):
    def __init__(
        self,
        destination: Path,
        current_version: str,
        incoming_version: str,
        *,
        plugin_id: str = "",
        plugin_type: PluginType | None = None,
        name: str = "",
    ) -> None:
        super().__init__(f"Plugin destination already exists: {destination}")
        self.destination = destination
        self.current_version = current_version
        self.incoming_version = incoming_version
        self.plugin_id = plugin_id
        self.plugin_type = plugin_type
        self.name = name


class PluginDestinationResolutionError(ValueError):
    pass


def Plugin_UserDirectory() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "Underline_RETLDC" / "plugins"


def PluginRoot_IsWritable(root: Path) -> bool:
    root = Path(root).resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = Path(tempfile.mkdtemp(prefix=".underline-retldc-write-", dir=root))
        probe.rmdir()
    except OSError as exc:
        if PluginInstaller_IsAccessError(exc):
            return False
        raise
    return True


def PluginInstaller_IsAccessError(error: BaseException) -> bool:
    if isinstance(error, PermissionError):
        return True
    if not isinstance(error, OSError):
        return False
    return error.errno in {errno.EACCES, errno.EPERM, errno.EROFS} or getattr(
        error, "winerror", None
    ) in {5, 32}


def PluginPackage_Discover(
    source: Path,
    application_root: Path,
    user_root: Path,
    *,
    context: TaskContext | None = None,
    status_messages: Mapping[PluginInstallStage, str] | None = None,
) -> PluginInstallPackage:
    source = Path(source).resolve()
    application_root = Path(application_root).resolve()
    user_root = Path(user_root).resolve()
    temporary: tempfile.TemporaryDirectory[str] | None = None
    _PluginProgress_Report(
        context, 0.0, PluginInstallStage.DISCOVERY, status_messages
    )
    try:
        if source.is_dir():
            prepared_root = source
        elif source.is_file() and source.suffix.casefold() == ".zip":
            temporary = tempfile.TemporaryDirectory(prefix="underline-retldc-plugin-")
            prepared_root = Path(temporary.name).resolve()
            _PluginProgress_Report(
                context, 0.02, PluginInstallStage.EXTRACTION, status_messages
            )
            extraction_message = (
                status_messages.get(
                    PluginInstallStage.EXTRACTION,
                    PluginInstallStage.EXTRACTION.value,
                )
                if status_messages
                else PluginInstallStage.EXTRACTION.value
            )
            _PluginZip_ExtractSafe(
                source,
                prepared_root,
                context=context,
                progress_message=extraction_message,
            )
        else:
            raise PluginInstallError(
                PluginInstallIssue(
                    source,
                    PluginInstallStage.DISCOVERY,
                    "Select an existing plugin folder or ZIP package",
                )
            )

        manifest_paths = tuple(_PluginManifestPaths(prepared_root, context=context))
        if not manifest_paths:
            raise PluginInstallError(
                PluginInstallIssue(
                    source,
                    PluginInstallStage.DISCOVERY,
                    "No plugin.json was found recursively in the selected source",
                )
            )
        _PluginProgress_Report(
            context, 0.1, PluginInstallStage.MANIFEST_VALIDATION, status_messages
        )
        validated: list[tuple[Path, PluginManifest]] = []
        issues: list[PluginInstallIssue] = []
        for index, manifest_path in enumerate(manifest_paths):
            if context is not None:
                context.raise_if_cancelled()
            try:
                manifest = _PluginManifest_Validate(manifest_path)
            except (OSError, ValueError) as exc:
                issues.append(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.MANIFEST_VALIDATION,
                        str(exc),
                        manifest_path=manifest_path,
                    )
                )
            else:
                validated.append((manifest_path, manifest))
            _PluginProgress_Report(
                context,
                0.1 + 0.1 * (index + 1) / len(manifest_paths),
                PluginInstallStage.MANIFEST_VALIDATION,
                status_messages,
            )

        if not validated:
            raise PluginInstallError(issues[0])

        all_plugin_roots = tuple(path.parent for path in manifest_paths)
        valid_roots = {path.parent for path, _manifest in validated}
        nested_roots = {
            root
            for root in valid_roots
            if any(other != root and other.is_relative_to(root) for other in all_plugin_roots)
        }
        leaf_ids = Counter(
            manifest.plugin_id
            for manifest_path, manifest in validated
            if manifest_path.parent not in nested_roots
        )
        candidates: list[PluginInstallCandidate] = []
        for manifest_path, manifest in validated:
            plugin_root = manifest_path.parent
            relative = plugin_root.relative_to(prepared_root)
            relative_path = relative.as_posix() if relative.parts else "."
            descendants = tuple(
                sorted(
                    other.relative_to(prepared_root).as_posix()
                    for other in all_plugin_roots
                    if other != plugin_root and other.is_relative_to(plugin_root)
                )
            )
            existing = tuple(
                _PluginInstaller_ExistingFind(
                    manifest.plugin_id, application_root, user_root
                )
            )
            if plugin_root in nested_roots:
                status = PluginCandidateStatus.NESTED_CONTAINER
            elif leaf_ids[manifest.plugin_id] > 1:
                status = PluginCandidateStatus.SOURCE_DUPLICATE_ID
            elif len(existing) > 1:
                status = PluginCandidateStatus.EXISTING_MULTIPLE
            elif existing:
                status = PluginCandidateStatus.EXISTING
            else:
                status = PluginCandidateStatus.READY
            preference = (
                existing[0].result if len(existing) == 1 else PluginInstallResult.APPLICATION
            )
            folder_name = _PluginFolderName_Resolve(source, prepared_root, plugin_root, manifest)
            candidates.append(
                PluginInstallCandidate(
                    source_root=source,
                    manifest_path=manifest_path,
                    plugin_root=plugin_root,
                    plugin_id=manifest.plugin_id,
                    plugin_type=manifest.plugin_type,
                    version=manifest.version,
                    name=manifest.name,
                    api_version=manifest.api_version,
                    entry=manifest.entry,
                    relative_path=relative_path,
                    conflict_status=status,
                    destination_category=PLUGIN_TYPE_SUBDIRECTORY[manifest.plugin_type],
                    destination_preference=preference,
                    folder_name=folder_name,
                    manifest=manifest,
                    existing_plugins=existing,
                    nested_descendants=descendants,
                )
            )
        candidates.sort(key=lambda item: item.relative_path.casefold())
        _PluginProgress_Report(
            context, 1.0, PluginInstallStage.CONFLICT_CHECK, status_messages
        )
        return PluginInstallPackage(
            source,
            prepared_root,
            tuple(candidates),
            tuple(issues),
            temporary,
        )
    except BaseException:
        if temporary is not None:
            temporary.cleanup()
        raise


def PluginInstaller_InstallBatch(
    package: PluginInstallPackage,
    decisions: Mapping[str, PluginInstallDecision],
    application_root: Path,
    user_root: Path,
    *,
    context: TaskContext | None = None,
    status_messages: Mapping[PluginInstallStage, str] | None = None,
) -> PluginInstallBatchOutcome:
    application_root = Path(application_root).resolve()
    user_root = Path(user_root).resolve()
    installable = tuple(
        candidate
        for candidate in package.candidates
        if decisions.get(candidate.relative_path, PluginInstallDecision.SKIP)
        is not PluginInstallDecision.SKIP
    )
    items: list[PluginInstallItemOutcome] = []
    completed = 0
    total = max(1, len(installable))
    _PluginProgress_Report(
        context, 0.0, PluginInstallStage.MANIFEST_VALIDATION, status_messages
    )
    _PluginProgress_Report(
        context, 0.08, PluginInstallStage.CONFLICT_CHECK, status_messages
    )
    _PluginProgress_Report(
        context, 0.15, PluginInstallStage.DESTINATION_RESOLUTION, status_messages
    )
    for candidate in package.candidates:
        decision = decisions.get(candidate.relative_path, PluginInstallDecision.SKIP)
        if decision is PluginInstallDecision.SKIP:
            if candidate.conflict_status in {
                PluginCandidateStatus.EXISTING_MULTIPLE,
                PluginCandidateStatus.SOURCE_DUPLICATE_ID,
            }:
                state = PluginInstallItemState.FAILED
                message = (
                    "The Plugin ID conflicts with another candidate or existing copy"
                )
            else:
                state = PluginInstallItemState.SKIPPED
                message = "Skipped by user"
            items.append(
                PluginInstallItemOutcome(
                    candidate,
                    state,
                    PluginInstallStage.CONFLICT_CHECK,
                    message,
                )
            )
            continue
        if context is not None:
            context.raise_if_cancelled()
        progress_start = 0.2 + 0.58 * completed / total
        _PluginProgress_Report(
            context,
            progress_start,
            PluginInstallStage.COPY,
            status_messages,
            current=completed + 1,
            total=len(installable),
            name=candidate.name,
        )
        try:
            outcome = _PluginInstaller_InstallCandidate(
                candidate,
                decision,
                application_root,
                user_root,
            )
        except PluginInstallError as exc:
            items.append(
                PluginInstallItemOutcome(
                    candidate,
                    PluginInstallItemState.FAILED,
                    exc.issue.stage,
                    exc.issue.reason,
                )
            )
        except (OSError, ValueError) as exc:
            items.append(
                PluginInstallItemOutcome(
                    candidate,
                    PluginInstallItemState.FAILED,
                    PluginInstallStage.COPY,
                    str(exc),
                )
            )
        else:
            items.append(
                PluginInstallItemOutcome(
                    candidate,
                    PluginInstallItemState.INSTALLED_LOAD_FAILED,
                    PluginInstallStage.LOAD_VERIFY,
                    "Plugin files were installed; registry verification is pending",
                    install_outcome=outcome,
                )
            )
        completed += 1
        _PluginProgress_Report(
            context,
            0.2 + 0.58 * completed / total,
            PluginInstallStage.COPY,
            status_messages,
            current=completed,
            total=len(installable),
            name=candidate.name,
        )

    if context is not None:
        context.raise_if_cancelled()
    _PluginProgress_Report(
        context, 0.82, PluginInstallStage.REGISTRY_REFRESH, status_messages
    )
    registry = PluginRegistry()
    PluginLoader(registry).discover(
        (
            PluginDiscoveryRoot(application_root, "application"),
            PluginDiscoveryRoot(user_root, "user"),
        )
    )
    _PluginProgress_Report(
        context, 0.92, PluginInstallStage.LOAD_VERIFY, status_messages
    )
    verified_items: list[PluginInstallItemOutcome] = []
    for item in items:
        outcome = item.install_outcome
        if outcome is None:
            verified_items.append(item)
            continue
        record = _PluginRecord_InstalledFind(
            registry.records,
            item.candidate.plugin_id,
            outcome.destination,
        )
        if record is not None and record.result is PluginLoadResult.LOADED:
            verified_items.append(
                replace(
                    item,
                    state=PluginInstallItemState.INSTALLED_AND_LOADED,
                    message="Installed and loaded",
                    record=record,
                )
            )
            continue
        if record is None:
            message = "The installed plugin was not found during registry refresh"
        else:
            diagnostic_text = " | ".join(
                diagnostic.message for diagnostic in record.diagnostics
            )
            message = diagnostic_text or f"Registry result: {record.result.value}"
        verified_items.append(replace(item, message=message, record=record))
    _PluginProgress_Report(
        context, 1.0, PluginInstallStage.LOAD_VERIFY, status_messages
    )
    return PluginInstallBatchOutcome(tuple(verified_items), registry)


def PluginInstaller_Install(
    source: Path,
    application_root: Path,
    user_root: Path,
    *,
    replace: bool = False,
) -> PluginInstallOutcome:
    package = PluginPackage_Discover(source, application_root, user_root)
    try:
        candidates = tuple(
            candidate
            for candidate in package.candidates
            if candidate.conflict_status is not PluginCandidateStatus.NESTED_CONTAINER
        )
        if not candidates and package.issues:
            raise PluginInstallError(package.issues[0])
        if len(candidates) != 1:
            raise PluginInstallError(
                PluginInstallIssue(
                    Path(source).resolve(),
                    PluginInstallStage.DISCOVERY,
                    "The single-plugin compatibility API requires exactly one plugin candidate",
                )
            )
        candidate = candidates[0]
        if candidate.conflict_status is PluginCandidateStatus.SOURCE_DUPLICATE_ID:
            raise _PluginCandidate_Error(
                candidate,
                PluginInstallStage.CONFLICT_CHECK,
                f"Plugin ID {candidate.plugin_id!r} appears more than once in the source",
            )
        if candidate.existing_plugins and not replace:
            existing = candidate.existing_plugins[0]
            raise PluginAlreadyExistsError(
                existing.path,
                existing.manifest.version,
                candidate.version,
                plugin_id=candidate.plugin_id,
                plugin_type=candidate.plugin_type,
                name=candidate.name,
            )
        decision = (
            PluginInstallDecision.REPLACE
            if candidate.existing_plugins
            else PluginInstallDecision.INSTALL
        )
        return _PluginInstaller_InstallCandidate(
            candidate,
            decision,
            Path(application_root).resolve(),
            Path(user_root).resolve(),
        )
    finally:
        package.close()


def PluginInstaller_InstallDirectory(
    source: Path,
    destination_root: Path,
    *,
    replace: bool = False,
) -> Path:
    source = Path(source).resolve()
    if not source.is_dir():
        raise ValueError(f"Plugin source directory does not exist: {source}")
    manifest = _PluginManifest_Validate(source / "plugin.json")
    return _PluginInstaller_InstallPrepared(
        source,
        manifest,
        Path(destination_root).resolve(),
        replace=replace,
        folder_name=_PluginFolderName_Sanitize(source.name, manifest.plugin_id),
    )


def _PluginInstaller_InstallCandidate(
    candidate: PluginInstallCandidate,
    decision: PluginInstallDecision,
    application_root: Path,
    user_root: Path,
) -> PluginInstallOutcome:
    if candidate.conflict_status is PluginCandidateStatus.NESTED_CONTAINER:
        raise _PluginCandidate_Error(
            candidate,
            PluginInstallStage.CONFLICT_CHECK,
            "This candidate contains a nested plugin and is not copied as a plugin root",
        )
    if candidate.conflict_status is PluginCandidateStatus.SOURCE_DUPLICATE_ID:
        raise _PluginCandidate_Error(
            candidate,
            PluginInstallStage.CONFLICT_CHECK,
            f"Plugin ID {candidate.plugin_id!r} appears more than once in this source",
        )
    if len(candidate.existing_plugins) > 1:
        raise _PluginCandidate_Error(
            candidate,
            PluginInstallStage.CONFLICT_CHECK,
            "The same Plugin ID already exists in multiple configured plugin roots",
            existing_paths=tuple(item.path for item in candidate.existing_plugins),
        )
    if candidate.existing_plugins:
        existing = candidate.existing_plugins[0]
        if decision is not PluginInstallDecision.REPLACE:
            raise _PluginCandidate_Error(
                candidate,
                PluginInstallStage.CONFLICT_CHECK,
                "The plugin already exists; choose Replace or Skip",
                target_path=existing.path,
                existing_paths=(existing.path,),
            )
        try:
            installed = _PluginInstaller_InstallPrepared(
                candidate.plugin_root,
                candidate.manifest,
                existing.root,
                replace=True,
                destination_override=existing.path,
                folder_name=candidate.folder_name,
            )
        except PluginDestinationResolutionError as exc:
            raise _PluginCandidate_Error(
                candidate,
                PluginInstallStage.DESTINATION_RESOLUTION,
                str(exc),
                target_path=existing.path,
                existing_paths=(existing.path,),
            ) from exc
        except (OSError, ValueError) as exc:
            raise _PluginCandidate_Error(
                candidate,
                PluginInstallStage.COPY,
                str(exc),
                target_path=existing.path,
                existing_paths=(existing.path,),
            ) from exc
        return PluginInstallOutcome(
            existing.result,
            installed,
            candidate.manifest,
            replaced=True,
        )

    application_category = (
        application_root / PLUGIN_TYPE_SUBDIRECTORY[candidate.plugin_type]
    )
    try:
        application_writable = PluginRoot_IsWritable(application_category)
    except OSError as exc:
        raise _PluginCandidate_Error(
            candidate,
            PluginInstallStage.DESTINATION_RESOLUTION,
            str(exc),
            target_path=application_category,
        ) from exc
    if application_writable:
        try:
            destination = _PluginInstaller_InstallPrepared(
                candidate.plugin_root,
                candidate.manifest,
                application_root,
                replace=False,
                folder_name=candidate.folder_name,
            )
        except PluginDestinationResolutionError as exc:
            raise _PluginCandidate_Error(
                candidate,
                PluginInstallStage.DESTINATION_RESOLUTION,
                str(exc),
                target_path=application_category,
            ) from exc
        except OSError as exc:
            if not PluginInstaller_IsAccessError(exc):
                raise _PluginCandidate_Error(
                    candidate,
                    PluginInstallStage.COPY,
                    str(exc),
                    target_path=application_category,
                ) from exc
        except ValueError as exc:
            raise _PluginCandidate_Error(
                candidate,
                PluginInstallStage.COPY,
                str(exc),
                target_path=application_category,
            ) from exc
        else:
            return PluginInstallOutcome(
                PluginInstallResult.APPLICATION,
                destination,
                candidate.manifest,
            )

    user_category = user_root / PLUGIN_TYPE_SUBDIRECTORY[candidate.plugin_type]
    try:
        destination = _PluginInstaller_InstallPrepared(
            candidate.plugin_root,
            candidate.manifest,
            user_root,
            replace=False,
            folder_name=candidate.folder_name,
        )
    except PluginDestinationResolutionError as exc:
        raise _PluginCandidate_Error(
            candidate,
            PluginInstallStage.DESTINATION_RESOLUTION,
            str(exc),
            target_path=user_category,
        ) from exc
    except (OSError, ValueError) as exc:
        raise _PluginCandidate_Error(
            candidate,
            PluginInstallStage.COPY,
            str(exc),
            target_path=user_category,
        ) from exc
    return PluginInstallOutcome(
        PluginInstallResult.USER_FALLBACK,
        destination,
        candidate.manifest,
    )


def _PluginManifest_Validate(source: Path) -> PluginManifest:
    manifest = Manifest_Load(source)
    if manifest.api_version != PLUGIN_API_VERSION:
        raise ValueError(
            f"Plugin API {manifest.api_version} is unsupported; expected {PLUGIN_API_VERSION}"
        )
    if (
        _PLUGIN_ID_PATTERN.fullmatch(manifest.plugin_id) is None
        or ".." in manifest.plugin_id
    ):
        raise ValueError(
            "Plugin ID may contain only letters, digits, dots, underscores, and hyphens"
        )
    module_name, class_name = manifest.entry.split(":", maxsplit=1)
    if not class_name.isidentifier() or not module_name:
        raise ValueError("Plugin entry must identify a valid module and class")
    module_parts = module_name.split(".")
    if any(not part.isidentifier() for part in module_parts):
        raise ValueError("Plugin entry module path is invalid")
    plugin_root = Path(source).parent
    module_file = plugin_root.joinpath(*module_parts).with_suffix(".py")
    package_file = plugin_root.joinpath(*module_parts, "__init__.py")
    if not module_file.is_file() and not package_file.is_file():
        raise ValueError(f"Plugin entry module does not exist: {module_name}")
    return manifest


def _PluginCandidate_Error(
    candidate: PluginInstallCandidate,
    stage: PluginInstallStage,
    reason: str,
    *,
    target_path: Path | None = None,
    existing_paths: tuple[Path, ...] = (),
) -> PluginInstallError:
    return PluginInstallError(
        PluginInstallIssue(
            candidate.source_root,
            stage,
            reason,
            manifest_path=candidate.manifest_path,
            plugin_id=candidate.plugin_id,
            plugin_type=candidate.plugin_type,
            target_path=target_path,
            existing_paths=existing_paths,
        )
    )


def _PluginProgress_Report(
    context: TaskContext | None,
    progress: float,
    stage: PluginInstallStage,
    status_messages: Mapping[PluginInstallStage, str] | None,
    **values: object,
) -> None:
    if context is None:
        return
    context.raise_if_cancelled()
    template = status_messages.get(stage, stage.value) if status_messages else stage.value
    try:
        message = template.format(**values)
    except (KeyError, ValueError):
        message = template
    context.report_progress(progress, message)


def _PluginRecord_InstalledFind(
    records: tuple[PluginRecord, ...],
    plugin_id: str,
    destination: Path,
) -> PluginRecord | None:
    destination = destination.resolve()
    for record in records:
        if record.plugin_id != plugin_id:
            continue
        try:
            source = Path(record.source).resolve()
        except OSError:
            continue
        if source == destination:
            return record
    return None


def _PluginFolderName_Resolve(
    source: Path,
    prepared_root: Path,
    plugin_root: Path,
    manifest: PluginManifest,
) -> str:
    relative = plugin_root.relative_to(prepared_root)
    if relative.parts:
        preferred = plugin_root.name
    elif source.is_dir():
        preferred = source.name
    else:
        preferred = source.stem
    return _PluginFolderName_Sanitize(preferred, manifest.plugin_id)


def _PluginFolderName_Sanitize(preferred: str, plugin_id: str) -> str:
    cleaned = _PLUGIN_FOLDER_UNSAFE_PATTERN.sub("_", preferred).strip(" .")
    if cleaned and cleaned not in {".", ".."}:
        return cleaned
    fallback = _PLUGIN_FOLDER_UNSAFE_PATTERN.sub("_", plugin_id).strip(" .")
    return f"plugin-{fallback or 'unnamed'}"


def _PluginInstaller_ExistingFind(
    plugin_id: str,
    application_root: Path,
    user_root: Path,
) -> list[PluginExistingInstallation]:
    matches: list[PluginExistingInstallation] = []
    for root, application_result in (
        (application_root, PluginInstallResult.APPLICATION),
        (user_root, PluginInstallResult.USER_EXISTING),
    ):
        if not root.is_dir():
            continue
        for manifest_path in _PluginManifestPaths(root):
            try:
                manifest = Manifest_Load(manifest_path)
            except ValueError:
                continue
            if manifest.plugin_id == plugin_id:
                matches.append(
                    PluginExistingInstallation(
                        manifest_path.parent.resolve(),
                        manifest,
                        application_result,
                        root.resolve(),
                    )
                )
    return matches


def _PluginManifestPaths(
    root: Path,
    *,
    context: TaskContext | None = None,
) -> Iterator[Path]:
    def error_raise(error: OSError) -> None:
        raise error

    for directory, child_directories, filenames in os.walk(
        root, followlinks=False, onerror=error_raise
    ):
        if context is not None:
            context.raise_if_cancelled()
        current = Path(directory)
        child_directories[:] = sorted(
            name
            for name in child_directories
            if name not in _PLUGIN_SCAN_EXCLUDED_NAMES
            and not name.startswith(".underline-retldc-")
            and not (current / name).is_symlink()
        )
        if "plugin.json" in filenames:
            manifest_path = current / "plugin.json"
            if manifest_path.is_symlink():
                continue
            yield manifest_path.resolve()


def _PluginInstaller_InstallPrepared(
    source: Path,
    manifest: PluginManifest,
    destination_root: Path,
    *,
    replace: bool,
    destination_override: Path | None = None,
    folder_name: str | None = None,
) -> Path:
    destination_root.mkdir(parents=True, exist_ok=True)
    if destination_override is None:
        category_directory = (
            destination_root / PLUGIN_TYPE_SUBDIRECTORY[manifest.plugin_type]
        )
        safe_name = _PluginFolderName_Sanitize(
            folder_name or source.name,
            manifest.plugin_id,
        )
        destination = _PluginDestination_Resolve(
            category_directory,
            safe_name,
            manifest.plugin_id,
        )
    else:
        destination = Path(destination_override).resolve()
        if not destination.is_relative_to(destination_root):
            raise PluginDestinationResolutionError(
                "Existing plugin destination is outside its configured root"
            )
        category_directory = destination.parent
        safe_name = destination.name
    category_directory.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace:
        current_manifest = Manifest_Load(destination / "plugin.json")
        raise PluginAlreadyExistsError(
            destination,
            current_manifest.version,
            manifest.version,
            plugin_id=manifest.plugin_id,
            plugin_type=manifest.plugin_type,
            name=manifest.name,
        )

    unique_suffix = uuid.uuid4().hex
    staging = category_directory / (
        f".underline-retldc-staging-{safe_name}-{unique_suffix}"
    )
    backup = category_directory / (
        f".underline-retldc-backup-{safe_name}-{unique_suffix}"
    )
    try:
        _PluginDirectory_Copy(source, staging)
        staged_manifest = _PluginManifest_Validate(staging / "plugin.json")
        if staged_manifest != manifest:
            raise ValueError("Copied plugin manifest changed during installation")
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except BaseException:
            if backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        if backup.exists():
            _PluginDirectory_Remove(backup, suppress_errors=True)
    except BaseException:
        if staging.exists():
            _PluginDirectory_Remove(staging, suppress_errors=True)
        raise
    return destination.resolve()


def _PluginDestination_Resolve(
    category_directory: Path,
    preferred_name: str,
    plugin_id: str,
) -> Path:
    preferred = category_directory / preferred_name
    if not preferred.exists():
        return preferred
    preferred_manifest = preferred / "plugin.json"
    if preferred_manifest.is_file():
        try:
            existing_manifest = Manifest_Load(preferred_manifest)
        except ValueError:
            existing_manifest = None
        if existing_manifest is not None and existing_manifest.plugin_id == plugin_id:
            return preferred
    identity_name = _PluginFolderName_Sanitize(f"plugin-{plugin_id}", plugin_id)
    identity_destination = category_directory / identity_name
    if not identity_destination.exists():
        return identity_destination
    raise PluginDestinationResolutionError(
        "Both the preferred plugin folder and the Plugin-ID fallback folder already exist"
    )


def _PluginDirectory_Copy(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"Plugin staging directory already exists: {destination}")
    destination.mkdir(parents=False)
    def error_raise(error: OSError) -> None:
        raise error

    for directory, child_directories, filenames in os.walk(
        source,
        followlinks=False,
        onerror=error_raise,
    ):
        current = Path(directory)
        relative = current.relative_to(source)
        target_directory = destination / relative
        target_directory.mkdir(parents=True, exist_ok=True)
        for name in child_directories:
            if (current / name).is_symlink():
                raise ValueError("Plugin folders must not contain symbolic links")
        for name in filenames:
            source_file = current / name
            if source_file.is_symlink():
                raise ValueError("Plugin folders must not contain symbolic links")
            shutil.copy2(source_file, target_directory / name)


def _PluginDirectory_Remove(directory: Path, *, suppress_errors: bool = False) -> None:
    def permission_retry(function: object, path: str, _error: object) -> None:
        Path(path).chmod(stat.S_IWRITE)
        function(path)  # type: ignore[operator]

    try:
        shutil.rmtree(directory, onerror=permission_retry)
    except OSError:
        if not suppress_errors:
            raise


def _PluginZip_ExtractSafe(
    source: Path,
    destination: Path,
    *,
    context: TaskContext | None = None,
    progress_message: str = "",
) -> None:
    try:
        archive = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as exc:
        raise PluginInstallError(
            PluginInstallIssue(
                source,
                PluginInstallStage.EXTRACTION,
                f"Unable to open plugin ZIP: {exc}",
            )
        ) from exc
    with archive:
        members = archive.infolist()
        if len(members) > PLUGIN_ZIP_MAX_ENTRIES:
            raise PluginInstallError(
                PluginInstallIssue(
                    source,
                    PluginInstallStage.EXTRACTION,
                    f"Plugin ZIP contains more than {PLUGIN_ZIP_MAX_ENTRIES} entries",
                )
            )
        total_size = sum(item.file_size for item in members)
        if total_size > PLUGIN_ZIP_MAX_UNCOMPRESSED_BYTES:
            raise PluginInstallError(
                PluginInstallIssue(
                    source,
                    PluginInstallStage.EXTRACTION,
                    "Plugin ZIP is too large after extraction",
                )
            )
        seen_paths: set[str] = set()
        extracted_size = 0
        for member in members:
            if context is not None:
                context.raise_if_cancelled()
            raw_name = member.filename.replace("\\", "/")
            relative = PurePosixPath(raw_name)
            if (
                not raw_name
                or raw_name.startswith("/")
                or relative.is_absolute()
                or ".." in relative.parts
                or any(":" in part for part in relative.parts)
            ):
                raise PluginInstallError(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.EXTRACTION,
                        f"Unsafe path in plugin ZIP: {member.filename}",
                    )
                )
            if member.flag_bits & 0x1:
                raise PluginInstallError(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.EXTRACTION,
                        "Encrypted plugin ZIP entries are not supported",
                    )
                )
            file_type = (member.external_attr >> 16) & 0o170000
            if file_type == stat.S_IFLNK:
                raise PluginInstallError(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.EXTRACTION,
                        "Plugin ZIP must not contain symbolic links",
                    )
                )
            if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise PluginInstallError(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.EXTRACTION,
                        f"Unsupported special entry in plugin ZIP: {member.filename}",
                    )
                )
            normalized_key = "/".join(relative.parts).casefold()
            if normalized_key in seen_paths and not member.is_dir():
                raise PluginInstallError(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.EXTRACTION,
                        f"Duplicate path in plugin ZIP: {member.filename}",
                    )
                )
            seen_paths.add(normalized_key)
            target = destination.joinpath(*relative.parts)
            try:
                resolved_target = target.resolve()
            except OSError as exc:
                raise PluginInstallError(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.EXTRACTION,
                        f"Unable to resolve ZIP entry {member.filename}: {exc}",
                    )
                ) from exc
            if not resolved_target.is_relative_to(destination):
                raise PluginInstallError(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.EXTRACTION,
                        f"Unsafe path in plugin ZIP: {member.filename}",
                    )
                )
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with archive.open(member) as input_file, target.open("wb") as output_file:
                    shutil.copyfileobj(input_file, output_file)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PluginInstallError(
                    PluginInstallIssue(
                        source,
                        PluginInstallStage.EXTRACTION,
                        f"Unable to extract ZIP entry {member.filename}: {exc}",
                    )
                ) from exc
            extracted_size += member.file_size
            if context is not None and total_size:
                context.report_progress(
                    min(0.09, 0.02 + 0.07 * extracted_size / total_size),
                    progress_message,
                )
