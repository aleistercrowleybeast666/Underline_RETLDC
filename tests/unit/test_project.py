from pathlib import Path

from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.project import (
    PROJECT_SCHEMA,
    PluginReference,
    Project_DefaultExportDirectory,
    Project_Load,
    Project_Save,
    Project_SourceHash,
    Project_SourceResolve,
    ProjectDocument,
    ProjectSourceResolveResult,
    ProjectSourceState,
    ProjectStreamState,
)


def test_project_json_round_trip_and_source_hash(tmp_path: Path) -> None:
    raw = tmp_path / "raw.txt"
    raw.write_text("0,0\n1,2\n", encoding="utf-8")
    parser = PluginReference("builtin.parser.tr_f", "1.0.0", "1", {"delimiter": ","})
    calibration = PluginReference(
        "builtin.calibration.linear", "1.0.0", "1", {"K": 2.0, "B": 0.0}
    )
    analyzer = PluginReference("builtin.analyzer.thrust", "1.0.0", "1", {})
    document = ProjectDocument(
        source_path=str(raw),
        source_hash=Project_SourceHash(raw),
        parser=parser,
        calibration=calibration,
        processors=(
            PluginReference("builtin.processor.vertical_linear_baseline", "1.0.0", "1", {}),
        ),
        thrust_polarity=-1,
        regions={"pre": (0.0, 0.1), "burn": (0.2, 0.8), "post": (0.9, 1.0)},
        analyzer=analyzer,
        motor_metadata={"propellant_mass_kg": 0.1},
        export_settings={"eng": False},
        locale="en_US",
        diagnostics=(Diagnostic(DiagnosticSeverity.INFO, "test", "test"),),
    )
    destination = tmp_path / "project.json"
    Project_Save(document, destination)
    assert Project_Load(destination) == document
    assert len(document.source_hash) == 64
    assert document.to_dict()["thrust_polarity"] == -1


def test_project_migrates_legacy_processor_sign_to_thrust_polarity() -> None:
    document = ProjectDocument(
        processors=(
            PluginReference(
                "builtin.processor.vertical_linear_baseline",
                "1.0.0",
                "1",
                {"enabled": True, "sign": -1},
            ),
        ),
    )
    payload = document.to_dict()
    payload.pop("thrust_polarity")
    migrated = ProjectDocument.from_dict(payload)
    assert migrated.thrust_polarity == -1
    assert migrated.processors[0].config == {"enabled": True}
    assert migrated.to_dict()["schema"] == PROJECT_SCHEMA


def test_incomplete_project_round_trip(tmp_path: Path) -> None:
    parser = PluginReference(
        "builtin.parser.tr_f",
        "1.0.0",
        "1",
        {"delimiter": ",", "time_unit": "s", "invalid_row_policy": "skip"},
    )
    document = ProjectDocument(
        parser=parser,
        calibration=None,
        processors=(),
        regions={},
        analyzer=None,
        export_settings={
            "directory": None,
            "selected_exporter_ids": ["builtin.exporter.thrust_png"],
            "openrocket_exporter_id": "builtin.exporter.openrocket_eng",
        },
        workflow_state={
            "parsed": False,
            "calibrated": False,
            "processed": False,
            "analyzed": False,
        },
    )
    destination = tmp_path / "Incomplete.retldc.json"
    Project_Save(document, destination)
    loaded = Project_Load(destination)
    assert loaded == document
    assert loaded.source_path is None
    assert loaded.parser == parser
    assert loaded.analyzer is None


def test_project_source_resolution_valid_missing_relocated_and_mismatch(
    tmp_path: Path,
) -> None:
    original_directory = tmp_path / "original"
    original_directory.mkdir()
    source = original_directory / "TEST_SD.TXT"
    source.write_text("0,0\n1,2\n", encoding="utf-8")
    expected_hash = Project_SourceHash(source)
    document = ProjectDocument(
        source_path=str(source),
        source_hash=expected_hash,
    )
    found = Project_SourceResolve(document)
    assert found.result is ProjectSourceResolveResult.FOUND
    assert found.path == source.resolve()

    relocated_directory = tmp_path / "relocated"
    relocated_directory.mkdir()
    relocated = relocated_directory / source.name
    source.rename(relocated)
    missing = Project_SourceResolve(document)
    assert missing.result is ProjectSourceResolveResult.MISSING

    resolved = Project_SourceResolve(document, relocated_source=relocated)
    assert resolved.result is ProjectSourceResolveResult.RELOCATED
    assert resolved.path == relocated.resolve()
    relocated.write_text("0,999\n1,2\n", encoding="utf-8")
    mismatch = Project_SourceResolve(document, relocated_source=relocated)
    assert mismatch.result is ProjectSourceResolveResult.HASH_MISMATCH
    assert mismatch.actual_hash != expected_hash


def test_saved_project_default_export_directory() -> None:
    project = Path("D:/tests/Test_001.retldc.json")
    assert Project_DefaultExportDirectory(project) == Path(
        "D:/tests/Test_001_exports"
    )


def test_project_round_trip_preserves_multiple_sources_and_stream_offsets(
    tmp_path: Path,
) -> None:
    parser = PluginReference("builtin.parser.tr_f", "1.0.0", "1", {})
    document = ProjectDocument(
        sources=(
            ProjectSourceState("source_1", "D:/data/thrust.txt", "a" * 64, parser),
            ProjectSourceState("source_2", "D:/data/pressure.txt", "b" * 64, parser),
        ),
        streams=(
            ProjectStreamState("stream_1", "source_1", 0.0, "Thrust"),
            ProjectStreamState("stream_2", "source_2", -1.25, "Pressure"),
        ),
    )
    destination = tmp_path / "multi.retldc.json"
    Project_Save(document, destination)
    loaded = Project_Load(destination)
    assert loaded == document
    assert loaded.streams[1].time_offset_s == -1.25


def test_legacy_project_without_workflow_state_infers_completed_stages(
    tmp_path: Path,
) -> None:
    source = tmp_path / "raw.txt"
    source.write_text("0,0\n1,1\n", encoding="utf-8")
    document = ProjectDocument(
        source_path=str(source),
        source_hash=Project_SourceHash(source),
        parser=PluginReference("builtin.parser.tr_f", "1.0.0", "1", {}),
        calibration=PluginReference("builtin.calibration.identity", "1.0.0", "1", {}),
        processors=(PluginReference("processor", "1.0.0", "1", {}),),
        regions={"pre": (0.0, 0.1), "burn": (0.2, 0.8), "post": (0.9, 1.0)},
        analyzer=PluginReference("analyzer", "1.0.0", "1", {}),
    )
    payload = document.to_dict()
    payload.pop("workflow_state")
    loaded = ProjectDocument.from_dict(payload)
    assert loaded.workflow_state == {
        "parsed": True,
        "calibrated": True,
        "processed": True,
        "analyzed": True,
    }


def test_project_v2_preserves_source_tabular_mapping_and_reads_v1() -> None:
    mapping = {
        "sheet_name": "Sheet1",
        "header_row": 1,
        "data_start_row": 2,
        "time": {"mode": "column", "column": 0, "unit": "s"},
        "columns": [
            {"column": 0, "usage": "time", "unit": "s"},
            {
                "column": 1,
                "usage": "data",
                "channel_id": "pc",
                "quantity": "pressure",
                "role": "chamber_pressure",
                "unit": "MPa",
                "expected_header": "Pc",
            },
        ],
    }
    parser = PluginReference(
        "builtin.parser.generic_xlsx",
        "1.0.0",
        "1",
        mapping,
    )
    document = ProjectDocument(
        sources=(ProjectSourceState("source_1", "D:/data/result.xlsx", None, parser),),
        streams=(ProjectStreamState("stream_1", "source_1"),),
        parser=parser,
    )
    payload = document.to_dict()
    assert payload["schema"] == PROJECT_SCHEMA == "underline-retldc-project/2"
    assert ProjectDocument.from_dict(payload).sources[0].parser == parser

    payload["schema"] = "underline-retldc-project/1"
    migrated = ProjectDocument.from_dict(payload)
    assert migrated.sources[0].parser is not None
    assert migrated.sources[0].parser.config["columns"][1]["channel_id"] == "pc"
    assert migrated.to_dict()["schema"] == PROJECT_SCHEMA
