from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.data_quality import Dataset_QualityInspect
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.plugin_api.common import (
    ParseResult,
    ProbeContext,
    ProbeResult,
    TaskContext,
)
from underline_retldc.plugin_api.parser import ParserPlugin


class TwoColumnRawParserBase(ParserPlugin):
    """Shared implementation for semantically ambiguous ``time,value`` formats."""

    channel_id: ClassVar[str]
    channel_name: ClassVar[str]
    quantity: ClassVar[str]
    semantic_role: ClassVar[str]
    source_format: ClassVar[str]
    diagnostic_prefix: ClassVar[str]

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
        path = Path(source)
        if not path.is_file():
            return ProbeResult(0.0, "Source is not a readable file")
        try:
            with path.open("rb") as handle:
                text = handle.read(context.max_bytes).decode("utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            return ProbeResult(0.0, f"Unable to read UTF-8 text: {exc}")

        rows = [line.strip() for line in text.splitlines() if line.strip()][
            : context.max_records
        ]
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
                timestamp, value = (float(part.strip()) for part in parts)
            except ValueError:
                continue
            if math.isfinite(timestamp) and math.isfinite(value):
                valid += 1
                timestamps.append(timestamp)
        structure_ratio = structure_matches / len(rows)
        valid_ratio = valid / len(rows)
        monotonic_ratio = 0.0
        if len(timestamps) >= 2:
            differences = np.diff(np.asarray(timestamps, dtype=np.float64))
            monotonic_ratio = float(
                np.count_nonzero(differences >= 0) / len(differences)
            )
        elif timestamps:
            monotonic_ratio = 0.5
        confidence = (
            0.35 * structure_ratio + 0.45 * valid_ratio + 0.20 * monotonic_ratio
        )
        if valid < 3:
            confidence = min(confidence, 0.45)
        return ProbeResult(
            float(min(1.0, max(0.0, confidence))),
            f"{valid}/{len(rows)} numeric two-column records; "
            f"timestamp monotonicity {monotonic_ratio:.0%}",
        )

    def parse(
        self,
        source: Path,
        config: Mapping[str, Any],
        context: TaskContext,
    ) -> ParseResult:
        path = Path(source)
        delimiter = str(config.get("delimiter", ","))
        time_unit = str(config.get("time_unit", "s"))
        invalid_policy = str(config.get("invalid_row_policy", "skip"))
        if not delimiter:
            raise ValueError(f"{self.source_format} delimiter must not be empty")
        if invalid_policy not in {"skip", "error"}:
            raise ValueError("invalid_row_policy must be 'skip' or 'error'")
        time_scales = {"s": 1.0, "ms": 1.0e-3, "us": 1.0e-6}
        if time_unit not in time_scales:
            raise ValueError("time_unit must be 's', 'ms', or 'us'")
        if not path.is_file():
            raise FileNotFoundError(f"{self.source_format} source does not exist: {path}")

        times: list[float] = []
        raw_values: list[float] = []
        diagnostics: list[Diagnostic] = []
        malformed_rows = 0
        total_size = max(path.stat().st_size, 1)
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if line_number % 1024 == 0:
                        context.raise_if_cancelled()
                        context.report_progress(
                            min(handle.buffer.tell() / total_size, 0.99),
                            f"Parsing {self.source_format}",
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
                            raw_value = float(parts[1].strip())
                            if not math.isfinite(timestamp) or not math.isfinite(raw_value):
                                reason = "values must be finite"
                        except ValueError:
                            reason = "columns are not valid numbers"
                    if reason is not None:
                        malformed_rows += 1
                        diagnostics.append(
                            Diagnostic(
                                DiagnosticSeverity.WARNING,
                                f"{self.diagnostic_prefix}.malformed_row",
                                reason,
                                source=str(path),
                                line=line_number,
                                plugin_id=self.descriptor.plugin_id,
                            )
                        )
                        if invalid_policy == "error":
                            raise ValueError(f"{path}:{line_number}: {reason}")
                        continue
                    times.append(timestamp * time_scales[time_unit])
                    raw_values.append(raw_value)
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"{self.source_format} source is not valid UTF-8 text: {path}: {exc}"
            ) from exc

        context.raise_if_cancelled()
        if not times:
            raise ValueError(
                f"{self.source_format} source contains no valid records: {path}"
            )
        channel = Channel(
            id=self.channel_id,
            name=self.channel_name,
            quantity=self.quantity,
            unit="raw",
            values=raw_values,
            role="raw",
            semantic_role=self.semantic_role,
            metadata={"source_format": f"{self.source_format}/1", "column": 1},
        )
        dataset = Dataset(
            time=times,
            time_unit="s",
            channels={channel.id: channel},
            metadata={
                "source_path": str(path.resolve()),
                "source_format": f"{self.source_format}/1",
                "source_time_unit": time_unit,
                "malformed_rows": malformed_rows,
            },
            diagnostics=diagnostics,
        )
        quality = Dataset_QualityInspect(dataset)
        dataset = dataset.with_diagnostics(quality.diagnostics)
        context.report_progress(1.0, f"{self.source_format} parsed")
        return ParseResult(dataset=dataset, diagnostics=dataset.diagnostics)

    def validate(self, dataset: Dataset) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        if self.channel_id not in dataset.channels:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    f"{self.diagnostic_prefix}.missing_raw_channel",
                    f"{self.source_format} Dataset does not contain {self.channel_id}",
                    plugin_id=self.descriptor.plugin_id,
                )
            )
        diagnostics.extend(Dataset_QualityInspect(dataset).diagnostics)
        return diagnostics
