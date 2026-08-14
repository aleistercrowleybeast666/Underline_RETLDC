from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from underline_retldc.core.data_quality import Dataset_QualityInspect
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic
from underline_retldc.core.tabular import (
    Tabular_MappingApply,
    Tabular_PreviewBuild,
    TabularPreview,
    TabularTable,
)
from underline_retldc.plugin_api.common import (
    ParseResult,
    PluginDescriptor,
    PluginType,
    ProbeContext,
    ProbeResult,
    TaskContext,
)
from underline_retldc.plugin_api.parser import TabularParserPlugin

_DELIMITER_CANDIDATES = ",;\t| "
_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "gb18030")


class GenericDelimitedParser(TabularParserPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.parser.generic_delimited",
            plugin_type=PluginType.PARSER,
            version="1.0.0",
            api_version="1",
            name="Generic CSV / TSV",
            description="Delimited text reader using explicit reusable Tabular Column Mapping",
            translation_key="parser.generic_delimited.name",
        )

    def config_schema(self) -> dict[str, Any]:
        hidden = {"x-ui-hidden": True}
        return {
            "type": "object",
            "properties": {
                "delimiter": {"type": "string", "default": "auto", **hidden},
                "custom_delimiter": {"type": "string", "default": "", **hidden},
                "encoding": {"type": "string", "default": "auto", **hidden},
                "header_row": {
                    "type": ["integer", "null"],
                    "default": 1,
                    **hidden,
                },
                "data_start_row": {"type": "integer", "default": 2, **hidden},
                "data_end_row": {
                    "type": ["integer", "null"],
                    "default": None,
                    **hidden,
                },
                "time": {"type": "object", "default": {"mode": "none"}, **hidden},
                "columns": {"type": "array", "default": [], **hidden},
                "invalid_row_policy": {
                    "type": "string",
                    "enum": ["preserve", "error"],
                    "default": "preserve",
                    **hidden,
                },
            },
            "x-underline-retldc-tabular": {
                "reader": "delimited",
                "preview_rows": 50,
                "preset_supported": True,
            },
        }

    @staticmethod
    def _encoding_resolve(path: Path, configured: str) -> str:
        value = configured.strip() or "auto"
        if value != "auto":
            return value
        prefix = path.read_bytes()[:65_536]
        for encoding in _ENCODING_CANDIDATES:
            try:
                prefix.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue
        raise ValueError(
            "Unable to auto-detect delimited-text encoding; select an encoding explicitly"
        )

    @staticmethod
    def _delimiter_resolve(path: Path, encoding: str, config: Mapping[str, Any]) -> str:
        configured = str(config.get("delimiter", "auto"))
        aliases = {"tab": "\t", "space": " "}
        configured = aliases.get(configured, configured)
        if configured == "custom":
            configured = str(config.get("custom_delimiter", ""))
        if configured != "auto":
            if len(configured) != 1:
                raise ValueError("Delimited text separator must be exactly one character")
            return configured
        with path.open("r", encoding=encoding, newline="") as handle:
            sample = handle.read(65_536)
        try:
            return csv.Sniffer().sniff(sample, delimiters=_DELIMITER_CANDIDATES).delimiter
        except csv.Error:
            lines = [line for line in sample.splitlines() if line.strip()]
            scored: list[tuple[int, float, str]] = []
            for candidate in _DELIMITER_CANDIDATES:
                widths = [
                    len(row)
                    for row in csv.reader(lines, delimiter=candidate)
                    if len(row) > 1
                ]
                if len(widths) < 2:
                    continue
                common_width = max(set(widths), key=widths.count)
                consistency = widths.count(common_width) / len(widths)
                scored.append((widths.count(common_width), consistency, candidate))
            if scored:
                return max(scored)[2]
            raise ValueError(
                "Unable to auto-detect delimiter; select comma, semicolon, Tab, space, "
                "pipe, or a custom delimiter"
            ) from None

    def _table_read(
        self,
        source: Path,
        config: Mapping[str, Any],
        *,
        maximum_row_number: int | None = None,
    ) -> tuple[TabularTable, str, str]:
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"Delimited source does not exist: {path}")
        encoding = self._encoding_resolve(path, str(config.get("encoding", "auto")))
        delimiter = self._delimiter_resolve(path, encoding, config)
        rows: dict[int, dict[int, str]] = {}
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle, delimiter=delimiter, skipinitialspace=True)
                for row_number, values in enumerate(reader, start=1):
                    rows[row_number] = {
                        column: value for column, value in enumerate(values)
                    }
                    if (
                        maximum_row_number is not None
                        and row_number >= maximum_row_number
                    ):
                        break
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ValueError(f"Unable to read delimited source {path}: {exc}") from exc
        return TabularTable(rows), delimiter, encoding

    def probe(self, source: Path, context: ProbeContext) -> ProbeResult:
        path = Path(source)
        if not path.is_file():
            return ProbeResult(0.0, "Source is not a readable file")
        try:
            encoding = self._encoding_resolve(path, "auto")
            delimiter = self._delimiter_resolve(path, encoding, {"delimiter": "auto"})
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle, delimiter=delimiter)
                rows = [row for _, row in zip(range(context.max_records), reader, strict=False)]
        except (OSError, ValueError, UnicodeDecodeError, csv.Error) as exc:
            return ProbeResult(0.0, f"Unable to inspect delimited text: {exc}")
        populated = [row for row in rows if any(cell.strip() for cell in row)]
        if not populated:
            return ProbeResult(0.0, "No populated delimited rows in probe window")
        widths = [len(row) for row in populated]
        common_width = max(set(widths), key=widths.count)
        consistent = sum(width == common_width for width in widths) / len(widths)
        extension_bonus = 0.12 if path.suffix.casefold() in {".csv", ".tsv"} else 0.04
        confidence = min(0.97, 0.52 + 0.32 * consistent + extension_bonus)
        return ProbeResult(
            confidence,
            f"Detected {delimiter!r} delimiter, {encoding}, {common_width} columns",
        )

    def preview(
        self,
        source: Path,
        config: Mapping[str, Any],
        *,
        maximum_rows: int = 50,
    ) -> TabularPreview:
        header_value = config.get("header_row")
        header_row = int(header_value) if header_value not in (None, "", 0, "0") else None
        default_start = header_row + 1 if header_row is not None else 1
        data_start_row = int(config.get("data_start_row", default_start))
        maximum_row_number = max(
            header_row or 1,
            data_start_row + max(1, min(int(maximum_rows), 100)) - 1,
        )
        table, delimiter, encoding = self._table_read(
            Path(source), config, maximum_row_number=maximum_row_number
        )
        return Tabular_PreviewBuild(
            table,
            config,
            resolved_reader_config={
                "delimiter": delimiter,
                "encoding": encoding,
            },
            maximum_rows=maximum_rows,
        )

    def parse(
        self, source: Path, config: Mapping[str, Any], context: TaskContext
    ) -> ParseResult:
        context.raise_if_cancelled()
        table, delimiter, encoding = self._table_read(Path(source), config)
        context.report_progress(0.45, "Delimited table loaded")
        effective_config = {
            **dict(config),
            "delimiter": delimiter,
            "encoding": encoding,
        }
        dataset = Tabular_MappingApply(
            table,
            effective_config,
            dataset_metadata={
                "source_path": str(Path(source).resolve()),
                "source_format": "DELIMITED",
                "delimiter": delimiter,
                "encoding": encoding,
                "tabular_mapping": effective_config,
            },
            plugin_id=self.descriptor.plugin_id,
        )
        quality = Dataset_QualityInspect(dataset)
        dataset = dataset.with_diagnostics(quality.diagnostics)
        context.report_progress(1.0, "Delimited table mapped")
        return ParseResult(dataset, dataset.diagnostics)

    def validate(self, dataset: Dataset) -> list[Diagnostic]:
        return list(Dataset_QualityInspect(dataset).diagnostics)
