import json
import zipfile
from pathlib import Path
from threading import Event

import pytest

from underline_retldc.core.registry import PluginLoadResult
from underline_retldc.plugin_api.common import PluginType, TaskContext
from underline_retldc.plugins import installer as plugin_installer
from underline_retldc.plugins.installer import (
    PLUGIN_TYPE_SUBDIRECTORY,
    PluginCandidateStatus,
    PluginInstallDecision,
    PluginInstaller_InstallBatch,
    PluginInstallItemState,
    PluginInstallResult,
    PluginInstallStage,
    PluginPackage_Discover,
)


def _manifest(
    plugin_id: str,
    *,
    plugin_type: str = "parser",
    version: str = "1.0.0",
    class_name: str = "ExampleParser",
) -> dict[str, str]:
    return {
        "plugin_id": plugin_id,
        "plugin_type": plugin_type,
        "api_version": "1",
        "version": version,
        "entry": f"plugin:{class_name}",
        "name": plugin_id,
    }


def _parser_code(plugin_id: str, version: str = "1.0.0") -> str:
    return f'''
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType, ProbeResult
from underline_retldc.plugin_api.parser import ParserPlugin

class ExampleParser(ParserPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "{plugin_id}", PluginType.PARSER, "{version}", "1", "{plugin_id}", ""
        )
    def probe(self, source, context):
        return ProbeResult(0.0, "test")
    def config_schema(self):
        return {{"type": "object"}}
    def parse(self, source, config, context):
        raise NotImplementedError
    def validate(self, dataset):
        return []
'''


def _calibration_code(plugin_id: str, version: str = "1.0.0") -> str:
    return f'''
import numpy as np
from underline_retldc.plugin_api.calibration import CalibrationModelPlugin
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType

class ExampleCalibration(CalibrationModelPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "{plugin_id}", PluginType.CALIBRATION,
            "{version}", "1", "{plugin_id}", ""
        )
    def parameter_schema(self):
        return {{"type": "object", "properties": {{}}}}
    def evaluate(self, raw, parameters):
        return np.array(raw, dtype=float, copy=True)
'''


def _plugin_write(
    directory: Path,
    manifest: dict[str, str],
    code: str,
) -> Path:
    directory.mkdir(parents=True)
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "plugin.py").write_text(code, encoding="utf-8")
    return directory


def _archive_tree(source: Path, archive_path: Path, *, wrapper: Path = Path()) -> None:
    with zipfile.ZipFile(archive_path, "w") as archive:
        for item in source.rglob("*"):
            if item.is_file():
                archive.write(item, wrapper / item.relative_to(source))


def _install_all(package, application_root: Path, user_root: Path):
    decisions = {
        candidate.relative_path: (
            PluginInstallDecision.INSTALL
            if candidate.conflict_status is PluginCandidateStatus.READY
            else PluginInstallDecision.SKIP
        )
        for candidate in package.candidates
    }
    return PluginInstaller_InstallBatch(
        package,
        decisions,
        application_root,
        user_root,
    )


def test_official_tr_t_directory_installs_and_loads_directly(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "plugins" / "parsers" / "tr_t"
    application_root = tmp_path / "application"
    user_root = tmp_path / "user"
    package = PluginPackage_Discover(source, application_root, user_root)
    try:
        assert len(package.candidates) == 1
        candidate = package.candidates[0]
        assert candidate.relative_path == "."
        assert candidate.plugin_id == "builtin.parser.tr_t"
        outcome = _install_all(package, application_root, user_root)
    finally:
        package.close()
    assert outcome.success_count == 1
    assert outcome.items[0].state is PluginInstallItemState.INSTALLED_AND_LOADED
    assert outcome.items[0].install_outcome is not None
    assert outcome.items[0].install_outcome.destination == (
        application_root / "parsers" / "tr_t"
    ).resolve()


def test_arbitrary_folder_depth_copies_only_resolved_plugin_root(tmp_path: Path) -> None:
    package_root = tmp_path / "package"
    source = _plugin_write(
        package_root / "a" / "b" / "c" / "tr_t",
        _manifest("example.parser.deep"),
        _parser_code("example.parser.deep"),
    )
    (package_root / "README_FOR_USER.txt").write_text("wrapper", encoding="utf-8")
    application_root = tmp_path / "application"
    user_root = tmp_path / "user"
    package = PluginPackage_Discover(package_root, application_root, user_root)
    try:
        assert package.candidates[0].plugin_root == source.resolve()
        assert package.candidates[0].relative_path == "a/b/c/tr_t"
        outcome = _install_all(package, application_root, user_root)
    finally:
        package.close()
    destination = application_root / "parsers" / "tr_t"
    assert outcome.success_count == 1
    assert (destination / "plugin.json").is_file()
    assert not (destination / "README_FOR_USER.txt").exists()


@pytest.mark.parametrize("wrapper", [Path(), Path("a/b/c/tr_t")])
def test_zip_root_and_arbitrary_wrapper_are_supported(
    tmp_path: Path,
    wrapper: Path,
) -> None:
    source = _plugin_write(
        tmp_path / "zip_source",
        _manifest("example.parser.zip"),
        _parser_code("example.parser.zip"),
    )
    archive_path = tmp_path / "zip_plugin.zip"
    _archive_tree(source, archive_path, wrapper=wrapper)
    application_root = tmp_path / "application"
    package = PluginPackage_Discover(archive_path, application_root, tmp_path / "user")
    try:
        assert len(package.candidates) == 1
        outcome = _install_all(package, application_root, tmp_path / "user")
    finally:
        package.close()
    assert outcome.success_count == 1


def test_mixed_multi_plugin_zip_is_classified_and_loaded(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _plugin_write(
        source / "a" / "parser_a",
        _manifest("example.parser.a"),
        _parser_code("example.parser.a"),
    )
    _plugin_write(
        source / "b" / "parser_b",
        _manifest("example.parser.b"),
        _parser_code("example.parser.b"),
    )
    _plugin_write(
        source / "c" / "calibration_a",
        _manifest(
            "example.calibration.a",
            plugin_type="calibration",
            class_name="ExampleCalibration",
        ),
        _calibration_code("example.calibration.a"),
    )
    archive_path = tmp_path / "mixed.zip"
    _archive_tree(source, archive_path, wrapper=Path("wrapper/deeper"))
    application_root = tmp_path / "application"
    package = PluginPackage_Discover(archive_path, application_root, tmp_path / "user")
    try:
        assert len(package.candidates) == 3
        outcome = _install_all(package, application_root, tmp_path / "user")
    finally:
        package.close()
    assert outcome.success_count == 3
    assert (application_root / "parsers" / "parser_a").is_dir()
    assert (application_root / "parsers" / "parser_b").is_dir()
    assert (application_root / "calibrations" / "calibration_a").is_dir()


def test_nested_manifest_uses_only_deepest_candidate(tmp_path: Path) -> None:
    outer = _plugin_write(
        tmp_path / "package" / "outer",
        _manifest("example.parser.outer"),
        _parser_code("example.parser.outer"),
    )
    _plugin_write(
        outer / "child" / "inner",
        _manifest("example.parser.inner"),
        _parser_code("example.parser.inner"),
    )
    package = PluginPackage_Discover(
        tmp_path / "package",
        tmp_path / "application",
        tmp_path / "user",
    )
    try:
        statuses = {
            candidate.plugin_id: candidate.conflict_status
            for candidate in package.candidates
        }
        assert statuses["example.parser.outer"] is PluginCandidateStatus.NESTED_CONTAINER
        assert statuses["example.parser.inner"] is PluginCandidateStatus.READY
        outcome = _install_all(package, tmp_path / "application", tmp_path / "user")
    finally:
        package.close()
    assert outcome.success_count == 1
    assert not (tmp_path / "application" / "parsers" / "outer").exists()
    assert (tmp_path / "application" / "parsers" / "inner").is_dir()


def test_duplicate_source_id_is_rejected_without_blocking_other_plugin(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    for folder in ("a", "b"):
        _plugin_write(
            source / folder,
            _manifest("example.parser.duplicate"),
            _parser_code("example.parser.duplicate"),
        )
    _plugin_write(
        source / "valid",
        _manifest("example.parser.other"),
        _parser_code("example.parser.other"),
    )
    package = PluginPackage_Discover(
        source,
        tmp_path / "application",
        tmp_path / "user",
    )
    try:
        duplicate_candidates = [
            item for item in package.candidates if item.plugin_id.endswith("duplicate")
        ]
        assert all(
            item.conflict_status is PluginCandidateStatus.SOURCE_DUPLICATE_ID
            for item in duplicate_candidates
        )
        outcome = _install_all(package, tmp_path / "application", tmp_path / "user")
    finally:
        package.close()
    assert outcome.success_count == 1
    assert outcome.registry.get("example.parser.other")
    with pytest.raises(KeyError):
        outcome.registry.get("example.parser.duplicate")


def test_every_manifest_type_maps_to_one_stable_category(tmp_path: Path) -> None:
    source = tmp_path / "source"
    for plugin_type in PluginType:
        plugin_id = f"example.{plugin_type.value}.category"
        _plugin_write(
            source / plugin_type.value,
            _manifest(plugin_id, plugin_type=plugin_type.value),
            _parser_code(plugin_id),
        )
    package = PluginPackage_Discover(
        source,
        tmp_path / "application",
        tmp_path / "user",
    )
    try:
        assert {
            candidate.plugin_type: candidate.destination_category
            for candidate in package.candidates
        } == PLUGIN_TYPE_SUBDIRECTORY
    finally:
        package.close()


def test_permission_fallback_is_decided_per_plugin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    for suffix in ("application", "fallback"):
        plugin_id = f"example.parser.{suffix}"
        _plugin_write(
            source / suffix,
            _manifest(plugin_id),
            _parser_code(plugin_id),
        )
    application_root = (tmp_path / "application").resolve()
    user_root = (tmp_path / "user").resolve()
    original = plugin_installer._PluginInstaller_InstallPrepared

    def install_with_one_permission_failure(source_path, manifest, root, **options):
        if (
            Path(root).resolve() == application_root
            and manifest.plugin_id.endswith("fallback")
        ):
            raise PermissionError(13, "permission denied", str(root))
        return original(source_path, manifest, root, **options)

    monkeypatch.setattr(
        plugin_installer,
        "_PluginInstaller_InstallPrepared",
        install_with_one_permission_failure,
    )
    package = PluginPackage_Discover(source, application_root, user_root)
    try:
        outcome = _install_all(package, application_root, user_root)
    finally:
        package.close()
    assert outcome.success_count == 2
    results = {
        item.candidate.plugin_id: item.install_outcome.result
        for item in outcome.items
        if item.install_outcome is not None
    }
    assert results["example.parser.application"] is PluginInstallResult.APPLICATION
    assert results["example.parser.fallback"] is PluginInstallResult.USER_FALLBACK


def test_existing_user_plugin_replaces_in_place_without_application_duplicate(
    tmp_path: Path,
) -> None:
    user_root = tmp_path / "user"
    existing = _plugin_write(
        user_root / "parsers" / "legacy_location",
        _manifest("example.parser.replace", version="1.0.0"),
        _parser_code("example.parser.replace", "1.0.0"),
    )
    (existing / "obsolete.txt").write_text("old", encoding="utf-8")
    incoming = _plugin_write(
        tmp_path / "incoming",
        _manifest("example.parser.replace", version="2.0.0"),
        _parser_code("example.parser.replace", "2.0.0"),
    )
    application_root = tmp_path / "application"
    package = PluginPackage_Discover(incoming, application_root, user_root)
    try:
        candidate = package.candidates[0]
        assert candidate.conflict_status is PluginCandidateStatus.EXISTING
        outcome = PluginInstaller_InstallBatch(
            package,
            {candidate.relative_path: PluginInstallDecision.REPLACE},
            application_root,
            user_root,
        )
    finally:
        package.close()
    assert outcome.success_count == 1
    assert outcome.items[0].install_outcome is not None
    assert outcome.items[0].install_outcome.destination == existing.resolve()
    assert not application_root.exists()
    assert not (existing / "obsolete.txt").exists()


def test_batch_progress_is_monotonic_and_load_failure_is_reported(tmp_path: Path) -> None:
    source = _plugin_write(
        tmp_path / "broken",
        _manifest("example.parser.broken"),
        "raise RuntimeError('broken during import')\n",
    )
    application_root = tmp_path / "application"
    package = PluginPackage_Discover(source, application_root, tmp_path / "user")
    progress: list[tuple[float, str]] = []
    context = TaskContext(
        cancellation_event=Event(),
        progress_callback=lambda value, message: progress.append((value, message)),
    )
    messages = {
        stage: (
            "install {current}/{total}: {name}"
            if stage is PluginInstallStage.COPY
            else stage.value
        )
        for stage in PluginInstallStage
    }
    try:
        candidate = package.candidates[0]
        outcome = PluginInstaller_InstallBatch(
            package,
            {candidate.relative_path: PluginInstallDecision.INSTALL},
            application_root,
            tmp_path / "user",
            context=context,
            status_messages=messages,
        )
    finally:
        package.close()
    assert [value for value, _message in progress] == sorted(
        value for value, _message in progress
    )
    assert progress[-1][0] == 1.0
    assert any("install 1/1" in message for _value, message in progress)
    assert outcome.items[0].state is PluginInstallItemState.INSTALLED_LOAD_FAILED
    assert outcome.items[0].record is not None
    assert outcome.items[0].record.result is PluginLoadResult.IMPORT_ERROR
