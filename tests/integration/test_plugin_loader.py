import json
from pathlib import Path

from underline_retldc.core.registry import PluginLoadResult, PluginRegistry
from underline_retldc.plugin_api.common import PluginType
from underline_retldc.plugins.installer import PluginInstaller_InstallDirectory
from underline_retldc.plugins.loader import PluginDiscoveryRoot, PluginLoader

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
        (PluginDiscoveryRoot(root, "bundled"),)
    )
    assert len(records) == 10
    assert all(record.result is PluginLoadResult.LOADED for record in records)
    assert all(record.source_kind == "bundled" for record in records)
    assert registry.get("builtin.parser.tr_f").descriptor.plugin_type is PluginType.PARSER
    assert (
        registry.get("builtin.calibration.linear").descriptor.plugin_type
        is PluginType.CALIBRATION
    )
    assert registry.get("builtin.calibration.identity")
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
