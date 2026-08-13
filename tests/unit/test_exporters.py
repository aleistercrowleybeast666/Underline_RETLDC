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
    export_plugins["json"].export(json_path, dataset, analysis, {}, TaskContext())
    assert "Corrected Thrust [N]" in csv_path.read_text(encoding="utf-8")
    assert '"underline-retldc-analysis/1"' in json_path.read_text(encoding="utf-8")


def test_eng_requires_confirmation_and_writes_shifted_curve(
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
    with pytest.raises(ValueError, match="Confirm"):
        export_plugins["eng"].export(
            tmp_path / "motor.eng", dataset, None, config, TaskContext()
        )
    config["curve_confirmed"] = True
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
                "config": {"enabled": True, "sign": 1},
            },
            "analyzer": {
                "id": "builtin.analyzer.thrust",
                "version": "1.0.0",
                "config": {},
            },
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

    csv_path = tmp_path / "processed_thrust_ZH.csv"
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
