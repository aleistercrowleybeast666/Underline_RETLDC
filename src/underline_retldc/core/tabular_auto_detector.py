from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import numpy as np

from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.tabular import Tabular_ColumnLabel, TabularPreset, TabularPreview
from underline_retldc.core.units import Unit_Normalize

_TIME_HEADERS = {"t", "time", "timestamp", "times", "second", "seconds", "时间", "时刻"}
_THRUST_HEADERS = {"f", "force", "thrust", "推力"}
_PRESSURE_HEADERS = {
    "pc",
    "chamberp",
    "chamberpressure",
    "combustionchamberpressure",
    "室压",
    "燃烧室压力",
}
_TEMPERATURE_HEADERS = {"temperature", "temp", "thermocouple", "温度", "热电偶"}
_OTHER_MARKERS = (
    "kn",
    "燃喷比",
    "喷燃比",
    "燃面面积",
    "burnarea",
    "已燃肉厚",
    "web",
    "喉径",
    "throat",
    "燃面",
    "面积",
    "长度",
    "质量",
    "密度",
    "燃速",
    "rb",
    "燃面比",
    "设计参数",
    "几何参数",
    "系数",
    "状态标志",
)
_TIME_UNITS = {"s", "ms", "us"}
_FORCE_UNITS = {"N", "kN", "kgf", "lbf"}
_PRESSURE_UNITS = {"Pa", "kPa", "MPa", "bar", "psi"}
_TEMPERATURE_UNITS = {"K", "degC", "degF"}
_HEADER_UNIT = re.compile(r"^\s*(.*?)\s*[\[(]([^\])]+)[\])]\s*$")


@dataclass(frozen=True, slots=True)
class TabularColumnSuggestion:
    column_index: int
    header: str
    suggested_user_category: str
    unit: str | None
    confidence: float
    reasons: tuple[str, ...] = ()
    scores: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scores", MappingProxyType(dict(self.scores)))


@dataclass(frozen=True, slots=True)
class TabularAutoDetectionResult:
    header_row: int | None
    data_start_row: int | None
    time_config: Mapping[str, Any]
    column_suggestions: tuple[TabularColumnSuggestion, ...]
    confidence: float
    diagnostics: tuple[Diagnostic, ...] = ()
    blocking_reason: str | None = None
    resolved_reader_config: Mapping[str, Any] = field(default_factory=dict)
    preset_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "time_config", MappingProxyType(dict(self.time_config)))
        object.__setattr__(
            self,
            "resolved_reader_config",
            MappingProxyType(dict(self.resolved_reader_config)),
        )

    @property
    def can_parse(self) -> bool:
        return self.blocking_reason is None and self.data_start_row is not None

    def mapping_config(self, base_config: Mapping[str, Any] | None = None) -> dict[str, Any]:
        config = dict(base_config or {})
        config.update(dict(self.resolved_reader_config))
        config.update(
            {
                "header_row": self.header_row,
                "data_start_row": self.data_start_row or 1,
                "data_end_row": config.get("data_end_row"),
                "time": dict(self.time_config),
                "invalid_row_policy": config.get("invalid_row_policy", "preserve"),
            }
        )
        used_ids: set[str] = set()
        columns: list[dict[str, Any]] = []
        for suggestion in self.column_suggestions:
            column = suggestion.column_index
            header_name, _unit = _header_parts(suggestion.header)
            if suggestion.suggested_user_category == "time":
                columns.append(
                    {
                        "column": column,
                        "usage": "time",
                        "unit": suggestion.unit or "s",
                        "expected_header": suggestion.header or None,
                    }
                )
                continue
            category = suggestion.suggested_user_category
            channel_id = _channel_id(header_name, category, column)
            base_id = channel_id
            suffix = 2
            while channel_id in used_ids:
                channel_id = f"{base_id}_{suffix}"
                suffix += 1
            used_ids.add(channel_id)
            quantity, role = {
                "thrust": ("force", "thrust"),
                "chamber_pressure": ("pressure", "chamber_pressure"),
                "temperature": ("temperature", "temperature"),
                "other": (f"custom.{channel_id}", "auxiliary"),
            }[category]
            columns.append(
                {
                    "column": column,
                    "usage": "data",
                    "display_name": header_name or Tabular_ColumnLabel(column),
                    "channel_id": channel_id,
                    "quantity": quantity,
                    "role": role,
                    "unit": suggestion.unit,
                    "expected_header": suggestion.header or None,
                }
            )
        config["columns"] = columns
        return config


class TabularAutoDetector:
    """Deterministic, local-only structure and column detector for bounded previews."""

    def __init__(
        self,
        *,
        time_threshold: float = 0.68,
        time_ambiguity_margin: float = 0.08,
    ) -> None:
        self._time_threshold = float(time_threshold)
        self._time_ambiguity_margin = float(time_ambiguity_margin)

    def detect(
        self,
        preview: TabularPreview,
        *,
        parser_context: Mapping[str, Any] | None = None,
        preset_candidates: Sequence[TabularPreset] = (),
    ) -> TabularAutoDetectionResult:
        del parser_context  # Reserved for future reader-specific, non-GUI hints.
        rows = {
            number: tuple(values)
            for number, values in zip(preview.row_numbers, preview.rows, strict=True)
        }
        if not rows or preview.column_count < 2:
            return self._failure(
                preview,
                "tabular.auto_structure_failed",
                "No stable two-dimensional data region was found.",
            )
        data_start = _data_start_detect(rows)
        if data_start is None:
            return self._failure(
                preview,
                "tabular.auto_structure_failed",
                "No stable numeric data region was found.",
            )
        header_row = _header_row_detect(rows, data_start)
        headers = (
            tuple(rows[header_row])
            if header_row is not None
            else tuple("" for _ in range(preview.column_count))
        )
        data_rows = tuple(rows[number] for number in sorted(rows) if number >= data_start)
        time_scores = [
            _time_score(headers[column], data_rows, column)
            for column in range(preview.column_count)
        ]
        ranked_time = sorted(
            enumerate(time_scores), key=lambda item: item[1][0], reverse=True
        )
        best_column, (best_time_score, best_time_unit, best_time_reasons) = ranked_time[0]
        if best_time_score < self._time_threshold:
            suggestions = self._column_suggestions(headers, data_rows, None)
            return self._failure(
                preview,
                "tabular.auto_time_missing",
                "Unable to determine a time column; select a time source in Advanced.",
                header_row=header_row,
                data_start_row=data_start,
                suggestions=suggestions,
            )
        if (
            len(ranked_time) > 1
            and ranked_time[1][1][0] >= self._time_threshold
            and best_time_score - ranked_time[1][1][0] < self._time_ambiguity_margin
        ):
            suggestions = self._column_suggestions(headers, data_rows, None)
            return self._failure(
                preview,
                "tabular.auto_time_ambiguous",
                "Multiple similarly likely time columns were detected; confirm one in Advanced.",
                header_row=header_row,
                data_start_row=data_start,
                suggestions=suggestions,
            )
        suggestions = list(self._column_suggestions(headers, data_rows, best_column))
        suggestions[best_column] = TabularColumnSuggestion(
            best_column,
            headers[best_column],
            "time",
            best_time_unit or "s",
            best_time_score,
            best_time_reasons,
            {"time": best_time_score},
        )
        preset_name, preset_score = _preset_best_match(
            preset_candidates,
            headers,
            preview,
        )
        classified_scores = [
            item.confidence
            for item in suggestions
            if item.column_index != best_column
        ]
        confidence = min(
            0.99,
            0.55 * best_time_score
            + 0.35 * (sum(classified_scores) / max(len(classified_scores), 1))
            + 0.10 * preset_score,
        )
        diagnostic = Diagnostic(
            DiagnosticSeverity.INFO,
            "tabular.auto_detected",
            "Tabular structure and mapping were detected locally.",
            details={
                "header_row": header_row,
                "data_start_row": data_start,
                "time_column": best_column,
                "confidence": confidence,
            },
        )
        return TabularAutoDetectionResult(
            header_row=header_row,
            data_start_row=data_start,
            time_config={
                "mode": "column",
                "column": best_column,
                "unit": best_time_unit or "s",
            },
            column_suggestions=tuple(suggestions),
            confidence=confidence,
            diagnostics=(diagnostic,),
            resolved_reader_config=preview.resolved_reader_config,
            preset_name=preset_name,
        )

    @staticmethod
    def _column_suggestions(
        headers: tuple[str, ...],
        data_rows: tuple[tuple[str, ...], ...],
        time_column: int | None,
    ) -> tuple[TabularColumnSuggestion, ...]:
        return tuple(
            _column_classify(column, header, data_rows, is_time=column == time_column)
            for column, header in enumerate(headers)
        )

    @staticmethod
    def _failure(
        preview: TabularPreview,
        code: str,
        reason: str,
        *,
        header_row: int | None = None,
        data_start_row: int | None = None,
        suggestions: tuple[TabularColumnSuggestion, ...] = (),
    ) -> TabularAutoDetectionResult:
        return TabularAutoDetectionResult(
            header_row=header_row,
            data_start_row=data_start_row,
            time_config={"mode": "none"},
            column_suggestions=suggestions,
            confidence=0.0,
            diagnostics=(Diagnostic(DiagnosticSeverity.WARNING, code, reason),),
            blocking_reason=reason,
            resolved_reader_config=preview.resolved_reader_config,
        )


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _row_profile(row: tuple[str, ...]) -> tuple[int, int, float]:
    populated = sum(bool(_text(value)) for value in row)
    numeric = sum(_number(value) is not None for value in row)
    return populated, numeric, numeric / populated if populated else 0.0


def _data_start_detect(rows: Mapping[int, tuple[str, ...]]) -> int | None:
    ordered = sorted(rows)
    for position, row_number in enumerate(ordered):
        window_numbers = ordered[position : position + 4]
        if len(window_numbers) < min(3, len(ordered)):
            continue
        profiles = [_row_profile(rows[number]) for number in window_numbers]
        if profiles[0][0] < 2 or profiles[0][2] < 0.60:
            continue
        useful = [profile for profile in profiles if profile[0] >= 2 and profile[2] >= 0.60]
        if len(useful) < min(3, len(window_numbers)):
            continue
        widths = [profile[0] for profile in useful]
        common_width, count = Counter(widths).most_common(1)[0]
        if common_width >= 2 and count / len(widths) >= 0.66:
            return row_number
    return None


def _header_row_detect(
    rows: Mapping[int, tuple[str, ...]], data_start: int
) -> int | None:
    candidates = [number for number in sorted(rows) if data_start - 5 <= number < data_start]
    best: tuple[float, int] | None = None
    data_width = _row_profile(rows[data_start])[0]
    for row_number in candidates:
        row = rows[row_number]
        populated, numeric, _ratio = _row_profile(row)
        textual = populated - numeric
        if populated < 2 or textual < 1:
            continue
        token_hits = sum(_header_token_strength(_text(value)) > 0 for value in row)
        proximity = 1.0 / (data_start - row_number)
        width_match = min(populated, data_width) / max(populated, data_width, 1)
        score = 0.45 * (textual / populated) + 0.25 * width_match + 0.20 * proximity
        score += 0.10 * min(1.0, token_hits / 2)
        if best is None or score > best[0]:
            best = (score, row_number)
    return best[1] if best is not None and best[0] >= 0.56 else None


def _header_parts(header: str) -> tuple[str, str | None]:
    text = _text(header)
    match = _HEADER_UNIT.match(text)
    if match is None:
        return text, None
    return match.group(1).strip(), Unit_Normalize(match.group(2).strip())


def _compact(header: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", header.casefold())


def _header_token_strength(header: str) -> float:
    name, _unit = _header_parts(header)
    compact = _compact(name)
    if (
        compact in _TIME_HEADERS
        or compact in _THRUST_HEADERS
        or compact in _PRESSURE_HEADERS
        or compact in _TEMPERATURE_HEADERS
        or name.strip() == "T"
        or re.fullmatch(r"tc\d*", compact)
    ):
        return 1.0
    return 0.5 if any(marker in compact for marker in _OTHER_MARKERS) else 0.0


def _time_score(
    header: str,
    data_rows: tuple[tuple[str, ...], ...],
    column: int,
) -> tuple[float, str | None, tuple[str, ...]]:
    name, explicit_unit = _header_parts(header)
    compact = _compact(name)
    values = np.asarray(
        [value for row in data_rows if (value := _number(row[column])) is not None],
        dtype=np.float64,
    )
    populated = sum(bool(_text(row[column])) for row in data_rows)
    numeric_ratio = len(values) / populated if populated else 0.0
    header_score = (
        1.0
        if (
            (compact in _TIME_HEADERS or "时间" in compact or "timestamp" in compact)
            and name.strip() != "T"
        )
        else 0.0
    )
    normalized_unit = Unit_Normalize(explicit_unit) if explicit_unit else None
    unit_score = 1.0 if normalized_unit in _TIME_UNITS else 0.0
    monotonic = 0.0
    continuity = 0.0
    dt_consistency = 0.0
    if len(values) >= 3:
        differences = np.diff(values)
        monotonic = float(np.mean(differences > 0.0))
        positive = differences[differences > 0.0]
        if positive.size:
            median = float(np.median(positive))
            continuity = float(np.mean(differences >= 0.0))
            if median > 0.0:
                mad = float(np.median(np.abs(positive - median)))
                dt_consistency = max(0.0, 1.0 - min(1.0, mad / median * 4.0))
    reasonable_start = 1.0 if len(values) and abs(float(values[0])) <= 10.0 else 0.4
    score = (
        0.36 * header_score
        + 0.10 * unit_score
        + 0.14 * numeric_ratio
        + 0.20 * monotonic
        + 0.08 * continuity
        + 0.08 * dt_consistency
        + 0.04 * reasonable_start
    )
    reasons = (
        f"header={header_score:.2f}",
        f"unit={unit_score:.2f}",
        f"numeric={numeric_ratio:.2f}",
        f"monotonic={monotonic:.2f}",
        f"dt_consistency={dt_consistency:.2f}",
    )
    return min(1.0, score), normalized_unit, reasons


def _column_classify(
    column: int,
    header: str,
    data_rows: tuple[tuple[str, ...], ...],
    *,
    is_time: bool,
) -> TabularColumnSuggestion:
    if is_time:
        return TabularColumnSuggestion(column, header, "time", "s", 1.0, ("time",))
    name, explicit_unit = _header_parts(header)
    compact = _compact(name)
    normalized_unit = Unit_Normalize(explicit_unit) if explicit_unit else None
    if any(marker == compact or marker in compact for marker in _OTHER_MARKERS):
        return TabularColumnSuggestion(
            column,
            header,
            "other",
            normalized_unit,
            0.99,
            ("explicit auxiliary/geometry/design token",),
            {"other": 1.0},
        )
    populated = sum(bool(_text(row[column])) for row in data_rows)
    numeric = sum(_number(row[column]) is not None for row in data_rows)
    numeric_score = numeric / populated if populated else 0.0
    scores = {"thrust": 0.0, "chamber_pressure": 0.0, "temperature": 0.0}
    reasons: dict[str, list[str]] = {key: [] for key in scores}
    if compact in _THRUST_HEADERS or "thrust" in compact or "推力" in compact:
        scores["thrust"] += 0.72
        reasons["thrust"].append("strong thrust header")
    if normalized_unit in _FORCE_UNITS:
        scores["thrust"] += 0.25
        reasons["thrust"].append("force unit")
    if (
        compact in _PRESSURE_HEADERS
        or "chamberpressure" in compact
        or "燃烧室压力" in compact
        or "室压" in compact
    ):
        scores["chamber_pressure"] += 0.72
        reasons["chamber_pressure"].append("strong chamber-pressure header")
    if normalized_unit in _PRESSURE_UNITS:
        scores["chamber_pressure"] += 0.22
        reasons["chamber_pressure"].append("pressure unit")
    # A generic tank/feed/injector pressure is pressure data, but not the Primary Chamber Pressure.
    if any(token in compact for token in ("tank", "feed", "injector", "管路", "贮箱")):
        scores["chamber_pressure"] = 0.0
        reasons["chamber_pressure"] = ["non-chamber pressure qualifier"]
    temperature_header = (
        compact in _TEMPERATURE_HEADERS
        or name.strip() == "T"
        or re.fullmatch(r"tc\d*", compact) is not None
        or "temperature" in compact
        or "温度" in compact
        or "热电偶" in compact
    )
    if temperature_header:
        scores["temperature"] += 0.72
        reasons["temperature"].append("strong temperature header")
    if normalized_unit in _TEMPERATURE_UNITS:
        scores["temperature"] += 0.25
        reasons["temperature"].append("temperature unit")
    for key in scores:
        scores[key] += 0.03 * numeric_score
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    category, score = ranked[0]
    margin = score - ranked[1][1]
    if score < 0.68 or margin < 0.18:
        return TabularColumnSuggestion(
            column,
            header,
            "other",
            normalized_unit,
            max(0.70, 1.0 - score),
            ("no scientific category exceeded the conservative threshold",),
            scores,
        )
    return TabularColumnSuggestion(
        column,
        header,
        category,
        normalized_unit,
        min(0.99, score),
        tuple(reasons[category]),
        scores,
    )


def _channel_id(name: str, category: str, column: int) -> str:
    ascii_name = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    value = ascii_name or {
        "thrust": "thrust",
        "chamber_pressure": "chamber_pressure",
        "temperature": "temperature",
        "other": f"column_{Tabular_ColumnLabel(column).lower()}",
    }[category]
    return f"channel_{value}" if value[0].isdigit() else value


def _preset_best_match(
    presets: Sequence[TabularPreset],
    headers: tuple[str, ...],
    preview: TabularPreview,
) -> tuple[str | None, float]:
    best_name: str | None = None
    best_score = 0.0
    for preset in presets:
        columns = preset.config.get("columns", [])
        if not isinstance(columns, Sequence) or isinstance(columns, (str, bytes)):
            continue
        expected = {
            int(item["column"]): _text(item.get("expected_header"))
            for item in columns
            if isinstance(item, Mapping) and "column" in item
        }
        width_score = 1.0 if len(columns) == preview.column_count else 0.0
        hinted = [(column, value) for column, value in expected.items() if value]
        header_score = (
            sum(column < len(headers) and headers[column] == value for column, value in hinted)
            / len(hinted)
            if hinted
            else 0.0
        )
        sheet_score = 0.0
        preset_sheet = _text(preset.config.get("sheet_name"))
        if preset_sheet and preset_sheet == _text(preview.selected_sheet):
            sheet_score = 1.0
        score = 0.35 * width_score + 0.55 * header_score + 0.10 * sheet_score
        if score > best_score:
            best_name, best_score = preset.name, score
    return best_name, best_score
