from __future__ import annotations

import importlib
import shutil
from dataclasses import replace
from pathlib import Path
from threading import Event

import numpy as np
import pytest

from underline_retldc.app.export_snapshot import ExportSnapshot_Build
from underline_retldc.app.project_pipeline import ProjectPipeline
from underline_retldc.app.source_input import Source_ParseVerified
from underline_retldc.cli import main
from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project import Project_Load, Project_Save, Project_SourceHash
from underline_retldc.plugin_api.common import TaskCancelledError, TaskContext

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/motor_test_package/v1"


@pytest.fixture
def prepared(tmp_path, bundled_registry):
    for name in ("synthetic.csv", "synthetic.retldc.json"):
        shutil.copyfile(FIXTURES / name, tmp_path / name)
    project = tmp_path / "synthetic.retldc.json"
    session = ProjectPipeline.Project_LoadSession(project, bundled_registry, TaskContext())
    plugin = bundled_registry.get("builtin.exporter.treediagram_motor")
    return session, plugin


def _contract(plugin):
    return importlib.import_module(plugin.__class__.__module__ + ".contract")


def _package(session, plugin, registry, **options):
    snapshot = ExportSnapshot_Build(session, registry)
    return plugin.Package_Build(snapshot.dataset, {**snapshot.Config_Copy(), **options})


def test_actual_parser_calibration_polarity_compensation_export(prepared, bundled_registry):
    session, plugin = prepared
    package = _package(session, plugin, bundled_registry)
    assert package["metrics"]["total_impulse_ns"] == pytest.approx(200.0, abs=1e-11)
    assert max(package["simulation_curve"]["thrust_n"]) == pytest.approx(200.0)
    assert package["motor"]["diameter_m"] == 0.05
    assert package["motor"]["length_m"] == 0.2
    assert package["motor"]["propellant_mass_kg"] == 0.15
    assert package["source"]["sha256"] == Project_SourceHash(session.source_path)
    assert [stage["stage"] for stage in package["processing_chain"]] == [
        "parser",
        "calibration",
        "polarity",
        "processor",
        "analyzer",
    ]
    assert package["calibration"]["status"] == "unknown"
    np.testing.assert_allclose(
        package["evidence_curve"]["thrust_n"],
        session.processed_dataset.channel("thrust_processed").values,
    )


def test_multiple_sources_cwd_selection_and_frozen_snapshot(
    tmp_path, prepared, bundled_registry, monkeypatch
):
    session, plugin = prepared
    document = Project_Load(session.project_path)
    other = tmp_path / "secondary.csv"
    other.write_text("0,999\n0.2,998\n0.4,997\n", encoding="utf-8")
    source = replace(
        document.sources[0], source_id="second", path=other.name, sha256=Project_SourceHash(other)
    )
    stream = replace(document.streams[0], source_id="second", stream_id="other_rate")
    document = replace(
        document, sources=(*document.sources, source), streams=(*document.streams, stream)
    )
    Project_Save(document, session.project_path)
    elsewhere = tmp_path / "wrong_cwd"
    elsewhere.mkdir()
    (elsewhere / other.name).write_text("0,0\n1,0", encoding="utf-8")
    monkeypatch.chdir(elsewhere)
    restored = ProjectPipeline.Project_LoadSession(
        session.project_path, bundled_registry, TaskContext()
    )
    assert restored.project_data.sources["second"].sha256 == source.sha256
    before = _package(restored, plugin, bundled_registry)
    snapshot = ExportSnapshot_Build(restored, bundled_registry)
    restored.active_stream_id = "other_rate"
    restored.source_path, restored.source_hash = other, source.sha256
    restored.parser_id, restored.parser_config = "irrelevant.ui.selection", {"wrong": True}
    restored.calibration_config = {"parameters": {"K": 999}}
    after = _package(restored, plugin, bundled_registry)
    assert before == after
    restored.processor_config["enabled"] = False
    assert plugin.Package_Build(snapshot.dataset, snapshot.Config_Copy()) == before
    assert snapshot.Config_Copy()["source_reference"]["source_id"] == "bench"


def test_unsaved_and_modified_source_keeps_original_identity(prepared, bundled_registry):
    session, plugin = prepared
    session.project_path = None
    original_hash = session.project_data.sources["bench"].sha256
    session.source_path.write_text("0,100\n1,100\n", encoding="utf-8")
    package = _package(session, plugin, bundled_registry)
    assert package["source"]["sha256"] == original_hash
    assert package["source"]["sha256"] != Project_SourceHash(session.source_path)
    assert package["metrics"]["total_impulse_ns"] == pytest.approx(200)


def test_relocated_project_matches_hash_and_never_uses_same_name_cwd(
    prepared,
    bundled_registry,
    tmp_path,
    monkeypatch,
):
    session, _plugin = prepared
    relocated = tmp_path / "relocated"
    relocated.mkdir()
    for name in ("synthetic.csv", "synthetic.retldc.json"):
        shutil.copyfile(FIXTURES / name, relocated / name)
    monkeypatch.chdir(tmp_path)
    loaded = ProjectPipeline.Project_LoadSession(
        relocated / "synthetic.retldc.json", bundled_registry, TaskContext()
    )
    assert loaded.source_path == (relocated / "synthetic.csv").resolve()
    (relocated / "synthetic.csv").write_text("0,0\n1,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        ProjectPipeline.Project_LoadSession(
            relocated / "synthetic.retldc.json", bundled_registry, TaskContext()
        )


def test_actual_result_channel_not_fixed_name(prepared, bundled_registry):
    session, plugin = prepared
    dataset = session.processed_dataset
    renamed = replace(dataset.channel("thrust_processed"), id="final_force_custom")
    channels = {key: value for key, value in dataset.channels.items() if key != "thrust_processed"}
    channels[renamed.id] = renamed
    session.processing_result = replace(
        session.processing_result,
        dataset=replace(dataset, channels=channels),
        output_channel_ids=("baseline_model", "thrust_corrected", renamed.id),
    )
    session.analysis_result = replace(
        session.analysis_result,
        metadata={
            **session.analysis_result.metadata,
            "channel_id": renamed.id,
        },
    )
    assert _package(session, plugin, bundled_registry)["source"]["final_channel_id"] == renamed.id


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda p: p["motor"].update(total_mass_kg=True), "NUMBER"),
        (lambda p: p["motor"].update(propellant_mass_kg=2.0), "MASS"),
        (lambda p: p["motor"].update(diameter_m=-1), "NUMBER"),
        (lambda p: p.update(schema_version=2), "VERSION"),
        (lambda p: p["evidence_curve"]["time_s"].__setitem__(1, -99), "CLOCK"),
        (lambda p: p["evidence_curve"]["thrust_n"].pop(), "LENGTH"),
        (lambda p: p["simulation_curve"]["thrust_n"].__setitem__(1, 999), "SAMPLE_IDENTITY"),
        (lambda p: p["processing_chain"][0].update(source_sha256="f" * 64), "CHAIN"),
        (lambda p: p["metrics"].update(total_impulse_ns=201), "IMPULSE"),
    ],
)
def test_semantic_invalid_vectors(prepared, bundled_registry, change, code):
    session, plugin = prepared
    contract = _contract(plugin)
    package = _package(session, plugin, bundled_registry)
    change(package)
    package["content_sha256"] = contract.MotorPackage_Digest(package)
    with pytest.raises(ValueError, match=code):
        contract.MotorPackage_Validate(package)


def test_import_limits_duplicate_keys_digest_and_nonfinite(prepared, bundled_registry, tmp_path):
    session, plugin = prepared
    contract = _contract(plugin)
    package = _package(session, plugin, bundled_registry)
    package["content_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="DIGEST"):
        contract.MotorPackage_Validate(package)
    path = tmp_path / "bad.json"
    for text, match in [
        ('{"a":1,"a":2}', "DUPLICATE_KEY"),
        ('{"a":NaN}', "NUMBER"),
        ("[" * 2000, "JSON"),
    ]:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match=match):
            contract.MotorPackage_Load(path)
    deep = {}
    for _ in range(26):
        deep = {"a": deep}
    with pytest.raises(ValueError, match="LIMIT"):
        contract.MotorPackage_Validate(deep)


def test_unknown_mass_negative_samples_and_gap_are_not_fabricated(prepared, bundled_registry):
    session, plugin = prepared
    annotation = ExportSnapshot_Build(
        session, bundled_registry, motor_metadata={"manufacturer": "format annotation"})
    assert annotation.Config_Copy()["motor_metadata"]["manufacturer"] == "format annotation"
    with pytest.raises(ValueError, match="physical metadata"):
        ExportSnapshot_Build(session, bundled_registry, motor_metadata={"propellant_mass_kg": .3})
    # Replay a real unknown-mass project. Editing a completed session in place
    # would mix an old analysis with a new mass and must be refused.
    session.motor_metadata = {}
    with pytest.raises(ValueError, match="changed after analysis"):
        _package(session, plugin, bundled_registry)
    project = session.project_path
    Project_Save(replace(Project_Load(project), motor_metadata={}), project)
    session = ProjectPipeline.Project_LoadSession(project, bundled_registry, TaskContext())
    package = _package(session, plugin, bundled_registry, maximum_gap_s=0.01)
    assert package["motor"]["propellant_mass_kg"] is None
    assert package["simulation_curve"] is None
    assert package["metrics"]["total_impulse_ns"] is None
    assert len(package["evidence_curve"]["time_s"]) == 61
    assert min(package["evidence_curve"]["thrust_n"]) < 0
    assert {item["code"] for item in package["diagnostics"]} >= {
        "GAP",
        "NEGATIVE_THRUST",
        "MASS_UNKNOWN",
    }


def test_boundaries_interpolate_only_within_gap_and_retain_original_samples(
    prepared, bundled_registry
):
    session, plugin = prepared
    session.regions = {"active_test": [0.525, 2.475]}
    package = _package(session, plugin, bundled_registry)
    curve = package["simulation_curve"]
    assert curve["inserted_boundary_indices"] == [0, len(curve["time_s"]) - 1]
    assert curve["thrust_n"][0] == pytest.approx(5)
    assert curve["thrust_n"][-1] == pytest.approx(5)
    assert package["metrics"]["total_impulse_ns"] == pytest.approx(199.875)
    session.regions = {"active_test": [-1, 2.5]}
    assert _package(session, plugin, bundled_registry)["simulation_curve"] is None


def test_cancel_after_temporary_write_preserves_destination(prepared, bundled_registry, tmp_path):
    session, plugin = prepared
    snapshot = ExportSnapshot_Build(session, bundled_registry)
    destination = tmp_path / "existing.tdmotor.json"
    destination.write_text("original", encoding="utf-8")
    event = Event()
    context = TaskContext(event, lambda *_: event.set())
    with pytest.raises(TaskCancelledError):
        plugin.export(
            destination, snapshot.dataset, snapshot.analysis, snapshot.Config_Copy(), context
        )
    assert destination.read_text() == "original"
    assert not list(tmp_path.glob(".tdmotor-*.tmp"))


def test_headless_and_shared_snapshot_export_identical(prepared, bundled_registry, tmp_path):
    session, plugin = prepared
    output = tmp_path / "cli.tdmotor.json"
    assert main(["export", str(session.project_path), str(output)]) == 0
    assert _contract(plugin).MotorPackage_Load(output) == _package(
        session, plugin, bundled_registry
    )
    draft = Project_Load(session.project_path)
    Project_Save(replace(draft, workflow_state={"parsed": True}), session.project_path)
    with pytest.raises(SystemExit) as error:
        main(["export", str(session.project_path), str(output)])
    assert error.value.code == 2
    assert _contract(plugin).MotorPackage_Load(output)["metrics"]["total_impulse_ns"] == 200.0


def test_file_changes_during_parse_rejected(tmp_path, bundled_registry):
    source = tmp_path / "changing.csv"
    source.write_text("0,1\n1,2\n2,3\n", encoding="utf-8")
    parser = bundled_registry.get("builtin.parser.tr_f")

    class MutatingParser:
        def parse(self, path, config, context):
            result = parser.parse(path, config, context)
            path.write_text("0,999\n1,999\n2,999\n", encoding="utf-8")
            return result

    with pytest.raises(ValueError, match="hash"):
        Source_ParseVerified(MutatingParser(), source, {}, TaskContext())


def test_relocation_is_explicit_and_checks_recorded_hash(prepared, bundled_registry, tmp_path):
    session, plugin = prepared
    relocated = tmp_path / "other-name.csv"
    session.source_path.rename(relocated)
    with pytest.raises(FileNotFoundError):
        ProjectPipeline.Project_LoadSession(session.project_path, bundled_registry, TaskContext())
    loaded = ProjectPipeline.Project_LoadSession(
        session.project_path,
        bundled_registry,
        TaskContext(),
        relocated_sources={"bench": relocated},
    )
    assert _package(loaded, plugin, bundled_registry)["metrics"]["total_impulse_ns"] == 200.0
    relocated.write_text("0,0\n1,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        ProjectPipeline.Project_LoadSession(
            session.project_path,
            bundled_registry,
            TaskContext(),
            relocated_sources={"bench": relocated},
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("time", [0, 0, 1]),
        ("time", [0, 1, 0]),
        ("force", [0, float("nan"), 1]),
        ("force", [0, float("inf"), 1]),
    ],
)
def test_invalid_scientific_arrays_not_silently_repaired(
    prepared,
    bundled_registry,
    field,
    value,
):
    session, plugin = prepared
    snapshot = ExportSnapshot_Build(session, bundled_registry)
    dataset = Dataset(
        time=value if field == "time" else [0, 0.5, 1],
        channels={
            "out": Channel(
                "out", "force", "N", value if field == "force" else [0, 1, 0], "processed"
            )
        },
    )
    with pytest.raises(ValueError, match="CLOCK|NUMBER"):
        plugin.Package_Build(dataset, {**snapshot.Config_Copy(), "channel_id": "out"})


def test_kn_conversion_and_raw_unit_rejection(prepared, bundled_registry):
    session, plugin = prepared
    snapshot = ExportSnapshot_Build(session, bundled_registry)
    dataset = snapshot.dataset
    original = dataset.channel("thrust_processed")
    converted = replace(original, values=original.values / 1000, unit="kN")
    channels = {**dataset.channels, original.id: converted}
    package = plugin.Package_Build(replace(dataset, channels=channels), snapshot.Config_Copy())
    assert package["metrics"]["total_impulse_ns"] == pytest.approx(200)
    channels[original.id] = replace(original, unit="raw")
    with pytest.raises(ValueError):
        plugin.Package_Build(replace(dataset, channels=channels), snapshot.Config_Copy())


def test_real_export_dialog_background_job_uses_frozen_primary(prepared, tmp_path, monkeypatch):
    import time

    from PySide6.QtWidgets import QApplication, QMessageBox

    from underline_retldc.app.settings import SettingsService
    from underline_retldc.gui.main_window import MainWindow
    from underline_retldc.i18n.service import TranslationService

    session, plugin = prepared
    application = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[2]
    window = MainWindow(
        TranslationService("zh_CN"),
        SettingsService(tmp_path / "settings.ini"),
        project_root=root,
        user_plugin_directory=tmp_path / "user_plugins",
    )
    window.session = session
    window._export_availability_update()
    dialog = window.export_dialog
    assert dialog.exporter_checks[plugin.descriptor.plugin_id].isEnabled()
    assert dialog.export_group_id(plugin.descriptor.plugin_id) == "thrust"
    dialog.set_output_directory(tmp_path / "gui-export")
    dialog.set_motor_metadata(session.motor_metadata)
    dialog.set_selected_exporter_ids((plugin.descriptor.plugin_id,))
    errors = []
    monkeypatch.setattr(window, "_error_show", errors.append)
    monkeypatch.setattr(QMessageBox, "information", lambda *_a, **_k: QMessageBox.StandardButton.Ok)
    window._export_execute()
    session.source_hash = "f" * 64
    session.parser_config = {"unrelated": True}
    for _ in range(1000):
        application.processEvents()
        if window._active_task is None:
            break
        time.sleep(0.01)
    assert window._active_task is None and not errors
    package = _contract(plugin).MotorPackage_Load(tmp_path / "gui-export/motor.tdmotor.json")
    assert package["source"]["sha256"] == session.project_data.sources["bench"].sha256
    assert package["metrics"]["total_impulse_ns"] == 200.0
    window.close()


def test_calibration_document_notes_survive_gui_config(tmp_path, bundled_registry):
    from PySide6.QtWidgets import QApplication

    from underline_retldc.core.calibration import Calibration_Load
    from underline_retldc.gui.pages.setup_page import SetupPage
    from underline_retldc.i18n.service import TranslationService

    application = QApplication.instance() or QApplication([])
    page = SetupPage(TranslationService("en_US"))
    page.set_calibrations(
        tuple(
            bundled_registry.get(key)
            for key in ("builtin.calibration.identity", "builtin.calibration.linear")
        )
    )
    page.set_channels([Channel("load", "force", "raw", [1, 2], "raw")])
    document = Calibration_Load(
        Path(__file__).resolve().parents[2]
        / "examples/record_showcase/peak_estimate.calibration.json"
    )
    page.set_calibration_document(document)
    config = page.calibration_config()
    origin = config["calibration_provenance"]["origin_document"]
    assert origin["notes"] == document.notes
    assert origin["qualification"] == "estimated"
    assert origin["model"]["parameters"] == {"K": 0.49, "B": 0.0}
    assert config["calibration_provenance"]["parameters_modified"] is False
    page.close()
    page.deleteLater()
    application.processEvents()


def test_third_party_default_export_group_keeps_primary_processed_input(prepared, bundled_registry):
    session, _plugin = prepared
    usual = ExportSnapshot_Build(session, bundled_registry)
    other = ExportSnapshot_Build(session, bundled_registry, group_id="other")
    assert usual.Config_Copy() == other.Config_Copy()
    assert other.analysis is not None
    np.testing.assert_array_equal(
        other.dataset.channel("thrust_processed").values,
        session.processed_dataset.channel("thrust_processed").values,
    )


def test_explicit_estimated_calibration_survives_replay_and_export(
    prepared, bundled_registry,
):
    from underline_retldc.core.calibration import Calibration_Load

    session, plugin = prepared
    document = Project_Load(session.project_path)
    origin = Calibration_Load(
        Path(__file__).resolve().parents[2]
        / "examples/record_showcase/peak_estimate.calibration.json"
    ).to_dict()
    channels = dict(document.channels)
    key = "bench/loadcell/thrust_raw"
    state = channels[key]
    config = {
        **state.calibration.config,
        "parameters": dict(origin["model"]["parameters"]),
        "calibration_provenance": {
            "origin_document": origin,
            "parameters_modified": False,
        },
    }
    channels[key] = replace(state, calibration=replace(state.calibration, config=config))
    Project_Save(replace(document, channels=channels), session.project_path)
    replay = ProjectPipeline.Project_LoadSession(
        session.project_path, bundled_registry, TaskContext()
    )
    package = _package(replay, plugin, bundled_registry)
    assert package["calibration"]["status"] == "estimated"
    assert origin["notes"] in package["calibration"]["notes"]
    assert package["processing_chain"][1]["config"]["parameters"] == {"K": 0.49, "B": 0.0}


def test_excess_samples_are_rejected_at_export_and_contract(prepared, bundled_registry):
    session, plugin = prepared
    contract = _contract(plugin)
    snapshot = ExportSnapshot_Build(session, bundled_registry)
    count = contract.MAX_SAMPLES + 1
    dataset = Dataset(
        time=np.arange(count, dtype=float),
        channels={"out": Channel("out", "force", "N", np.ones(count), "processed")},
    )
    with pytest.raises(ValueError, match="LENGTH"):
        plugin.Package_Build(dataset, {**snapshot.Config_Copy(), "channel_id": "out"})
    package = _package(session, plugin, bundled_registry)
    package["evidence_curve"]["time_s"] = list(range(count))
    with pytest.raises(ValueError, match="LIMIT|LENGTH"):
        contract.MotorPackage_Validate(package)
