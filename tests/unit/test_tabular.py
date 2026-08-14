from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from underline_retldc.core.tabular import (
    Tabular_MappingApply,
    Tabular_MappingSuggest,
    Tabular_PreviewBuild,
    TabularPreset,
    TabularPreset_Load,
    TabularPreset_Save,
    TabularTable,
)


def _manual_config(*, time: dict | None = None) -> dict:
    return {
        "header_row": 1,
        "data_start_row": 2,
        "data_end_row": None,
        "time": time or {"mode": "column", "column": 0, "unit": "s"},
        "invalid_row_policy": "preserve",
        "columns": [
            {
                "column": 0,
                "usage": "time",
                "unit": "s",
                "expected_header": "T0",
            },
            {
                "column": 1,
                "usage": "data",
                "display_name": "Pressure",
                "channel_id": "pressure_a",
                "quantity": "pressure",
                "role": "chamber_pressure",
                "unit": "MPa",
                "expected_header": "CH_A",
            },
            {
                "column": 2,
                "usage": "data",
                "display_name": "Force",
                "channel_id": "force_b",
                "quantity": "force",
                "role": "thrust",
                "unit": "N",
                "expected_header": "CH_B",
            },
        ],
    }


def test_unknown_headers_parse_from_manual_mapping_by_column_index() -> None:
    table = TabularTable(
        {
            1: {0: "T0", 1: "CH_A", 2: "CH_B"},
            2: {0: "0.0", 1: "0.1", 2: "10"},
            3: {0: "0.15", 1: "0.2", 2: "20"},
        }
    )
    preview = Tabular_PreviewBuild(table, {"header_row": 1, "data_start_row": 2})
    suggestion = Tabular_MappingSuggest(
        preview, {"header_row": 1, "data_start_row": 2}
    )
    assert suggestion["time"]["mode"] == "none"

    dataset = Tabular_MappingApply(table, _manual_config())
    np.testing.assert_allclose(dataset.time, [0.0, 0.15])
    assert set(dataset.channels) == {"pressure_a", "force_b"}
    assert dataset.channel("pressure_a").semantic_role == "chamber_pressure"
    assert dataset.channel("pressure_a").data_unit == "MPa"
    assert dataset.channel("force_b").semantic_role == "thrust"
    assert dataset.channel("force_b").data_unit == "N"


def test_header_and_data_rows_ignore_columns_and_preserve_missing_alignment() -> None:
    table = TabularTable(
        {
            1: {0: "Laboratory note"},
            3: {0: "Clock", 1: "Signal", 2: "Remarks"},
            4: {0: "units", 1: "units"},
            5: {0: 0.0, 1: 1.0, 2: "start"},
            6: {0: 0.1, 1: None, 2: "missing"},
            7: {0: 0.25, 1: 3.0},
        }
    )
    config = {
        "header_row": 3,
        "data_start_row": 5,
        "time": {"mode": "column", "column": 0, "unit": "s"},
        "columns": [
            {"column": 0, "usage": "time", "expected_header": "Clock"},
            {
                "column": 1,
                "usage": "data",
                "channel_id": "signal",
                "quantity": "force",
                "unit": "N",
                "expected_header": "Signal",
            },
            {"column": 2, "usage": "ignore", "expected_header": "Remarks"},
        ],
    }
    dataset = Tabular_MappingApply(table, config)
    np.testing.assert_allclose(dataset.time, [0.0, 0.1, 0.25])
    np.testing.assert_allclose(
        dataset.channel("signal").values,
        [1.0, np.nan, 3.0],
        equal_nan=True,
    )
    assert {item.code for item in dataset.diagnostics} == {
        "tabular.channel_invalid_values"
    }


def test_header_none_time_column_sample_rate_and_period_modes() -> None:
    table = TabularTable(
        {
            1: {0: 5.0, 1: 10.0},
            2: {0: 5.2, 1: 20.0},
            3: {0: 5.5, 1: 30.0},
        }
    )
    base = {
        "header_row": None,
        "data_start_row": 1,
        "columns": [
            {
                "column": 1,
                "usage": "data",
                "channel_id": "force",
                "quantity": "force",
                "unit": "N",
            }
        ],
    }
    column_dataset = Tabular_MappingApply(
        table,
        {
            **base,
            "time": {"mode": "column", "column": 0, "unit": "s"},
        },
    )
    np.testing.assert_allclose(column_dataset.time, [5.0, 5.2, 5.5])

    rate_dataset = Tabular_MappingApply(
        table,
        {
            **base,
            "time": {"mode": "sample_rate", "sample_rate_hz": 20.0},
        },
    )
    np.testing.assert_allclose(rate_dataset.time, [0.0, 0.05, 0.1])

    period_dataset = Tabular_MappingApply(
        table,
        {
            **base,
            "time": {"mode": "sample_period", "sample_period_s": 0.2},
        },
    )
    np.testing.assert_allclose(period_dataset.time, [0.0, 0.2, 0.4])

    with pytest.raises(ValueError, match="No time source configured"):
        Tabular_MappingApply(table, {**base, "time": {"mode": "none"}})

    with pytest.raises(ValueError, match="only one Time column"):
        Tabular_MappingApply(
            table,
            {
                **base,
                "time": {"mode": "column", "column": 0, "unit": "s"},
                "columns": [
                    {"column": 0, "usage": "time", "unit": "s"},
                    {"column": 1, "usage": "time", "unit": "s"},
                ],
            },
        )


def test_preset_round_trip_uses_indices_and_warns_when_headers_change(
    tmp_path: Path,
) -> None:
    preset = TabularPreset(
        "Unknown Rig",
        "builtin.parser.generic_delimited",
        "1.0.0",
        {**_manual_config(), "delimiter": ",", "encoding": "utf-8-sig"},
    )
    destination = tmp_path / "unknown_rig_tabular_preset.json"
    TabularPreset_Save(preset, destination)
    loaded = TabularPreset_Load(destination)
    assert loaded == preset

    changed_headers = TabularTable(
        {
            1: {0: "t", 1: "Thrust_Output", 2: "Chamber_P"},
            2: {0: 0.0, 1: 99.0, 2: 12.0},
            3: {0: 0.1, 1: 101.0, 2: 15.0},
        }
    )
    dataset = Tabular_MappingApply(changed_headers, loaded.config)
    np.testing.assert_allclose(dataset.channel("pressure_a").values, [99.0, 101.0])
    np.testing.assert_allclose(dataset.channel("force_b").values, [12.0, 15.0])
    mismatches = [
        item for item in dataset.diagnostics if item.code == "tabular.header_hint_mismatch"
    ]
    assert len(mismatches) == 3

    too_narrow = TabularTable({1: {0: "t", 1: "only"}, 2: {0: 0.0, 1: 1.0}})
    with pytest.raises(ValueError, match="missing source column.*C"):
        Tabular_MappingApply(too_narrow, loaded.config)
