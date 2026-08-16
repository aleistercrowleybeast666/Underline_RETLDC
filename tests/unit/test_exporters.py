import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.gui.theme import Theme_Apply
from underline_retldc.plugin_api.common import TaskContext


@pytest.fixture(scope="module", autouse=True)
def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def export_plugins(bundled_registry):
    return {
        "analyzer": bundled_registry.get("builtin.analyzer.thrust"),
        "csv": bundled_registry.get("builtin.exporter.csv"),
        "json": bundled_registry.get("builtin.exporter.analysis_json"),
        "eng": bundled_registry.get("builtin.exporter.openrocket_eng"),
        "png": bundled_registry.get("builtin.exporter.thrust_png"),
        "text": bundled_registry.get("builtin.exporter.analysis_txt"),
        "pressure_csv": bundled_registry.get(
            "builtin.exporter.chamber_pressure_csv"
        ),
        "pressure_png": bundled_registry.get(
            "builtin.exporter.chamber_pressure_png"
        ),
        "temperature_csv": bundled_registry.get("builtin.exporter.temperature_csv"),
        "temperature_png": bundled_registry.get("builtin.exporter.temperature_png"),
    }


def _dataset() -> Dataset:
    return Dataset(
        time=np.array([0.0, 0.5, 1.0]),
        channels={
            "thrust_processed": Channel(
                "thrust_processed", "thrust", "N", [0.0, 10.0, 0.0], "processed"
            )
        },
    )


def test_csv_and_analysis_json_export(tmp_path: Path, export_plugins) -> None:
    dataset = _dataset()
    analysis = export_plugins["analyzer"].analyze(
        dataset,
        {"channel_id": "thrust_processed", "ignition": 0.0, "burnout": 1.0},
        TaskContext(),
    )
    csv_path = tmp_path / "curve.csv"
    json_path = tmp_path / "analysis.json"
    export_plugins["csv"].export(csv_path, dataset, analysis, {}, TaskContext())
    export_plugins["json"].export(
        json_path,
        dataset,
        analysis,
        {
            "thrust_polarity": -1,
            "processing_metadata": {
                "baseline_start": 0.0,
                "baseline_pre_source": "assumed_zero",
            }
        },
        TaskContext(),
    )
    assert "Corrected Thrust [N]" in csv_path.read_text(encoding="utf-8")
    assert '"underline-retldc-analysis/1"' in json_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["processing_metadata"]["baseline_pre_source"] == "assumed_zero"
    assert payload["thrust_polarity"] == -1
    assert payload["dataset"]["channels"]["thrust_processed"]["data_unit"] == "N"


def test_eng_writes_analyzed_shifted_curve_without_confirmation(
    tmp_path: Path, export_plugins
) -> None:
    dataset = _dataset()
    config = {
        "channel_id": "thrust_processed",
        "ignition": 0.0,
        "burnout": 1.0,
        "motor_designation": "T10",
        "diameter_mm": 24.0,
        "length_mm": 80.0,
        "delay_s": 0.0,
        "propellant_mass_kg": 0.05,
        "total_motor_mass_kg": 0.10,
        "manufacturer": "Underline",
    }
    destination = tmp_path / "motor.eng"
    result = export_plugins["eng"].export(
        destination, dataset, None, config, TaskContext()
    )
    lines = destination.read_text(encoding="ascii").splitlines()
    assert lines[1].startswith("T10 24 80 0 0.05 0.1 Underline")
    assert lines[2] == "0 0"
    assert result.metadata["ignition_shift_s"] == 0.0


def _offset_dataset() -> Dataset:
    return Dataset(
        time=np.array([10.0, 10.5, 11.0, 11.5, 12.0]),
        channels={
            "thrust_raw": Channel(
                "thrust_raw", "force", "raw", [900.0, 900.0, 900.0, 900.0, 900.0], "raw"
            ),
            "thrust_processed": Channel(
                "thrust_processed", "thrust", "N", [70.0, 0.0, 10.0, 0.0, 70.0], "processed"
            ),
        },
        metadata={"source_path": "D:/rocket/TEST_SD.TXT"},
    )


def _offset_analysis(dataset: Dataset, analyzer):
    return analyzer.analyze(
        dataset,
        {
            "channel_id": "thrust_processed",
            "ignition": 10.5,
            "burnout": 11.5,
            "propellant_mass_kg": 0.05,
        },
        TaskContext(),
    )


def test_png_uses_final_burn_curve_and_zero_time_origin(
    tmp_path: Path, export_plugins
) -> None:
    dataset = _offset_dataset()
    analysis = export_plugins["analyzer"].analyze(
        dataset,
        {
            "channel_id": "thrust_processed",
            "ignition": 10.25,
            "burnout": 11.75,
        },
        TaskContext(),
    )
    destination = tmp_path / "thrust_curve.png"
    result = export_plugins["png"].export(
        destination,
        dataset,
        analysis,
        {
            "channel_id": "thrust_processed",
            "ignition": 10.25,
            "burnout": 11.75,
            "title": "Regression Thrust Curve",
        },
        TaskContext(),
    )
    assert destination.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert destination.stat().st_size > 5_000
    assert result.metadata["source_channel_id"] == "thrust_processed"
    assert result.metadata["sample_count"] == 5
    assert result.metadata["time_start"] == 0.0
    assert result.metadata["time_end"] == 1.5
    assert result.metadata["interpolated_boundaries"] == ["ignition", "burnout"]


def test_text_summary_contains_provenance_metrics_and_final_table(
    tmp_path: Path, export_plugins
) -> None:
    dataset = _offset_dataset()
    analysis = _offset_analysis(dataset, export_plugins["analyzer"])
    destination = tmp_path / "analysis_summary.txt"
    config = {
        "channel_id": "thrust_processed",
        "ignition": 10.5,
        "burnout": 11.5,
        "project_name": "试车_001.retldc.json",
        "source_hash": "abc123",
        "thrust_polarity": -1,
        "motor_metadata": {
            "propellant_mass_kg": 0.05,
            "total_motor_mass_kg": 0.10,
        },
        "provenance": {
            "parser": {
                "id": "builtin.parser.tr_f",
                "version": "1.0.0",
                "config": {"delimiter": ","},
            },
            "calibration": {
                "id": "builtin.calibration.linear",
                "version": "1.0.0",
                "config": {"parameters": {"K": 1.0, "B": 0.0}},
            },
            "processor": {
                "id": "builtin.processor.vertical_linear_baseline",
                "version": "1.0.0",
                "config": {"enabled": True},
            },
            "analyzer": {
                "id": "builtin.analyzer.thrust",
                "version": "1.0.0",
                "config": {},
            },
        },
        "processing_metadata": {
            "baseline_start": 0.0,
            "baseline_end": 0.0,
            "baseline_pre_source": "assumed_zero",
            "baseline_post_source": "assumed_zero",
        },
    }
    result = export_plugins["text"].export(
        destination, dataset, analysis, config, TaskContext()
    )
    text = destination.read_text(encoding="utf-8")
    for expected in (
        "试车_001.retldc.json",
        "Peak Thrust [N]",
        "Average Thrust [N]",
        "Test Duration [s]",
        "Total Impulse [N s]",
        "Specific Impulse [s]",
        "Time to Peak [s]",
        "builtin.parser.tr_f",
        "builtin.calibration.linear",
        "builtin.processor.vertical_linear_baseline",
        "Thrust Polarity: Reversed (-1)",
        "Thrust Correction: Motor Weight-Change Compensation",
        "PRE Baseline Source: assumed_zero",
        "POST Baseline Source: assumed_zero",
        "Time(s)\tThrust(N)",
        "0\t0",
        "0.5\t10",
        "1\t0",
    ):
        assert expected in text
    assert "900" not in text
    assert result.metadata["source_channel_id"] == "thrust_processed"
    assert result.metadata["time_start"] == 0.0


def test_export_overwrites_fixed_name_without_numbered_copy(
    tmp_path: Path, export_plugins
) -> None:
    dataset = _offset_dataset()
    analysis = _offset_analysis(dataset, export_plugins["analyzer"])
    destination = tmp_path / "analysis_summary.txt"
    exporter = export_plugins["text"]
    base_config = {
        "ignition": 10.5,
        "burnout": 11.5,
        "channel_id": "thrust_processed",
    }
    first = exporter.export(
        destination,
        dataset,
        analysis,
        {**base_config, "project_name": "First"},
        TaskContext(),
    )
    first_text = destination.read_text(encoding="utf-8")
    second = exporter.export(
        destination,
        dataset,
        analysis,
        {**base_config, "project_name": "Second"},
        TaskContext(),
    )
    second_text = destination.read_text(encoding="utf-8")
    assert first.destination == second.destination == destination
    assert "Project Name: First" in first_text
    assert "Project Name: Second" in second_text
    assert list(tmp_path.iterdir()) == [destination]


def test_exporters_localize_chinese_output_content(
    tmp_path: Path, export_plugins
) -> None:
    dataset = _dataset()
    analysis = export_plugins["analyzer"].analyze(
        dataset,
        {"channel_id": "thrust_processed", "ignition": 0.0, "burnout": 1.0},
        TaskContext(),
    )
    config = {
        "channel_id": "thrust_processed",
        "ignition": 0.0,
        "burnout": 1.0,
        "output_locale": "zh_CN",
    }

    csv_path = tmp_path / "thrust_data_ZH.csv"
    export_plugins["csv"].export(csv_path, dataset, analysis, config, TaskContext())
    assert "时间 [s],已修正推力 [N]" in csv_path.read_text(encoding="utf-8")

    json_path = tmp_path / "analysis_data_ZH.json"
    result = export_plugins["json"].export(
        json_path, dataset, analysis, config, TaskContext()
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["output"]["locale"] == "zh_CN"
    assert payload["output"]["title"] == "火箭发动机试车数据分析"
    assert result.metadata["output_locale"] == "zh_CN"

    text_path = tmp_path / "analysis_summary_ZH.txt"
    export_plugins["text"].export(
        text_path, dataset, analysis, config, TaskContext()
    )
    summary = text_path.read_text(encoding="utf-8")
    assert "火箭发动机试车数据分析摘要" in summary
    assert "[试车区间]" in summary
    assert "时间(s)\t推力(N)" in summary

    png_path = tmp_path / "thrust_curve_ZH.png"
    result = export_plugins["png"].export(
        png_path, dataset, analysis, config, TaskContext()
    )
    assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result.metadata["output_locale"] == "zh_CN"
    assert result.metadata["title"] == "发动机推力曲线"


def test_formal_png_is_independent_of_gui_theme(
    tmp_path: Path, export_plugins
) -> None:
    app = QApplication.instance()
    assert app is not None
    dataset = _dataset()
    analysis = export_plugins["analyzer"].analyze(
        dataset,
        {"channel_id": "thrust_processed", "ignition": 0.0, "burnout": 1.0},
        TaskContext(),
    )
    config = {
        "channel_id": "thrust_processed",
        "ignition": 0.0,
        "burnout": 1.0,
        "output_locale": "en_US",
    }
    light_path = tmp_path / "light.png"
    dark_path = tmp_path / "dark.png"
    Theme_Apply(app, "light")
    light_result = export_plugins["png"].export(
        light_path, dataset, analysis, config, TaskContext()
    )
    Theme_Apply(app, "dark")
    export_plugins["png"].export(
        dark_path, dataset, analysis, config, TaskContext()
    )
    assert light_path.read_bytes() == dark_path.read_bytes()
    assert light_result.metadata["title"] == "Rocket Motor Thrust Curve"
    Theme_Apply(app, "light")


def test_pressure_and_temperature_exports_use_channel_semantics_and_skip_absent(
    tmp_path: Path, export_plugins
) -> None:
    dataset = Dataset(
        time=np.array([0.0, 0.5, 1.0]),
        channels={
            "thrust_processed": Channel(
                "thrust_processed", "force", "N", [0.0, 10.0, 0.0], "processed"
            ),
            "pc_calibrated": Channel(
                "pc_calibrated",
                "pressure",
                "MPa",
                [0.1, 2.0, 0.2],
                "calibrated",
                semantic_role="chamber_pressure",
                name="Pc",
            ),
            "wall_temp_calibrated": Channel(
                "wall_temp_calibrated",
                "temperature",
                "K",
                [300.0, 350.0, 340.0],
                "calibrated",
                semantic_role="chamber_wall_temperature",
                name="Wall temperature",
            ),
        },
    )
    config = {
        "output_locale": "en_US",
        "ignition": 0.0,
        "burnout": 1.0,
    }
    pressure_csv = tmp_path / "chamber_pressure_data_EN.csv"
    pressure_png = tmp_path / "chamber_pressure_curve_EN.png"
    temperature_csv = tmp_path / "temperature_data_EN.csv"
    temperature_png = tmp_path / "temperature_curve_EN.png"
    results = {}
    for key, destination in (
        ("pressure_csv", pressure_csv),
        ("pressure_png", pressure_png),
        ("temperature_csv", temperature_csv),
        ("temperature_png", temperature_png),
    ):
        result = export_plugins[key].export(
            destination, dataset, None, config, TaskContext()
        )
        results[key] = result
        assert result.metadata["write_result"] == "written"
        assert destination.is_file()
    assert results["pressure_png"].metadata["active_interval"] == [0.0, 1.0]
    assert results["pressure_png"].metadata["cropped_to_active_test"] is True
    assert "Pc [MPa]" in pressure_csv.read_text(encoding="utf-8")
    assert "Wall temperature [K]" in temperature_csv.read_text(encoding="utf-8")
    assert pressure_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert temperature_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    analysis = export_plugins["analyzer"].analyze(
        dataset,
        {"channel_id": "thrust_processed", "ignition": 0.0, "burnout": 1.0},
        TaskContext(),
    )
    summary_path = tmp_path / "analysis_summary_EN.txt"
    export_plugins["text"].export(
        summary_path,
        dataset,
        analysis,
        {**config, "channel_id": "thrust_processed"},
        TaskContext(),
    )
    summary = summary_path.read_text(encoding="utf-8")
    for expected_metric in (
        "Chamber Pressure at Test Start [MPa]: 0.1",
        "Peak Chamber Pressure [MPa]: 2",
        "Mean Active Chamber Pressure [MPa]",
        "Temperature at Test Start [K]: 300",
        "Active Max [K]: 350",
        "Full Record Max [K]: 350",
        "Time of Max [s]: 0.5",
    ):
        assert expected_metric in summary

    absent = _dataset()
    stale = tmp_path / "temperature_data_absent_EN.csv"
    stale.write_text("stale", encoding="utf-8")
    skipped = export_plugins["temperature_csv"].export(
        stale, absent, None, config, TaskContext()
    )
    assert skipped.metadata["write_result"] == "skipped_no_channel"
    assert not stale.exists()


def test_export_option_filenames_match_engineering_outputs(export_plugins) -> None:
    expected = {
        "csv": "thrust_data.csv",
        "pressure_csv": "chamber_pressure_data.csv",
        "temperature_csv": "temperature_data.csv",
        "png": "thrust_curve.png",
        "pressure_png": "chamber_pressure_curve.png",
        "temperature_png": "temperature_curve.png",
        "text": "analysis_summary.txt",
        "json": "analysis_data.json",
        "eng": "motor.eng",
    }
    for key, filename in expected.items():
        schema = export_plugins[key].config_schema()
        assert schema["x-underline-retldc-export"]["filename"] == filename
