from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from underline_retldc.app.version import PLUGIN_API_VERSION
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.registry import PluginLoadResult, PluginRecord, PluginRegistry
from underline_retldc.plugin_api.analyzer import AnalyzerPlugin
from underline_retldc.plugin_api.calibration import CalibrationModelPlugin
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType
from underline_retldc.plugin_api.exporter import ExporterPlugin
from underline_retldc.plugin_api.parser import ParserPlugin
from underline_retldc.plugin_api.processor import ProcessorPlugin
from underline_retldc.plugins.manifest import Manifest_Load, PluginManifest


@dataclass(frozen=True, slots=True)
class PluginDiscoveryRoot:
    path: Path
    source_kind: str


class PluginLoader:
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    def discover(
        self,
        roots: list[Path | PluginDiscoveryRoot]
        | tuple[Path | PluginDiscoveryRoot, ...],
    ) -> tuple[PluginRecord, ...]:
        records: list[PluginRecord] = []
        discovered_directories: set[Path] = set()
        for configured_root in roots:
            if isinstance(configured_root, PluginDiscoveryRoot):
                root = Path(configured_root.path)
                source_kind = configured_root.source_kind
            else:
                root = Path(configured_root)
                source_kind = "unknown"
            if not root.exists():
                continue
            try:
                plugin_directories = self._plugin_directories(root)
            except OSError as exc:
                records.append(
                    self._failure(
                        PluginLoadResult.MANIFEST_ERROR,
                        root,
                        "plugin.discovery_error",
                        f"Unable to inspect plugin directory: {exc}",
                        source_kind=source_kind,
                    )
                )
                continue
            for plugin_directory in plugin_directories:
                resolved = plugin_directory.resolve()
                if resolved in discovered_directories:
                    continue
                discovered_directories.add(resolved)
                records.append(self.load(plugin_directory, source_kind=source_kind))
        return tuple(records)

    @staticmethod
    def _plugin_directories(root: Path) -> list[Path]:
        discovered: list[Path] = []
        excluded_names = {".venv", "__pycache__", ".git"}

        def error_raise(error: OSError) -> None:
            raise error

        for directory, child_directories, filenames in os.walk(
            root, followlinks=False, onerror=error_raise
        ):
            current = Path(directory)
            child_directories[:] = sorted(
                name
                for name in child_directories
                if name not in excluded_names
                and not name.startswith(".underline-retldc-")
                and not (current / name).is_symlink()
            )
            if "plugin.json" in filenames:
                discovered.append(current)
        return sorted(discovered, key=lambda item: str(item).casefold())

    def load(
        self, plugin_directory: Path, *, source_kind: str = "unknown"
    ) -> PluginRecord:
        plugin_directory = Path(plugin_directory).resolve()
        manifest_path = plugin_directory / "plugin.json"
        try:
            manifest = Manifest_Load(manifest_path)
        except (ValueError, OSError) as exc:
            return self._failure(
                PluginLoadResult.MANIFEST_ERROR,
                plugin_directory,
                "plugin.manifest_error",
                str(exc),
                source_kind=source_kind,
            )

        source_kind = self._source_kind_resolve(source_kind, manifest)

        if manifest.api_version != PLUGIN_API_VERSION:
            return self._failure(
                PluginLoadResult.API_MISMATCH,
                plugin_directory,
                "plugin.api_mismatch",
                f"Plugin API {manifest.api_version} is unsupported; expected {PLUGIN_API_VERSION}",
                manifest,
                source_kind,
            )
        try:
            self._registry.get(manifest.plugin_id)
        except KeyError:
            pass
        else:
            return self._failure(
                PluginLoadResult.DUPLICATE_ID,
                plugin_directory,
                "plugin.duplicate_id",
                f"Plugin ID {manifest.plugin_id!r} is already loaded",
                manifest,
                source_kind,
            )

        module_name, class_name = manifest.entry.split(":", maxsplit=1)
        module_file = plugin_directory.joinpath(*module_name.split(".")).with_suffix(".py")
        package_file = plugin_directory.joinpath(*module_name.split("."), "__init__.py")
        source_file = module_file if module_file.is_file() else package_file
        if not source_file.is_file():
            return self._failure(
                PluginLoadResult.IMPORT_ERROR,
                plugin_directory,
                "plugin.entry_missing",
                f"Entry module does not exist: {module_name}",
                manifest,
                source_kind,
            )

        unique_name = "_underline_retldc_plugin_" + hashlib.sha256(
            str(plugin_directory).encode("utf-8")
        ).hexdigest()[:16]
        try:
            specification = importlib.util.spec_from_file_location(
                unique_name,
                source_file,
                submodule_search_locations=[str(plugin_directory)],
            )
            if specification is None or specification.loader is None:
                raise ImportError(f"Cannot create import specification for {source_file}")
            module = importlib.util.module_from_spec(specification)
            sys.modules[unique_name] = module
            specification.loader.exec_module(module)
            plugin_class = getattr(module, class_name)
        except BaseException as exc:
            sys.modules.pop(unique_name, None)
            return self._failure(
                PluginLoadResult.IMPORT_ERROR,
                plugin_directory,
                "plugin.import_error",
                f"Unable to import {manifest.entry}: {exc}",
                manifest,
                source_kind,
            )

        try:
            plugin = plugin_class()
        except BaseException as exc:
            return self._failure(
                PluginLoadResult.INITIALIZATION_ERROR,
                plugin_directory,
                "plugin.initialization_error",
                f"Unable to initialize {manifest.entry}: {exc}",
                manifest,
                source_kind,
            )
        descriptor = getattr(plugin, "descriptor", None)
        expected_class = {
            PluginType.PARSER: ParserPlugin,
            PluginType.CALIBRATION: CalibrationModelPlugin,
            PluginType.PROCESSOR: ProcessorPlugin,
            PluginType.ANALYZER: AnalyzerPlugin,
            PluginType.EXPORTER: ExporterPlugin,
        }[manifest.plugin_type]
        if (
            not isinstance(plugin, expected_class)
            or not isinstance(descriptor, PluginDescriptor)
            or not self._matches(manifest, descriptor)
        ):
            return self._failure(
                PluginLoadResult.DESCRIPTOR_MISMATCH,
                plugin_directory,
                "plugin.descriptor_mismatch",
                "Plugin descriptor does not match its manifest",
                manifest,
                source_kind,
            )
        return self._registry.register(
            plugin,
            source=str(plugin_directory),
            source_kind=source_kind,
        )

    @staticmethod
    def _matches(manifest: PluginManifest, descriptor: PluginDescriptor) -> bool:
        return (
            descriptor.plugin_id == manifest.plugin_id
            and descriptor.plugin_type is manifest.plugin_type
            and descriptor.api_version == manifest.api_version
            and descriptor.version == manifest.version
        )

    @staticmethod
    def _source_kind_resolve(
        configured_source_kind: str, manifest: PluginManifest
    ) -> str:
        if configured_source_kind == "application":
            return (
                "bundled"
                if manifest.plugin_id.startswith("builtin.")
                else "application"
            )
        return configured_source_kind

    def _failure(
        self,
        result: PluginLoadResult,
        source: Path,
        code: str,
        message: str,
        manifest: PluginManifest | None = None,
        source_kind: str = "unknown",
    ) -> PluginRecord:
        record = PluginRecord(
            descriptor=None,
            result=result,
            source=str(source),
            source_kind=source_kind,
            diagnostics=(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    code,
                    message,
                    source=str(source),
                    plugin_id=manifest.plugin_id if manifest else None,
                    details={"plugin_version": manifest.version} if manifest else {},
                ),
            ),
            manifest_plugin_id=manifest.plugin_id if manifest else None,
        )
        self._registry.add_record(record)
        return record


def Plugin_TranslationDirectories(plugin_directory: Path) -> tuple[Path, ...]:
    translation_directory = Path(plugin_directory) / "i18n"
    return (translation_directory,) if translation_directory.is_dir() else ()
