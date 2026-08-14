import zipfile
from pathlib import Path

import numpy as np
import pytest

from underline_retldc.core.data_quality import Dataset_QualityInspect
from underline_retldc.core.defaults import FACTORY_DEFAULTS
from underline_retldc.core.parser_selection import (
    ParserSelection_Decide,
    ParserSelectionResult,
)
from underline_retldc.core.pipeline import Calibration_ApplyIdentityDefaults
from underline_retldc.core.tabular import Tabular_MappingSuggest
from underline_retldc.core.units import UnitSource
from underline_retldc.plugin_api.common import ProbeContext, TaskContext


def test_tr_f_valid_fixture_is_parsed_without_calibration(bundled_registry) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = Path(__file__).parents[1] / "data" / "valid_tr_f.txt"
    result = parser.parse(source, {}, TaskContext())

    assert result.dataset.sample_count == 4
    assert result.dataset.time_unit == "s"
    assert result.dataset.channel("thrust_raw").unit == "raw"
    assert result.dataset.channel("thrust_raw").semantic_role == "thrust"
    np.testing.assert_allclose(result.dataset.time, [0.0, 0.01, 0.02, 0.03])
    np.testing.assert_allclose(result.dataset.channel("thrust_raw").values, [0, 2, 5, 0])
    assert not result.dataset.time.flags.writeable
    assert not result.dataset.channel("thrust_raw").values.flags.writeable


def test_tr_f_probe_is_bounded_and_confident(bundled_registry) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = Path(__file__).parents[1] / "data" / "valid_tr_f.txt"
    probe = parser.probe(source, ProbeContext(max_bytes=128, max_records=4))
    assert probe.confidence > 0.9
    assert "numeric two-column" in probe.reason


@pytest.mark.parametrize(
    ("plugin_id", "channel_id", "quantity", "semantic_role", "source_format"),
    (
        ("builtin.parser.tr_f", "thrust_raw", "force", "thrust", "TR_F/1"),
        (
            "builtin.parser.tr_p",
            "pressure_raw",
            "pressure",
            "chamber_pressure",
            "TR_P/1",
        ),
        (
            "builtin.parser.tr_t",
            "temperature_raw",
            "temperature",
            "temperature",
            "TR_T/1",
        ),
    ),
)
def test_two_column_parser_variants_declare_distinct_semantics(
    bundled_registry,
    plugin_id: str,
    channel_id: str,
    quantity: str,
    semantic_role: str,
    source_format: str,
) -> None:
    source = Path(__file__).parents[1] / "data" / "valid_tr_f.txt"
    dataset = bundled_registry.get(plugin_id).parse(
        source,
        {},
        TaskContext(),
    ).dataset
    channel = dataset.channel(channel_id)
    assert channel.quantity == quantity
    assert channel.semantic_role == semantic_role
    assert channel.data_unit == "raw"
    assert dataset.metadata["source_format"] == source_format
    np.testing.assert_allclose(dataset.time, [0.0, 0.01, 0.02, 0.03])


def test_identical_two_column_probes_require_explicit_parser_choice(
    bundled_registry,
) -> None:
    source = Path(__file__).parents[1] / "data" / "valid_tr_f.txt"
    plugin_ids = (
        "builtin.parser.tr_f",
        "builtin.parser.tr_p",
        "builtin.parser.tr_t",
    )
    results = tuple(
        (
            bundled_registry.get(plugin_id),
            bundled_registry.get(plugin_id).probe(source, ProbeContext()),
        )
        for plugin_id in plugin_ids
    )
    decision = ParserSelection_Decide(
        results,
        threshold=FACTORY_DEFAULTS.parser_auto_select_threshold,
        ambiguity_margin=FACTORY_DEFAULTS.parser_auto_select_margin,
    )
    assert decision.result is ParserSelectionResult.AMBIGUOUS
    assert decision.parser is None
    assert {
        plugin.descriptor.plugin_id for plugin, _probe in decision.candidates
    } == set(plugin_ids)


def test_tr_f_empty_file_fails(tmp_path: Path, bundled_registry) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "empty.txt"
    source.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no valid records"):
        parser.parse(source, {}, TaskContext())


def test_tr_f_malformed_and_extra_columns_are_diagnosed(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "mixed.txt"
    source.write_text("0,1\nbad,row\n1,2,3\n2,4\n", encoding="utf-8")
    result = parser.parse(source, {}, TaskContext())
    assert result.dataset.sample_count == 2
    malformed = [item for item in result.diagnostics if item.code == "tr_f.malformed_row"]
    assert [item.line for item in malformed] == [2, 3]
    assert result.dataset.metadata["malformed_rows"] == 2


def test_tr_f_strict_invalid_policy_fails_at_line(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "strict.txt"
    source.write_text("0,1\ninvalid\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r":2:"):
        parser.parse(source, {"invalid_row_policy": "error"}, TaskContext())


def test_tr_f_explicit_millisecond_unit_is_normalized_to_seconds(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "milliseconds.txt"
    source.write_text("0,0\n10,1\n20,0\n", encoding="utf-8")
    dataset = parser.parse(
        source,
        {"time_unit": "ms", "delimiter": ",", "invalid_row_policy": "skip"},
        TaskContext(),
    ).dataset
    assert dataset.time_unit == "s"
    assert dataset.metadata["source_time_unit"] == "ms"
    np.testing.assert_allclose(dataset.time, [0.0, 0.01, 0.02])


def test_timestamp_anomalies_and_gap_are_reported(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "timing.txt"
    source.write_text("0,0\n1,1\n1,2\n0.5,3\n20,4\n", encoding="utf-8")
    dataset = parser.parse(source, {}, TaskContext()).dataset
    report = Dataset_QualityInspect(dataset)
    assert report.duplicate_timestamps == 1
    assert report.backward_timestamps == 1
    assert report.large_gaps == 1
    codes = {item.code for item in dataset.diagnostics}
    assert {"time.duplicate", "time.backward", "time.large_gap"} <= codes


def test_large_tr_f_reports_progress_without_tell_failure(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "large.txt"
    source.write_text(
        "".join(f"{index / 1000:.6f},{index}\n" for index in range(2500)),
        encoding="utf-8",
    )
    progress: list[float] = []
    result = parser.parse(
        source,
        {},
        TaskContext(progress_callback=lambda value, _message: progress.append(value)),
    )
    assert result.dataset.sample_count == 2500
    assert progress[-1] == 1.0
    assert any(value < 1.0 for value in progress)


def _xlsx_fixture_write(
    destination: Path,
    *,
    headers: tuple[str, ...] = (
        "时间 t (s)",
        "室压 Pc (MPa)",
        "推力 F (N)",
        "已燃肉厚 e (mm)",
        "燃面面积 Ab (mm²)",
        "燃喷比 Kn",
    ),
    rows: tuple[tuple[float, ...], ...] = (
        (0.0, 0.0, 0.0, 0.0, 10.0, 1.0),
        (0.1, 1.5, 20.0, 0.4, 11.0, 1.1),
        (0.2, 0.0, 0.0, 0.8, 12.0, 1.2),
    ),
) -> None:
    header_cells = "".join(
        f'<c r="{chr(65 + index)}1" t="inlineStr"><is><t>{header}</t></is></c>'
        for index, header in enumerate(headers)
    )
    data_rows = []
    for row_index, row in enumerate(rows, start=2):
        cells = "".join(
            f'<c r="{chr(65 + column)}{row_index}"><v>{value}</v></c>'
            for column, value in enumerate(row)
        )
        data_rows.append(f'<row r="{row_index}">{cells}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData><row r="1">{header_cells}</row>{"".join(data_rows)}</sheetData>'
        '</worksheet>'
    )
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '</Types>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Result" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def test_generic_xlsx_preserves_explicit_units_and_multiple_channels(
    tmp_path: Path, bundled_registry
) -> None:
    source = tmp_path / "结果.xlsx"
    _xlsx_fixture_write(source)
    parser = bundled_registry.get("builtin.parser.generic_xlsx")
    assert parser.probe(source, ProbeContext()).confidence >= 0.99
    base_config = {"header_row": 1, "data_start_row": 2}
    preview = parser.preview(source, base_config)
    assert preview.selected_sheet == "Result"
    config = Tabular_MappingSuggest(preview, base_config)
    dataset = parser.parse(source, config, TaskContext()).dataset

    assert dataset.sample_count == 3
    assert set(dataset.channels) == {"pc", "f", "e", "ab", "kn"}
    expected = {
        "pc": ("pressure", "MPa", "chamber_pressure"),
        "f": ("force", "N", "thrust"),
        "e": ("length", "mm", "auxiliary"),
        "ab": ("area", "mm²", "auxiliary"),
        "kn": ("kn", "1", "auxiliary"),
    }
    for channel_id, (quantity, unit, semantic_role) in expected.items():
        channel = dataset.channel(channel_id)
        assert channel.quantity == quantity
        assert channel.data_unit == unit
        assert channel.semantic_role == semantic_role
    assert dataset.channel("pc").unit_source is UnitSource.PLUGIN_DECLARED
    assert dataset.channel("kn").unit_source is UnitSource.DEFAULT_SI

    calibrated, outputs = Calibration_ApplyIdentityDefaults(
        dataset, bundled_registry.get("builtin.calibration.identity")
    )
    assert len(outputs) == 5
    for input_id, output_id in outputs.items():
        np.testing.assert_array_equal(
            calibrated.channel(output_id).values, dataset.channel(input_id).values
        )
        assert calibrated.channel(output_id).data_unit == dataset.channel(input_id).data_unit


def test_generic_xlsx_unknown_headers_use_explicit_manual_mapping(
    tmp_path: Path, bundled_registry
) -> None:
    source = tmp_path / "unknown.xlsx"
    _xlsx_fixture_write(
        source,
        headers=("T0", "CH_A", "CH_B"),
        rows=((0.0, 0.1, 10.0), (0.05, 0.2, 20.0)),
    )
    original = source.read_bytes()
    parser = bundled_registry.get("builtin.parser.generic_xlsx")
    config = {
        "sheet_name": "Result",
        "header_row": 1,
        "data_start_row": 2,
        "time": {"mode": "column", "column": 0, "unit": "s"},
        "columns": [
            {"column": 0, "usage": "time", "expected_header": "T0"},
            {
                "column": 1,
                "usage": "data",
                "channel_id": "pc_manual",
                "display_name": "Pressure",
                "quantity": "pressure",
                "role": "chamber_pressure",
                "unit": "MPa",
                "expected_header": "CH_A",
            },
            {
                "column": 2,
                "usage": "data",
                "channel_id": "force_manual",
                "display_name": "Force",
                "quantity": "force",
                "role": "thrust",
                "unit": "N",
                "expected_header": "CH_B",
            },
        ],
    }
    dataset = parser.parse(source, config, TaskContext()).dataset
    np.testing.assert_allclose(dataset.time, [0.0, 0.05])
    assert dataset.channel("pc_manual").semantic_role == "chamber_pressure"
    assert dataset.channel("force_manual").semantic_role == "thrust"
    assert source.read_bytes() == original


def test_generic_delimited_supports_auto_delimiter_late_header_and_missing_values(
    tmp_path: Path, bundled_registry
) -> None:
    source = tmp_path / "rig.csv"
    source.write_text(
        "Laboratory export\nClock,P1,F_OUT,Notes\nunits,MPa,N,text\n"
        "0.00,0.1,10,start\n0.05,,20,missing\n0.11,0.3,30,end\n",
        encoding="utf-8",
    )
    original = source.read_bytes()
    parser = bundled_registry.get("builtin.parser.generic_delimited")
    base = {
        "delimiter": "auto",
        "encoding": "auto",
        "header_row": 2,
        "data_start_row": 4,
    }
    preview = parser.preview(source, base)
    assert preview.resolved_reader_config["delimiter"] == ","
    config = {
        **base,
        **dict(preview.resolved_reader_config),
        "time": {"mode": "column", "column": 0, "unit": "s"},
        "columns": [
            {"column": 0, "usage": "time", "expected_header": "Clock"},
            {
                "column": 1,
                "usage": "data",
                "channel_id": "pressure",
                "quantity": "pressure",
                "role": "chamber_pressure",
                "unit": "MPa",
                "expected_header": "P1",
            },
            {
                "column": 2,
                "usage": "data",
                "channel_id": "force",
                "quantity": "force",
                "role": "thrust",
                "unit": "N",
                "expected_header": "F_OUT",
            },
            {"column": 3, "usage": "ignore", "expected_header": "Notes"},
        ],
    }
    dataset = parser.parse(source, config, TaskContext()).dataset
    np.testing.assert_allclose(dataset.time, [0.0, 0.05, 0.11])
    np.testing.assert_allclose(
        dataset.channel("pressure").values,
        [0.1, np.nan, 0.3],
        equal_nan=True,
    )
    np.testing.assert_allclose(dataset.channel("force").values, [10.0, 20.0, 30.0])
    assert source.read_bytes() == original
