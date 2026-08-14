from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.units import Unit_ConvertValues, Unit_Definition, Unit_Normalize
from underline_retldc.core.workspace_capabilities import (
    WorkspaceCapabilities_Default,
    WorkspaceChannelCapabilityRegistry,
)

TABULAR_PRESET_SCHEMA = "underline-retldc-tabular-preset/1"


class TabularColumnUsage(StrEnum):
    TIME = "time"
    DATA = "data"
    IGNORE = "ignore"
    METADATA = "metadata"


class TabularTimeMode(StrEnum):
    NONE = "none"
    COLUMN = "column"
    SAMPLE_RATE = "sample_rate"
    SAMPLE_PERIOD = "sample_period"


class TabularInvalidValuePolicy(StrEnum):
    PRESERVE = "preserve"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TabularTable:
    """Sparse, read-only, one-based source rows with zero-based columns."""

    rows: Mapping[int, Mapping[int, Any]]

    def __post_init__(self) -> None:
        normalized: dict[int, Mapping[int, Any]] = {}
        for raw_row_number, raw_row in self.rows.items():
            row_number = int(raw_row_number)
            if row_number < 1:
                raise ValueError("Tabular source row numbers must be one-based")
            if not isinstance(raw_row, Mapping):
                raise ValueError("Every Tabular source row must be a column mapping")
            row: dict[int, Any] = {}
            for raw_column, value in raw_row.items():
                column = int(raw_column)
                if column < 0:
                    raise ValueError("Tabular source columns must be zero-based")
                row[column] = value
            normalized[row_number] = MappingProxyType(row)
        object.__setattr__(self, "rows", MappingProxyType(normalized))

    @property
    def column_count(self) -> int:
        return max(
            (
                max(row, default=-1) + 1
                for row in self.rows.values()
            ),
            default=0,
        )

    @property
    def last_row_number(self) -> int:
        return max(self.rows, default=0)

    def cell(self, row_number: int, column: int) -> Any:
        return self.rows.get(int(row_number), {}).get(int(column))

    def header(self, row_number: int | None, column: int) -> str:
        if row_number is None:
            return ""
        value = self.cell(row_number, column)
        return "" if value is None else str(value).strip()


@dataclass(frozen=True, slots=True)
class TabularPreview:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    row_numbers: tuple[int, ...]
    column_count: int
    sheet_names: tuple[str, ...] = ()
    selected_sheet: str | None = None
    resolved_reader_config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.column_count < 0:
            raise ValueError("Tabular preview column_count must not be negative")
        if len(self.headers) != self.column_count:
            raise ValueError("Tabular preview header width does not match column_count")
        if len(self.rows) != len(self.row_numbers):
            raise ValueError("Tabular preview rows and row numbers must align")
        if any(len(row) != self.column_count for row in self.rows):
            raise ValueError("Tabular preview row width does not match column_count")
        object.__setattr__(
            self,
            "resolved_reader_config",
            MappingProxyType(dict(self.resolved_reader_config)),
        )


@dataclass(frozen=True, slots=True)
class TabularTimeConfig:
    mode: TabularTimeMode = TabularTimeMode.NONE
    column: int | None = None
    unit: str = "s"
    sample_rate_hz: float | None = None
    sample_period_s: float | None = None


@dataclass(frozen=True, slots=True)
class TabularColumnMapping:
    column: int
    usage: TabularColumnUsage
    channel_id: str | None = None
    display_name: str | None = None
    quantity: str | None = None
    semantic_role: str | None = None
    unit: str | None = None
    expected_header: str | None = None


@dataclass(frozen=True, slots=True)
class TabularMappingConfig:
    header_row: int | None
    data_start_row: int
    data_end_row: int | None
    time: TabularTimeConfig
    columns: tuple[TabularColumnMapping, ...]
    invalid_value_policy: TabularInvalidValuePolicy = TabularInvalidValuePolicy.PRESERVE


@dataclass(frozen=True, slots=True)
class TabularPreset:
    name: str
    parser_id: str
    parser_version: str
    config: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Tabular Preset name must not be empty")
        if not self.parser_id.strip() or not self.parser_version.strip():
            raise ValueError("Tabular Preset Parser ID and version must not be empty")
        copied = _json_copy(dict(self.config))
        Tabular_ConfigNormalize(copied)
        object.__setattr__(self, "config", MappingProxyType(copied))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TABULAR_PRESET_SCHEMA,
            "name": self.name,
            "parser_id": self.parser_id,
            "parser_version": self.parser_version,
            "config": _json_copy(dict(self.config)),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TabularPreset:
        if payload.get("schema") != TABULAR_PRESET_SCHEMA:
            raise ValueError(f"Unsupported Tabular Preset schema: {payload.get('schema')!r}")
        config = payload.get("config")
        if not isinstance(config, Mapping):
            raise ValueError("Tabular Preset config must be an object")
        return cls(
            name=str(payload.get("name", "")),
            parser_id=str(payload.get("parser_id", "")),
            parser_version=str(payload.get("parser_version", "")),
            config=dict(config),
        )


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def TabularPreset_Save(preset: TabularPreset, destination: Path) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(preset.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def TabularPreset_Load(source: Path) -> TabularPreset:
    try:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load Tabular Preset {source}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("Tabular Preset root must be an object")
    return TabularPreset.from_dict(payload)


def Tabular_ColumnLabel(column: int) -> str:
    value = int(column)
    if value < 0:
        raise ValueError("Tabular column must not be negative")
    label = ""
    while True:
        value, remainder = divmod(value, 26)
        label = chr(ord("A") + remainder) + label
        if value == 0:
            return label
        value -= 1


def Tabular_PreviewBuild(
    table: TabularTable,
    config: Mapping[str, Any],
    *,
    sheet_names: Sequence[str] = (),
    selected_sheet: str | None = None,
    resolved_reader_config: Mapping[str, Any] | None = None,
    maximum_rows: int = 50,
) -> TabularPreview:
    header_row = _optional_positive_int(config.get("header_row"), "header_row")
    data_start_row = int(
        config.get("data_start_row", (header_row + 1) if header_row is not None else 1)
    )
    if data_start_row < 1:
        raise ValueError("Tabular data_start_row must be at least 1")
    width = table.column_count
    headers = tuple(table.header(header_row, column) for column in range(width))
    selected_rows = [
        row_number
        for row_number in sorted(table.rows)
        if row_number >= data_start_row and not _row_is_blank(table.rows[row_number])
    ][: max(1, int(maximum_rows))]
    rows = tuple(
        tuple(_cell_display(table.cell(row_number, column)) for column in range(width))
        for row_number in selected_rows
    )
    return TabularPreview(
        headers=headers,
        rows=rows,
        row_numbers=tuple(selected_rows),
        column_count=width,
        sheet_names=tuple(str(item) for item in sheet_names),
        selected_sheet=selected_sheet,
        resolved_reader_config=dict(resolved_reader_config or {}),
    )


def _cell_display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    result = int(value)
    if result < 1:
        raise ValueError(f"Tabular {field_name} must be at least 1 or null")
    return result


def _row_is_blank(row: Mapping[int, Any]) -> bool:
    return not any(not _cell_is_blank(value) for value in row.values())


def _cell_is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def Tabular_ConfigNormalize(config: Mapping[str, Any]) -> TabularMappingConfig:
    header_row = _optional_positive_int(config.get("header_row"), "header_row")
    default_start = header_row + 1 if header_row is not None else 1
    data_start_row = int(config.get("data_start_row", default_start))
    data_end_row = _optional_positive_int(config.get("data_end_row"), "data_end_row")
    if data_start_row < 1:
        raise ValueError("Tabular data_start_row must be at least 1")
    if data_end_row is not None and data_end_row < data_start_row:
        raise ValueError("Tabular data_end_row must not precede data_start_row")

    time_payload = config.get("time", {})
    if not isinstance(time_payload, Mapping):
        raise ValueError("Tabular time config must be an object")
    try:
        time_mode = TabularTimeMode(str(time_payload.get("mode", "none")))
    except ValueError as exc:
        raise ValueError(f"Unsupported Tabular time mode {time_payload.get('mode')!r}") from exc
    time_column_value = time_payload.get("column")
    time_column = int(time_column_value) if time_column_value not in (None, "") else None
    if time_column is not None and time_column < 0:
        raise ValueError("Tabular time column must not be negative")
    time_unit = str(time_payload.get("unit", "s")).strip() or "s"
    sample_rate_value = time_payload.get("sample_rate_hz")
    sample_period_value = time_payload.get("sample_period_s")
    time_config = TabularTimeConfig(
        mode=time_mode,
        column=time_column,
        unit=time_unit,
        sample_rate_hz=(
            float(sample_rate_value) if sample_rate_value not in (None, "") else None
        ),
        sample_period_s=(
            float(sample_period_value) if sample_period_value not in (None, "") else None
        ),
    )

    columns_payload = config.get("columns", [])
    if not isinstance(columns_payload, Sequence) or isinstance(
        columns_payload, (str, bytes)
    ):
        raise ValueError("Tabular columns must be an array")
    columns: list[TabularColumnMapping] = []
    used_columns: set[int] = set()
    channel_ids: set[str] = set()
    for payload in columns_payload:
        if not isinstance(payload, Mapping):
            raise ValueError("Every Tabular column mapping must be an object")
        column = int(payload["column"])
        if column < 0 or column in used_columns:
            raise ValueError("Tabular column mappings require unique non-negative indices")
        used_columns.add(column)
        try:
            usage = TabularColumnUsage(str(payload.get("usage", "ignore")))
        except ValueError as exc:
            raise ValueError(
                f"Unsupported Tabular column usage {payload.get('usage')!r}"
            ) from exc
        channel_id = _optional_text(payload.get("channel_id"))
        quantity = _optional_text(payload.get("quantity"))
        if usage is TabularColumnUsage.DATA:
            if channel_id is None or quantity is None:
                raise ValueError("Tabular data columns require channel_id and quantity")
            if channel_id in channel_ids:
                raise ValueError(f"Duplicate Tabular Channel ID {channel_id!r}")
            channel_ids.add(channel_id)
        columns.append(
            TabularColumnMapping(
                column=column,
                usage=usage,
                channel_id=channel_id,
                display_name=_optional_text(payload.get("display_name")),
                quantity=quantity,
                semantic_role=_optional_text(payload.get("role")),
                unit=_optional_text(payload.get("unit")),
                expected_header=_optional_text(
                    payload.get("expected_header", payload.get("header_hint"))
                ),
            )
        )
    time_mappings = tuple(
        mapping for mapping in columns if mapping.usage is TabularColumnUsage.TIME
    )
    if len(time_mappings) > 1:
        raise ValueError("A Tabular Stream may contain only one Time column")
    if time_mode is TabularTimeMode.COLUMN:
        if time_column is None:
            raise ValueError("Time source is column, but no time column was selected")
        if time_mappings and time_mappings[0].column != time_column:
            raise ValueError("Tabular Time mapping does not match the selected time column")
    elif time_mappings:
        raise ValueError(
            "A Time column cannot be selected together with sample-rate or sample-period time"
        )
    try:
        invalid_policy = TabularInvalidValuePolicy(
            str(config.get("invalid_row_policy", "preserve"))
        )
    except ValueError as exc:
        raise ValueError(
            f"Unsupported Tabular invalid_row_policy {config.get('invalid_row_policy')!r}"
        ) from exc
    return TabularMappingConfig(
        header_row=header_row,
        data_start_row=data_start_row,
        data_end_row=data_end_row,
        time=time_config,
        columns=tuple(columns),
        invalid_value_policy=invalid_policy,
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_HEADER_UNIT = re.compile(r"^\s*(.*?)\s*[\[(]([^\])]+)[\])]\s*$")


def _header_name_unit(header: str) -> tuple[str, str | None]:
    match = _HEADER_UNIT.match(header)
    if match is None:
        return header.strip(), None
    return match.group(1).strip(), Unit_Normalize(match.group(2).strip())


def _suggest_semantics(name: str) -> tuple[str | None, str | None, bool]:
    compact = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", name.casefold())
    tokens = set(re.findall(r"[0-9a-z]+|[\u4e00-\u9fff]+", name.casefold()))
    is_time = compact in {"t", "time", "timestamp", "seconds", "时间", "时刻"} or (
        "时间" in compact or "timestamp" in compact
    )
    if is_time:
        return None, None, True
    if (
        compact in {"pc", "pressure", "chamberpressure", "室压", "燃烧室压力"}
        or "pressure" in tokens
        or "pc" in tokens
        or "室压" in compact
        or "压力" in compact
    ):
        role = (
            "chamber_pressure"
            if compact in {"pc", "chamberpressure", "室压", "燃烧室压力"}
            or "chamber" in compact
            or "室压" in compact
            else None
        )
        return "pressure", role, False
    if (
        compact in {"f", "force", "thrust", "推力"}
        or "thrust" in compact
        or "推力" in compact
    ):
        return "force", "thrust", False
    if compact in {"e", "web", "burnedweb", "已燃肉厚", "肉厚"} or "肉厚" in compact:
        return "length", "auxiliary", False
    if (
        compact in {"ab", "area", "burnarea", "燃面面积", "燃烧面积"}
        or "燃面面积" in compact
    ):
        return "area", "auxiliary", False
    if compact in {"kn", "燃喷比"} or "燃喷比" in compact or "kn" in tokens:
        return "kn", "auxiliary", False
    if compact in {"temperature", "temp", "温度"} or "temperature" in compact:
        return "temperature", "temperature", False
    return None, None, False


def _suggest_channel_id(name: str, quantity: str | None, column: int) -> str:
    ascii_name = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    value = ascii_name or quantity or f"column_{Tabular_ColumnLabel(column).lower()}"
    if value[0].isdigit():
        value = f"channel_{value}"
    return value


def _preview_numeric_ratio(preview: TabularPreview, column: int) -> float:
    populated = 0
    numeric = 0
    for row in preview.rows:
        value = row[column].strip()
        if not value:
            continue
        populated += 1
        try:
            float(value)
            numeric += 1
        except ValueError:
            pass
    return numeric / populated if populated else 0.0


def Tabular_MappingSuggest(
    preview: TabularPreview,
    base_config: Mapping[str, Any],
    capability_registry: WorkspaceChannelCapabilityRegistry | None = None,
) -> dict[str, Any]:
    """Return editable suggestions. Parsing never calls this function implicitly."""
    registry = capability_registry or WorkspaceCapabilities_Default()
    config = _json_copy(dict(base_config))
    config.update(_json_copy(dict(preview.resolved_reader_config)))
    header_row = _optional_positive_int(config.get("header_row"), "header_row")
    config["data_start_row"] = int(
        config.get(
            "data_start_row",
            (header_row + 1) if header_row is not None else 1,
        )
    )
    mappings: list[dict[str, Any]] = []
    time_columns: list[tuple[int, str]] = []
    used_channel_ids: set[str] = set()
    for column, header in enumerate(preview.headers):
        name, explicit_unit = _header_name_unit(header)
        quantity, semantic_role, is_time = _suggest_semantics(name)
        if is_time:
            unit = explicit_unit or "s"
            mappings.append(
                {
                    "column": column,
                    "usage": "time",
                    "expected_header": header or None,
                    "unit": unit,
                }
            )
            time_columns.append((column, unit))
            continue
        numeric_ratio = _preview_numeric_ratio(preview, column)
        if not header and numeric_ratio < 0.8:
            mappings.append({"column": column, "usage": "ignore"})
            continue
        if quantity is None:
            quantity = f"custom.{_suggest_channel_id(name, None, column)}"
        if registry.mapping_type(
            quantity=quantity,
            semantic_role=semantic_role,
        ) is None:
            semantic_role = "auxiliary"
        channel_id = _suggest_channel_id(name, quantity, column)
        base_id = channel_id
        suffix = 2
        while channel_id in used_channel_ids:
            channel_id = f"{base_id}_{suffix}"
            suffix += 1
        used_channel_ids.add(channel_id)
        mappings.append(
            {
                "column": column,
                "usage": "data",
                "display_name": name or Tabular_ColumnLabel(column),
                "channel_id": channel_id,
                "quantity": quantity,
                "role": semantic_role,
                "unit": explicit_unit,
                "expected_header": header or None,
            }
        )
    config["columns"] = mappings
    if len(time_columns) == 1:
        column, unit = time_columns[0]
        config["time"] = {"mode": "column", "column": column, "unit": unit}
    else:
        config["time"] = {"mode": "none"}
    config.setdefault("data_end_row", None)
    config.setdefault("invalid_row_policy", "preserve")
    return config


def _mapping_rows(table: TabularTable, config: TabularMappingConfig) -> tuple[int, ...]:
    end_row = config.data_end_row or table.last_row_number
    return tuple(
        row_number
        for row_number in sorted(table.rows)
        if config.data_start_row <= row_number <= end_row
        and not _row_is_blank(table.rows[row_number])
    )


def _numeric_value(
    value: Any,
    *,
    row_number: int,
    column: int,
    policy: TabularInvalidValuePolicy,
) -> tuple[float, str | None]:
    if _cell_is_blank(value):
        if policy is TabularInvalidValuePolicy.ERROR:
            raise ValueError(
                f"Missing numeric value at row {row_number}, column {Tabular_ColumnLabel(column)}"
            )
        return float("nan"), "missing"
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        if policy is TabularInvalidValuePolicy.ERROR:
            raise ValueError(
                f"Non-numeric value at row {row_number}, "
                f"column {Tabular_ColumnLabel(column)}"
            ) from exc
        return float("nan"), "non_numeric"
    if not math.isfinite(number):
        if policy is TabularInvalidValuePolicy.ERROR:
            raise ValueError(
                f"Non-finite value at row {row_number}, column {Tabular_ColumnLabel(column)}"
            )
        return number, "non_finite"
    return number, None


def _mapping_validate_columns(
    table: TabularTable,
    config: TabularMappingConfig,
) -> None:
    required_columns = {
        mapping.column
        for mapping in config.columns
        if mapping.usage in {
            TabularColumnUsage.DATA,
            TabularColumnUsage.TIME,
            TabularColumnUsage.METADATA,
        }
    }
    if config.time.mode is TabularTimeMode.COLUMN:
        if config.time.column is None:
            raise ValueError("Time source is column, but no time column was selected")
        required_columns.add(config.time.column)
    missing = sorted(column for column in required_columns if column >= table.column_count)
    if missing:
        labels = ", ".join(Tabular_ColumnLabel(column) for column in missing)
        raise ValueError(f"Tabular Mapping requires missing source column(s): {labels}")
    if config.time.mode is TabularTimeMode.COLUMN and any(
        mapping.column == config.time.column
        and mapping.usage is TabularColumnUsage.DATA
        for mapping in config.columns
    ):
        raise ValueError("The selected time column cannot also be a Data Channel")


def _time_values(
    table: TabularTable,
    rows: tuple[int, ...],
    config: TabularMappingConfig,
    diagnostics: list[Diagnostic],
    plugin_id: str | None,
) -> np.ndarray:
    time = config.time
    if time.mode is TabularTimeMode.NONE:
        raise ValueError(
            "No time source configured. Select a time column, sample rate, or sample period."
        )
    if time.mode is TabularTimeMode.SAMPLE_RATE:
        rate = time.sample_rate_hz
        if rate is None or not math.isfinite(rate) or rate <= 0:
            raise ValueError("Tabular sample rate must be a positive finite value")
        return np.arange(len(rows), dtype=np.float64) / rate
    if time.mode is TabularTimeMode.SAMPLE_PERIOD:
        period = time.sample_period_s
        if period is None or not math.isfinite(period) or period <= 0:
            raise ValueError("Tabular sample period must be a positive finite value")
        return np.arange(len(rows), dtype=np.float64) * period
    assert time.mode is TabularTimeMode.COLUMN and time.column is not None
    values: list[float] = []
    invalid_count = 0
    for row_number in rows:
        value, problem = _numeric_value(
            table.cell(row_number, time.column),
            row_number=row_number,
            column=time.column,
            policy=config.invalid_value_policy,
        )
        values.append(value)
        invalid_count += int(problem is not None)
    if invalid_count:
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.WARNING,
                "tabular.invalid_time_values",
                f"Time column contains {invalid_count} missing, non-numeric, or non-finite values",
                plugin_id=plugin_id,
                details={"column": time.column, "count": invalid_count},
            )
        )
    definition = Unit_Definition(time.unit)
    if definition is None or definition.dimension != "time" or not definition.engineering:
        raise ValueError(f"Tabular time unit {time.unit!r} is not a supported time unit")
    return Unit_ConvertValues(values, time.unit, "s")


def Tabular_MappingApply(
    table: TabularTable,
    raw_config: Mapping[str, Any],
    *,
    dataset_metadata: Mapping[str, Any] | None = None,
    plugin_id: str | None = None,
) -> Dataset:
    """Map a table by explicit column index; headers are validation hints only."""
    config = Tabular_ConfigNormalize(raw_config)
    _mapping_validate_columns(table, config)
    rows = _mapping_rows(table, config)
    if not rows:
        raise ValueError("Tabular data region contains no nonblank rows")
    diagnostics: list[Diagnostic] = []
    mappings_by_column = {mapping.column: mapping for mapping in config.columns}
    for mapping in config.columns:
        if config.header_row is None or not mapping.expected_header:
            continue
        actual_header = table.header(config.header_row, mapping.column)
        if actual_header != mapping.expected_header:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.WARNING,
                    "tabular.header_hint_mismatch",
                    f"Column {Tabular_ColumnLabel(mapping.column)} was expected to be "
                    f"{mapping.expected_header!r}, but is {actual_header!r}",
                    plugin_id=plugin_id,
                    details={
                        "column": mapping.column,
                        "expected_header": mapping.expected_header,
                        "actual_header": actual_header,
                    },
                )
            )
    populated_unmapped = [
        column
        for column in range(table.column_count)
        if column not in mappings_by_column
        and any(not _cell_is_blank(table.cell(row_number, column)) for row_number in rows)
    ]
    if populated_unmapped:
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.WARNING,
                "tabular.unmapped_columns_ignored",
                "Populated columns not present in the Mapping were ignored: "
                + ", ".join(Tabular_ColumnLabel(item) for item in populated_unmapped),
                plugin_id=plugin_id,
                details={"columns": populated_unmapped},
            )
        )
    time_values = _time_values(table, rows, config, diagnostics, plugin_id)
    channels: dict[str, Channel] = {}
    metadata_columns: list[dict[str, Any]] = []
    for mapping in config.columns:
        if mapping.usage is TabularColumnUsage.METADATA:
            metadata_columns.append(
                {
                    "column": mapping.column,
                    "expected_header": mapping.expected_header,
                }
            )
            continue
        if mapping.usage is not TabularColumnUsage.DATA:
            continue
        assert mapping.channel_id is not None and mapping.quantity is not None
        values: list[float] = []
        problem_counts = {"missing": 0, "non_numeric": 0, "non_finite": 0}
        for row_number in rows:
            value, problem = _numeric_value(
                table.cell(row_number, mapping.column),
                row_number=row_number,
                column=mapping.column,
                policy=config.invalid_value_policy,
            )
            values.append(value)
            if problem is not None:
                problem_counts[problem] += 1
        problem_count = sum(problem_counts.values())
        if problem_count:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.WARNING,
                    "tabular.channel_invalid_values",
                    f"Channel {mapping.channel_id!r} contains {problem_count} missing, "
                    "non-numeric, or non-finite values preserved in row alignment",
                    plugin_id=plugin_id,
                    details={
                        "channel_id": mapping.channel_id,
                        "column": mapping.column,
                        **problem_counts,
                    },
                )
            )
        channel = Channel(
            id=mapping.channel_id,
            name=mapping.display_name or mapping.expected_header or mapping.channel_id,
            quantity=mapping.quantity,
            unit=mapping.unit,
            values=values,
            role="raw",
            semantic_role=mapping.semantic_role,
            metadata={
                "tabular_column": mapping.column,
                "source_header": table.header(config.header_row, mapping.column),
                "data_start_row": config.data_start_row,
                "data_end_row": config.data_end_row,
                "workspace_category": (
                    "other" if mapping.semantic_role == "auxiliary" else None
                ),
            },
        )
        channels[channel.id] = channel
    if not channels:
        raise ValueError("Tabular Mapping contains no Data Channel columns")
    metadata = dict(dataset_metadata or {})
    metadata.update(
        {
            "tabular_header_row": config.header_row,
            "tabular_data_start_row": config.data_start_row,
            "tabular_data_end_row": config.data_end_row,
            "tabular_time_mode": config.time.mode.value,
            "tabular_source_rows": list(rows),
            "tabular_metadata_columns": metadata_columns,
        }
    )
    return Dataset(
        time=time_values,
        time_unit="s",
        channels=channels,
        metadata=metadata,
        diagnostics=diagnostics,
    )
