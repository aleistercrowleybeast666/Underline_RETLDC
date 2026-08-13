from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.data_quality import Dataset_QualityInspect
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.plugin_api.common import (
    ParseResult,
    PluginDescriptor,
    PluginType,
    ProbeContext,
    ProbeResult,
    TaskContext,
)
from underline_retldc.plugin_api.parser import ParserPlugin


class TrFParser(ParserPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.parser.tr_f",
            plugin_type=PluginType.PARSER,
            version="1.0.0",
            api_version="1",
            name="TR_F",
            description="Time / Raw Force two-column text parser",
            translation_key="parser.tr_f.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "delimiter": {
                    "type": "string",
                    "default": ",",
                    "minLength": 1,
                    "title": "Delimiter",
                    "x-i18n-key": "schema.parser.delimiter",
                },
                "time_unit": {
                    "type": "string",
                    "enum": ["s", "ms", "us"],
                    "default": "s",
                    "title": "Source time unit",
                    "x-i18n-key": "schema.parser.time_unit",
                },
                "invalid_row_policy": {
                    "type": "string",
                    "enum": ["skip", "error"],
                    "default": "skip",
                    "title": "Invalid row policy",
                    "x-i18n-key": "schema.parser.invalid_row_policy",
                    "x-enum-i18n-keys": {
                        "skip": "schema.parser.invalid_row_policy.skip",
                        "error": "schema.parser.invalid_row_policy.error",
                    },
                },
            },
        }

    def probe(self, source: Path, context: ProbeContext) -> ProbeResult:
        source = Path(source)
        if not source.is_file():
            return ProbeResult(0.0, "Source is not a readable file")
        try:
            raw_prefix = source.open("rb").read(context.max_bytes)
            text = raw_prefix.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            return ProbeResult(0.0, f"Unable to read UTF-8 text: {exc}")

        rows = [line.strip() for line in text.splitlines() if line.strip()]
        rows = rows[: context.max_records]
        if not rows:
            return ProbeResult(0.0, "No nonblank records in probe window")

        valid = 0
        structure_matches = 0
        timestamps: list[float] = []
        for row in rows:
            parts = row.split(",")
            if len(parts) != 2:
                continue
            structure_matches += 1
            try:
                timestamp, raw_force = (float(part.strip()) for part in parts)
            except ValueError:
                continue
            if math.isfinite(timestamp) and math.isfinite(raw_force):
                valid += 1
                timestamps.append(timestamp)

        structure_ratio = structure_matches / len(rows)
        valid_ratio = valid / len(rows)
        monotonic_ratio = 0.0
        if len(timestamps) >= 2:
            differences = np.diff(np.asarray(timestamps, dtype=np.float64))
            monotonic_ratio = float(np.count_nonzero(differences >= 0) / len(differences))
        elif timestamps:
            monotonic_ratio = 0.5

        confidence = 0.35 * structure_ratio + 0.45 * valid_ratio + 0.20 * monotonic_ratio
        if valid < 3:
            confidence = min(confidence, 0.45)
        reason = (
            f"{valid}/{len(rows)} numeric two-column records; "
            f"timestamp monotonicity {monotonic_ratio:.0%}"
        )
        return ProbeResult(float(min(1.0, max(0.0, confidence))), reason)

    def parse(
        self, source: Path, config: Mapping[str, Any], context: TaskContext
    ) -> ParseResult:
        source = Path(source)
        delimiter = str(config.get("delimiter", ","))
        time_unit = str(config.get("time_unit", "s"))
        invalid_policy = str(config.get("invalid_row_policy", "skip"))
        if not delimiter:
            raise ValueError("TR_F delimiter must not be empty")
        if invalid_policy not in {"skip", "error"}:
            raise ValueError("TR_F invalid_row_policy must be 'skip' or 'error'")
        time_scales = {"s": 1.0, "ms": 1.0e-3, "us": 1.0e-6}
        if time_unit not in time_scales:
            raise ValueError("TR_F time_unit must be 's', 'ms', or 'us'")
        if not source.is_file():
            raise FileNotFoundError(f"TR_F source does not exist: {source}")

        times: list[float] = []
        raw_values: list[float] = []
        diagnostics: list[Diagnostic] = []
        malformed_rows = 0
        total_size = max(source.stat().st_size, 1)
        try:
            with source.open("r", encoding="utf-8-sig", newline="") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if line_number % 1024 == 0:
                        context.raise_if_cancelled()
                        context.report_progress(
                            min(handle.buffer.tell() / total_size, 0.99), "Parsing TR_F"
                        )
                    stripped = line.strip()
                    if not stripped:
                        continue
                    parts = stripped.split(delimiter)
                    reason: str | None = None
                    if len(parts) != 2:
                        reason = f"expected exactly two columns, found {len(parts)}"
                    else:
                        try:
                            timestamp = float(parts[0].strip())
                            raw_force = float(parts[1].strip())
                            if not math.isfinite(timestamp) or not math.isfinite(raw_force):
                                reason = "values must be finite"
                        except ValueError:
                            reason = "columns are not valid numbers"
                    if reason is not None:
                        malformed_rows += 1
                        diagnostic = Diagnostic(
                            DiagnosticSeverity.WARNING,
                            "tr_f.malformed_row",
                            reason,
                            source=str(source),
                            line=line_number,
                            plugin_id=self.descriptor.plugin_id,
                        )
                        diagnostics.append(diagnostic)
                        if invalid_policy == "error":
                            raise ValueError(f"{source}:{line_number}: {reason}")
                        continue
                    times.append(timestamp * time_scales[time_unit])
                    raw_values.append(raw_force)
        except UnicodeDecodeError as exc:
            raise ValueError(f"TR_F source is not valid UTF-8 text: {source}: {exc}") from exc

        context.raise_if_cancelled()
        if not times:
            raise ValueError(f"TR_F source contains no valid records: {source}")
        channel = Channel(
            id="thrust_raw",
            quantity="force",
            unit="raw",
            values=raw_values,
            role="raw",
            metadata={"source_format": "TR_F/1", "column": 1},
        )
        dataset = Dataset(
            time=times,
            time_unit="s",
            channels={channel.id: channel},
            metadata={
                "source_path": str(source.resolve()),
                "source_format": "TR_F/1",
                "source_time_unit": time_unit,
                "malformed_rows": malformed_rows,
            },
            diagnostics=diagnostics,
        )
        quality = Dataset_QualityInspect(dataset)
        dataset = dataset.with_diagnostics(quality.diagnostics)
        context.report_progress(1.0, "TR_F parsed")
        return ParseResult(dataset=dataset, diagnostics=dataset.diagnostics)

    def validate(self, dataset: Dataset) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        if "thrust_raw" not in dataset.channels:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "tr_f.missing_raw_channel",
                    "TR_F Dataset does not contain thrust_raw",
                    plugin_id=self.descriptor.plugin_id,
                )
            )
        diagnostics.extend(Dataset_QualityInspect(dataset).diagnostics)
        return diagnostics
