import json
import zipfile
from pathlib import Path

import pytest

from underline_retldc.core.registry import PluginLoadResult, PluginRegistry
from underline_retldc.plugin_api.common import PluginType
from underline_retldc.plugins import installer as plugin_installer
from underline_retldc.plugins.installer import (
    PluginAlreadyExistsError,
    PluginInstaller_Install,
    PluginInstaller_InstallDirectory,
    PluginInstallResult,
)
from underline_retldc.plugins.loader import PluginDiscoveryRoot, PluginLoader
from underline_retldc.plugins.manifest import Manifest_Load

VALID_PLUGIN = '''
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType, ProbeResult
from underline_retldc.plugin_api.parser import ParserPlugin

class ExampleParser(ParserPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "example.parser.valid", PluginType.PARSER, "1.0.0", "1", "Example", ""
        )
    def probe(self, source, context):
        return ProbeResult(0.0, "example")
    def config_schema(self):
        return {"type": "object"}
    def parse(self, source, config, context):
        raise NotImplementedError
    def validate(self, dataset):
        return []
'''

VALID_CALIBRATION = '''
import numpy as np
from underline_retldc.plugin_api.calibration import CalibrationModelPlugin
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType

class ExampleCalibration(CalibrationModelPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "example.calibration.valid", PluginType.CALIBRATION,
            "1.0.0", "1", "Example Calibration", ""
        )
    def parameter_schema(self):
        return {"type": "object", "properties": {}}
    def evaluate(self, raw, parameters):
        return np.array(raw, dtype=float, copy=True)
'''


def _manifest(**overrides) -> dict:
    payload = {
        "plugin_id": "example.parser.valid",
        "plugin_type": "parser",
        "api_version": "1",
        "version": "1.0.0",
        "entry": "parser:ExampleParser",
        "name": "Example",
    }
    payload.update(overrides)
    return payload


def _plugin_directory(tmp_path: Path, name: str, manifest: dict, code: str) -> Path:
    directory = tmp_path / name
    directory.mkdir(parents=True)
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    module_name = str(manifest["entry"]).split(":", maxsplit=1)[0]
    module_path = directory.joinpath(*module_name.split(".")).with_suffix(".py")
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(code, encoding="utf-8")
    return directory


def test_valid_external_parser_loads(tmp_path: Path) -> None:
    directory = _plugin_directory(tmp_path, "valid", _manifest(), VALID_PLUGIN)
    registry = PluginRegistry()
    record = PluginLoader(registry).load(directory)
    assert record.result is PluginLoadResult.LOADED
    assert registry.get("example.parser.valid").descriptor.name == "Example"


def test_bad_manifest_is_isolated(tmp_path: Path) -> None:
    directory = tmp_path / "bad"
    directory.mkdir()
    (directory / "plugin.json").write_text("{bad", encoding="utf-8")
    record = PluginLoader(PluginRegistry()).load(directory)
    assert record.result is PluginLoadResult.MANIFEST_ERROR


def test_broken_optional_plugin_does_not_block_other_discovery(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins"
    _plugin_directory(plugin_root, "valid", _manifest(), VALID_PLUGIN)
    broken = plugin_root / "broken"
    broken.mkdir(parents=True)
    (broken / "plugin.json").write_text("{bad", encoding="utf-8")
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (PluginDiscoveryRoot(plugin_root, "user"),)
    )
    assert {record.result for record in records} == {
        PluginLoadResult.LOADED,
        PluginLoadResult.MANIFEST_ERROR,
    }
    assert registry.get("example.parser.valid")


def test_api_mismatch_is_isolated(tmp_path: Path) -> None:
    directory = _plugin_directory(
        tmp_path, "api", _manifest(api_version="999"), VALID_PLUGIN
    )
    record = PluginLoader(PluginRegistry()).load(directory)
    assert record.result is PluginLoadResult.API_MISMATCH


def test_broken_import_is_isolated(tmp_path: Path) -> None:
    directory = _plugin_directory(
        tmp_path, "broken", _manifest(), "raise RuntimeError('broken plugin')\n"
    )
    record = PluginLoader(PluginRegistry()).load(directory)
    assert record.result is PluginLoadResult.IMPORT_ERROR


def test_duplicate_id_is_isolated_before_import(
    tmp_path: Path, bundled_registry
) -> None:
    manifest = _manifest(
        plugin_id="builtin.parser.tr_f", version="1.0.0", entry="missing:Parser"
    )
    directory = _plugin_directory(tmp_path, "duplicate", manifest, "")
    record = PluginLoader(bundled_registry).load(directory)
    assert record.result is PluginLoadResult.DUPLICATE_ID


def test_descriptor_without_plugin_interface_is_rejected(tmp_path: Path) -> None:
    code = '''
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType
class ExampleParser:
    @property
    def descriptor(self):
        return PluginDescriptor(
            "example.parser.valid", PluginType.PARSER, "1.0.0", "1", "Example", ""
        )
'''
    directory = _plugin_directory(tmp_path, "wrong_type", _manifest(), code)
    record = PluginLoader(PluginRegistry()).load(directory)
    assert record.result is PluginLoadResult.DESCRIPTOR_MISMATCH


def test_bundled_plugins_are_discovered_recursively() -> None:
    project_root = Path(__file__).resolve().parents[2]
    root = project_root / "plugins"
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (PluginDiscoveryRoot(root, "application"),)
    )
    assert len(records) == len(tuple(root.rglob("plugin.json")))
    assert all(record.result is PluginLoadResult.LOADED for record in records)
    assert all(record.source_kind == "bundled" for record in records)
    assert registry.get("builtin.parser.tr_f").descriptor.plugin_type is PluginType.PARSER
    assert registry.get("builtin.parser.tr_p").descriptor.plugin_type is PluginType.PARSER
    assert registry.get("builtin.parser.tr_t").descriptor.plugin_type is PluginType.PARSER
    assert (
        registry.get("builtin.calibration.linear").descriptor.plugin_type
        is PluginType.CALIBRATION
    )
    assert registry.get("builtin.calibration.identity")
    assert registry.get("builtin.parser.generic_xlsx")
    assert registry.get("builtin.parser.generic_delimited")
    assert registry.get("builtin.exporter.chamber_pressure_csv")
    assert registry.get("builtin.exporter.temperature_png")
    assert not list((project_root / "src" / "underline_retldc" / "builtin").rglob("*.py"))


def test_recursive_discovery_uses_manifest_type_not_category_name(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins"
    _plugin_directory(
        plugin_root / "not_a_parser_category",
        "misplaced_parser",
        _manifest(),
        VALID_PLUGIN,
    )
    calibration_manifest = _manifest(
        plugin_id="example.calibration.valid",
        plugin_type="calibration",
        entry="calibration:ExampleCalibration",
        name="Example Calibration",
    )
    _plugin_directory(
        plugin_root / "calibrations",
        "example_calibration",
        calibration_manifest,
        VALID_CALIBRATION,
    )
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (PluginDiscoveryRoot(plugin_root, "user"),)
    )
    assert len(records) == 2
    assert all(record.result is PluginLoadResult.LOADED for record in records)
    assert registry.get("example.parser.valid").descriptor.plugin_type is PluginType.PARSER
    assert (
        registry.get("example.calibration.valid").descriptor.plugin_type
        is PluginType.CALIBRATION
    )


def test_installer_organizes_plugin_under_user_category(tmp_path: Path) -> None:
    source = _plugin_directory(tmp_path, "source", _manifest(), VALID_PLUGIN)
    user_root = tmp_path / "user_plugins"
    destination = PluginInstaller_InstallDirectory(source, user_root)
    assert destination.parent == user_root.resolve() / "parsers"
    assert (destination / "plugin.json").is_file()
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (PluginDiscoveryRoot(user_root, "user"),)
    )
    assert len(records) == 1
    assert records[0].result is PluginLoadResult.LOADED
    assert records[0].source_kind == "user"


def test_installer_prefers_writable_application_root(tmp_path: Path) -> None:
    source = _plugin_directory(tmp_path, "source", _manifest(), VALID_PLUGIN)
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"

    outcome = PluginInstaller_Install(source, application_root, user_root)

    assert outcome.result is PluginInstallResult.APPLICATION
    assert outcome.destination.parent == application_root.resolve() / "parsers"
    assert not user_root.exists()
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (
            PluginDiscoveryRoot(application_root, "application"),
            PluginDiscoveryRoot(user_root, "user"),
        )
    )
    assert len(records) == 1
    assert records[0].result is PluginLoadResult.LOADED
    assert records[0].source_kind == "application"


def test_installer_falls_back_when_application_root_probe_is_not_writable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _plugin_directory(tmp_path, "source", _manifest(), VALID_PLUGIN)
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"
    monkeypatch.setattr(plugin_installer, "PluginRoot_IsWritable", lambda _root: False)

    outcome = PluginInstaller_Install(source, application_root, user_root)

    assert outcome.result is PluginInstallResult.USER_FALLBACK
    assert outcome.destination.parent == user_root.resolve() / "parsers"
    assert not application_root.exists()
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (
            PluginDiscoveryRoot(application_root, "application"),
            PluginDiscoveryRoot(user_root, "user"),
        )
    )
    assert len(records) == 1
    assert records[0].result is PluginLoadResult.LOADED
    assert records[0].source_kind == "user"


def test_installer_falls_back_only_for_actual_copy_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _plugin_directory(tmp_path, "source", _manifest(), VALID_PLUGIN)
    application_root = (tmp_path / "application_plugins").resolve()
    user_root = (tmp_path / "user_plugins").resolve()
    original_install = plugin_installer._PluginInstaller_InstallPrepared

    def permission_once(source_path, manifest, destination_root, **options):
        if Path(destination_root).resolve() == application_root:
            raise PermissionError(13, "permission denied", str(destination_root))
        return original_install(source_path, manifest, destination_root, **options)

    monkeypatch.setattr(
        plugin_installer,
        "_PluginInstaller_InstallPrepared",
        permission_once,
    )
    outcome = PluginInstaller_Install(source, application_root, user_root)
    assert outcome.result is PluginInstallResult.USER_FALLBACK
    assert outcome.destination.parent == user_root / "parsers"


def test_installer_does_not_fallback_for_non_permission_copy_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _plugin_directory(tmp_path, "source", _manifest(), VALID_PLUGIN)
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"

    def invalid_copy(*_args, **_options):
        raise ValueError("copy validation failed")

    monkeypatch.setattr(
        plugin_installer,
        "_PluginInstaller_InstallPrepared",
        invalid_copy,
    )
    with pytest.raises(ValueError, match="copy validation failed"):
        PluginInstaller_Install(source, application_root, user_root)
    assert not user_root.exists()


def test_installer_does_not_fallback_for_invalid_manifest_or_api(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "plugin.json").write_text("{bad", encoding="utf-8")
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"
    with pytest.raises(ValueError, match="Unable to read plugin manifest"):
        PluginInstaller_Install(invalid, application_root, user_root)
    assert not application_root.exists()
    assert not user_root.exists()

    unsupported = _plugin_directory(
        tmp_path,
        "unsupported",
        _manifest(api_version="999"),
        VALID_PLUGIN,
    )
    with pytest.raises(ValueError, match="unsupported"):
        PluginInstaller_Install(unsupported, application_root, user_root)
    assert not application_root.exists()
    assert not user_root.exists()


def test_zip_installer_and_path_traversal_protection(tmp_path: Path) -> None:
    source = _plugin_directory(tmp_path, "zip_source", _manifest(), VALID_PLUGIN)
    archive_path = tmp_path / "plugin.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for item in source.rglob("*"):
            if item.is_file():
                archive.write(item, Path("example_plugin") / item.relative_to(source))
    outcome = PluginInstaller_Install(
        archive_path,
        tmp_path / "application_plugins",
        tmp_path / "user_plugins",
    )
    assert outcome.result is PluginInstallResult.APPLICATION
    assert (outcome.destination / "parser.py").is_file()

    unsafe_archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe_archive, "w") as archive:
        archive.writestr("../outside.txt", "unsafe")
        archive.writestr("example/plugin.json", json.dumps(_manifest()))
    with pytest.raises(ValueError, match="Unsafe path"):
        PluginInstaller_Install(
            unsafe_archive,
            tmp_path / "other_application_plugins",
            tmp_path / "other_user_plugins",
        )


def test_existing_plugin_reports_versions_and_replacement_removes_old_files(
    tmp_path: Path,
) -> None:
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"
    first = _plugin_directory(tmp_path, "first", _manifest(), VALID_PLUGIN)
    initial = PluginInstaller_Install(first, application_root, user_root)
    (initial.destination / "obsolete.py").write_text("old", encoding="utf-8")
    replacement_code = VALID_PLUGIN.replace('"1.0.0"', '"2.0.0"')
    second = _plugin_directory(
        tmp_path,
        "second",
        _manifest(version="2.0.0"),
        replacement_code,
    )

    with pytest.raises(PluginAlreadyExistsError) as captured:
        PluginInstaller_Install(second, application_root, user_root)
    assert captured.value.current_version == "1.0.0"
    assert captured.value.incoming_version == "2.0.0"

    replaced = PluginInstaller_Install(
        second,
        application_root,
        user_root,
        replace=True,
    )
    assert replaced.replaced
    assert replaced.result is PluginInstallResult.APPLICATION
    assert not (replaced.destination / "obsolete.py").exists()
    assert Manifest_Load(replaced.destination / "plugin.json").version == "2.0.0"


def test_distinct_plugin_ids_cannot_collide_in_installed_folder_names(
    tmp_path: Path,
) -> None:
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"
    dotted = _plugin_directory(
        tmp_path,
        "dotted",
        _manifest(plugin_id="example.parser.a.b"),
        VALID_PLUGIN,
    )
    underscored = _plugin_directory(
        tmp_path,
        "underscored",
        _manifest(plugin_id="example.parser.a_b"),
        VALID_PLUGIN,
    )

    dotted_outcome = PluginInstaller_Install(dotted, application_root, user_root)
    underscored_outcome = PluginInstaller_Install(
        underscored, application_root, user_root
    )

    assert dotted_outcome.destination != underscored_outcome.destination
    assert dotted_outcome.destination.name == "dotted"
    assert underscored_outcome.destination.name == "underscored"


def test_application_and_user_roots_report_duplicate_without_override(
    tmp_path: Path,
) -> None:
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"
    _plugin_directory(application_root, "application_copy", _manifest(), VALID_PLUGIN)
    _plugin_directory(user_root, "user_copy", _manifest(), VALID_PLUGIN)
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (
            PluginDiscoveryRoot(application_root, "application"),
            PluginDiscoveryRoot(user_root, "user"),
        )
    )
    assert [record.result for record in records] == [
        PluginLoadResult.LOADED,
        PluginLoadResult.DUPLICATE_ID,
    ]
    assert records[0].source_kind == "application"
    assert records[1].source_kind == "user"


def test_loader_ignores_installer_staging_and_backup_directories(
    tmp_path: Path,
) -> None:
    application_root = tmp_path / "application_plugins"
    _plugin_directory(
        application_root / "parsers",
        "example_parser_valid",
        _manifest(),
        VALID_PLUGIN,
    )
    _plugin_directory(
        application_root / "parsers",
        ".underline-retldc-backup-example_parser_valid-stale",
        _manifest(),
        VALID_PLUGIN,
    )
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (PluginDiscoveryRoot(application_root, "application"),)
    )
    assert len(records) == 1
    assert records[0].result is PluginLoadResult.LOADED
