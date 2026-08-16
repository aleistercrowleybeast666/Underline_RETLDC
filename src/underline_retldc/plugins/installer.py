from __future__ import annotations

import errno
import os
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from underline_retldc.app.version import PLUGIN_API_VERSION
from underline_retldc.plugin_api.common import PluginType
from underline_retldc.plugins.manifest import Manifest_Load, PluginManifest

PLUGIN_CATEGORY_DIRECTORIES = {
    PluginType.PARSER: "parsers",
    PluginType.CALIBRATION: "calibrations",
    PluginType.PROCESSOR: "processors",
    PluginType.ANALYZER: "analyzers",
    PluginType.EXPORTER: "exporters",
}
PLUGIN_ZIP_MAX_ENTRIES = 4096
PLUGIN_ZIP_MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_PLUGIN_ID_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?")


class PluginInstallResult(StrEnum):
    APPLICATION = "application"
    USER_FALLBACK = "user_fallback"
    USER_EXISTING = "user_existing"


@dataclass(frozen=True, slots=True)
class PluginInstallOutcome:
    result: PluginInstallResult
    destination: Path
    manifest: PluginManifest
    replaced: bool = False


class PluginAlreadyExistsError(FileExistsError):
    def __init__(
        self,
        destination: Path,
        current_version: str,
        incoming_version: str,
    ) -> None:
        super().__init__(f"Plugin destination already exists: {destination}")
        self.destination = destination
        self.current_version = current_version
        self.incoming_version = incoming_version


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


def PluginInstaller_Install(
    source: Path,
    application_root: Path,
    user_root: Path,
    *,
    replace: bool = False,
) -> PluginInstallOutcome:
    application_root = Path(application_root).resolve()
    user_root = Path(user_root).resolve()
    with _PluginPackage_Prepare(Path(source)) as source_directory:
        manifest = _PluginManifest_Validate(source_directory / "plugin.json")
        existing = _PluginInstaller_ExistingFind(
            manifest.plugin_id, application_root, user_root
        )
        if len(existing) > 1:
            locations = ", ".join(str(item[0]) for item in existing)
            raise FileExistsError(
                f"Plugin ID {manifest.plugin_id!r} exists in multiple roots: {locations}"
            )
        if existing:
            destination, current_manifest, existing_result, existing_root = existing[0]
            if not replace:
                raise PluginAlreadyExistsError(
                    destination,
                    current_manifest.version,
                    manifest.version,
                )
            installed = _PluginInstaller_InstallPrepared(
                source_directory,
                manifest,
                existing_root,
                replace=True,
                destination_override=destination,
            )
            return PluginInstallOutcome(
                result=existing_result,
                destination=installed,
                manifest=manifest,
                replaced=True,
            )

        if PluginRoot_IsWritable(application_root):
            try:
                destination = _PluginInstaller_InstallPrepared(
                    source_directory,
                    manifest,
                    application_root,
                    replace=False,
                )
            except OSError as exc:
                if not PluginInstaller_IsAccessError(exc):
                    raise
            else:
                return PluginInstallOutcome(
                    PluginInstallResult.APPLICATION,
                    destination,
                    manifest,
                )

        destination = _PluginInstaller_InstallPrepared(
            source_directory,
            manifest,
            user_root,
            replace=False,
        )
        return PluginInstallOutcome(
            PluginInstallResult.USER_FALLBACK,
            destination,
            manifest,
        )


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
    return manifest


@contextmanager
def _PluginPackage_Prepare(source: Path) -> Iterator[Path]:
    source = source.resolve()
    if source.is_dir():
        if not (source / "plugin.json").is_file():
            raise ValueError("The selected folder does not contain plugin.json")
        yield source
        return
    if not source.is_file() or source.suffix.casefold() != ".zip":
        raise ValueError("Select a plugin folder or ZIP package")
    with tempfile.TemporaryDirectory(prefix="underline-retldc-plugin-") as temporary:
        extraction_root = Path(temporary).resolve()
        _PluginZip_ExtractSafe(source, extraction_root)
        manifests = sorted(extraction_root.rglob("plugin.json"))
        if len(manifests) != 1:
            raise ValueError("Plugin ZIP must contain exactly one plugin.json")
        plugin_directory = manifests[0].parent
        if plugin_directory.parent != extraction_root:
            raise ValueError(
                "Plugin ZIP must contain one top-level plugin folder with plugin.json"
            )
        yield plugin_directory


def _PluginZip_ExtractSafe(source: Path, destination: Path) -> None:
    try:
        archive = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Unable to open plugin ZIP {source}: {exc}") from exc
    with archive:
        members = archive.infolist()
        if len(members) > PLUGIN_ZIP_MAX_ENTRIES:
            raise ValueError("Plugin ZIP contains too many entries")
        if sum(item.file_size for item in members) > PLUGIN_ZIP_MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Plugin ZIP is too large after extraction")
        seen_paths: set[str] = set()
        top_level_names: set[str] = set()
        for member in members:
            raw_name = member.filename.replace("\\", "/")
            relative = PurePosixPath(raw_name)
            if (
                not raw_name
                or raw_name.startswith("/")
                or relative.is_absolute()
                or ".." in relative.parts
                or any(":" in part for part in relative.parts)
            ):
                raise ValueError(f"Unsafe path in plugin ZIP: {member.filename}")
            if member.flag_bits & 0x1:
                raise ValueError("Encrypted plugin ZIP entries are not supported")
            file_type = (member.external_attr >> 16) & 0o170000
            if file_type == stat.S_IFLNK:
                raise ValueError("Plugin ZIP must not contain symbolic links")
            normalized_key = "/".join(relative.parts).casefold()
            if normalized_key in seen_paths and not member.is_dir():
                raise ValueError(f"Duplicate path in plugin ZIP: {member.filename}")
            seen_paths.add(normalized_key)
            if relative.parts:
                top_level_names.add(relative.parts[0].casefold())
            target = destination.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(destination):
                raise ValueError(f"Unsafe path in plugin ZIP: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with archive.open(member) as input_file, target.open("wb") as output_file:
                    shutil.copyfileobj(input_file, output_file)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise ValueError(
                    f"Unable to extract plugin ZIP entry {member.filename}: {exc}"
                ) from exc
        if len(top_level_names) != 1:
            raise ValueError("Plugin ZIP must contain exactly one top-level plugin folder")


def _PluginInstaller_ExistingFind(
    plugin_id: str,
    application_root: Path,
    user_root: Path,
) -> list[tuple[Path, PluginManifest, PluginInstallResult, Path]]:
    matches: list[tuple[Path, PluginManifest, PluginInstallResult, Path]] = []
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
                    (manifest_path.parent, manifest, application_result, root)
                )
    return matches


def _PluginManifestPaths(root: Path) -> Iterator[Path]:
    excluded_names = {".venv", ".git", "__pycache__"}
    for directory, child_directories, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        child_directories[:] = sorted(
            name
            for name in child_directories
            if name not in excluded_names
            and not name.startswith(".underline-retldc-")
            and not (current / name).is_symlink()
        )
        if "plugin.json" in filenames:
            yield current / "plugin.json"


def _PluginInstaller_InstallPrepared(
    source: Path,
    manifest: PluginManifest,
    destination_root: Path,
    *,
    replace: bool,
    destination_override: Path | None = None,
) -> Path:
    destination_root.mkdir(parents=True, exist_ok=True)
    if destination_override is None:
        category_directory = (
            destination_root / PLUGIN_CATEGORY_DIRECTORIES[manifest.plugin_type]
        )
        safe_name = f"plugin-{manifest.plugin_id}"
        destination = category_directory / safe_name
    else:
        destination = Path(destination_override).resolve()
        if not destination.is_relative_to(destination_root):
            raise ValueError("Existing plugin destination is outside its configured root")
        category_directory = destination.parent
        safe_name = destination.name
    category_directory.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace:
        current_manifest = Manifest_Load(destination / "plugin.json")
        raise PluginAlreadyExistsError(
            destination,
            current_manifest.version,
            manifest.version,
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
            _PluginDirectory_Remove(backup)
    except BaseException:
        if staging.exists():
            _PluginDirectory_Remove(staging, suppress_errors=True)
        raise
    return destination.resolve()


def _PluginDirectory_Copy(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"Plugin staging directory already exists: {destination}")
    destination.mkdir(parents=False)
    for directory, child_directories, filenames in os.walk(source, followlinks=False):
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
