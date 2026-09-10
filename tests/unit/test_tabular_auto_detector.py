from __future__ import annotations

from underline_retldc.core.tabular import TabularPreview
from underline_retldc.core.tabular_auto_detector import TabularAutoDetector


def _preview(rows: list[list[object]]) -> TabularPreview:
    width = max(len(row) for row in rows)
    return TabularPreview(
        headers=tuple("" for _ in range(width)),
        rows=tuple(
            tuple(str(row[column]) if column < len(row) else "" for column in range(width))
            for row in rows
        ),
        row_numbers=tuple(range(1, len(rows) + 1)),
        column_count=width,
    )


def _categories(rows: list[list[object]]) -> tuple[str, ...]:
    result = TabularAutoDetector().detect(_preview(rows))
    assert result.can_parse, result.blocking_reason
    return tuple(item.suggested_user_category for item in result.column_suggestions)


def test_auto_detector_time_pc_force() -> None:
    rows = [["Time (s)", "Pc (MPa)", "F (N)"]]
    rows.extend([[index * 0.01, index * 0.2, index * 10.0] for index in range(6)])
    result = TabularAutoDetector().detect(_preview(rows))
    assert result.header_row == 1
    assert result.data_start_row == 2
    assert result.time_config == {"mode": "column", "column": 0, "unit": "s"}
    assert tuple(item.suggested_user_category for item in result.column_suggestions) == (
        "time",
        "chamber_pressure",
        "thrust",
    )


def test_auto_detector_chinese_extra_columns_remain_other() -> None:
    rows = [["时间 t (s)", "室压 Pc (MPa)", "推力 F (N)", "已燃肉厚 e", "燃面面积 Ab", "燃喷比 Kn"]]
    rows.extend(
        [
            [index, index + 1, index + 2, index + 3, index + 4, index + 5]
            for index in range(6)
        ]
    )
    assert _categories(rows) == (
        "time",
        "chamber_pressure",
        "thrust",
        "other",
        "other",
        "other",
    )


def test_auto_detector_unknown_numeric_columns_remain_other() -> None:
    rows = [["t", "A", "B", "C"]]
    rows.extend([[index * 0.1, 100 + index, 200 + index, 300 + index] for index in range(6)])
    assert _categories(rows) == ("time", "other", "other", "other")


def test_auto_detector_temperature_requires_header_or_unit() -> None:
    rows = [["Time", "TC1 (degC)", "Temperature (K)", "Kn"]]
    rows.extend([[index, 20 + index, 293 + index, 30 + index] for index in range(6)])
    assert _categories(rows) == ("time", "temperature", "temperature", "other")


def test_auto_detector_skips_top_notes_and_finds_header() -> None:
    rows = [
        ["Engine: Example"],
        ["Date: 2026-08-01"],
        ["Operator note"],
        ["Time", "Pc", "F"],
    ]
    rows.extend([[index * 0.01, index, index * 2] for index in range(6)])
    result = TabularAutoDetector().detect(_preview(rows))
    assert result.can_parse
    assert result.header_row == 4
    assert result.data_start_row == 5


def test_auto_detector_twenty_extra_columns_do_not_block() -> None:
    headers = ["Time", "Pc", "F", *(f"X{index}" for index in range(20))]
    rows: list[list[object]] = [headers]
    rows.extend(
        [
            [index * 0.1, index, index * 2, *(index + extra for extra in range(20))]
            for index in range(6)
        ]
    )
    result = TabularAutoDetector().detect(_preview(rows))
    assert result.can_parse
    categories = tuple(item.suggested_user_category for item in result.column_suggestions)
    assert categories[:3] == ("time", "chamber_pressure", "thrust")
    assert categories[3:] == ("other",) * 20


def test_auto_detector_requires_explicit_time_when_no_header() -> None:
    rows = [[index, index * 2, index * 3] for index in range(8)]
    result = TabularAutoDetector().detect(_preview(rows))
    assert not result.can_parse
    assert result.blocking_reason
    assert result.diagnostics[0].code == "tabular.auto_time_missing"


def test_auto_detector_rejects_ambiguous_time_columns() -> None:
    rows = [["Time", "Timestamp", "F"]]
    rows.extend([[index * 0.1, index * 0.1, index * 2] for index in range(8)])
    result = TabularAutoDetector().detect(_preview(rows))
    assert not result.can_parse
    assert result.diagnostics[0].code == "tabular.auto_time_ambiguous"


def test_auto_detector_mapping_preserves_other_channels() -> None:
    rows = [["t", "A", "B", "C"]]
    rows.extend([[index * 0.1, index, index + 1, index + 2] for index in range(6)])
    result = TabularAutoDetector().detect(_preview(rows))
    config = result.mapping_config()
    assert [item["usage"] for item in config["columns"]] == ["time", "data", "data", "data"]
    assert [item.get("role") for item in config["columns"][1:]] == [
        "auxiliary",
        "auxiliary",
        "auxiliary",
    ]
