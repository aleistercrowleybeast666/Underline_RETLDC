from __future__ import annotations

import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from xml.etree import ElementTree

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

_SPREADSHEET_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOCUMENT_REL_NAMESPACE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
_PACKAGE_REL_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    if not letters:
        raise ValueError(f"Invalid XLSX cell reference {reference!r}")
    result = 0
    for character in letters.upper():
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


class GenericXlsxParser(TabularParserPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.parser.generic_xlsx",
            plugin_type=PluginType.PARSER,
            version="1.0.0",
            api_version="1",
            name="Generic XLSX",
            description="XLSX reader using explicit reusable Tabular Column Mapping",
            translation_key="parser.generic_xlsx.name",
        )

    def config_schema(self) -> dict[str, Any]:
        hidden = {"x-ui-hidden": True}
        return {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string", "default": "", **hidden},
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
                "reader": "xlsx",
                "preview_rows": 50,
                "preset_supported": True,
            },
        }

    def probe(self, source: Path, context: ProbeContext) -> ProbeResult:
        path = Path(source)
        if not path.is_file():
            return ProbeResult(0.0, "Source is not a readable file")
        try:
            with path.open("rb") as handle:
                signature = handle.read(min(context.max_bytes, 4))
            if signature != b"PK\x03\x04":
                return ProbeResult(0.0, "Not an OOXML ZIP container")
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
        except (OSError, zipfile.BadZipFile) as exc:
            return ProbeResult(0.0, f"Unable to inspect XLSX: {exc}")
        required = {
            "[Content_Types].xml",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
        }
        if not required <= names:
            return ProbeResult(0.0, "OOXML workbook parts are missing")
        confidence = 0.99 if path.suffix.casefold() == ".xlsx" else 0.94
        return ProbeResult(confidence, "Valid OOXML workbook container")

    @staticmethod
    def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        return [
            "".join(node.text or "" for node in item.iter(f"{{{_SPREADSHEET_NAMESPACE}}}t"))
            for item in root.findall(f"{{{_SPREADSHEET_NAMESPACE}}}si")
        ]

    @staticmethod
    def _sheet_entries(archive: zipfile.ZipFile) -> tuple[tuple[str, str], ...]:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relations = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relations.findall(f"{{{_PACKAGE_REL_NAMESPACE}}}Relationship")
        }
        sheets = workbook.find(f"{{{_SPREADSHEET_NAMESPACE}}}sheets")
        if sheets is None:
            raise ValueError("XLSX workbook contains no sheets")
        entries: list[tuple[str, str]] = []
        for sheet in sheets:
            name = sheet.attrib.get("name", "")
            relation_id = sheet.attrib.get(f"{{{_DOCUMENT_REL_NAMESPACE}}}id")
            if relation_id not in targets:
                continue
            target = str(targets[relation_id]).replace("\\", "/")
            target_path = PurePosixPath(target.lstrip("/"))
            if not target_path.parts or target_path.parts[0] != "xl":
                target_path = PurePosixPath("xl") / target_path
            normalized: list[str] = []
            for part in target_path.parts:
                if part == "..":
                    if not normalized:
                        raise ValueError("XLSX worksheet relation escapes the workbook root")
                    normalized.pop()
                elif part not in {"", ".", "/"}:
                    normalized.append(part)
            path = "/".join(normalized)
            if not path.startswith("xl/"):
                raise ValueError("XLSX worksheet relation is outside the workbook root")
            entries.append((name, path))
        if not entries:
            raise ValueError("XLSX workbook contains no readable worksheets")
        return tuple(entries)

    @staticmethod
    def _cell_value(cell: ElementTree.Element, shared: list[str]) -> str | float | None:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            inline = cell.find(f"{{{_SPREADSHEET_NAMESPACE}}}is")
            if inline is None:
                return ""
            return "".join(
                node.text or ""
                for node in inline.iter(f"{{{_SPREADSHEET_NAMESPACE}}}t")
            )
        value_node = cell.find(f"{{{_SPREADSHEET_NAMESPACE}}}v")
        if value_node is None or value_node.text is None:
            return None
        text = value_node.text
        if cell_type == "s":
            try:
                return shared[int(text)]
            except (IndexError, ValueError) as exc:
                raise ValueError("XLSX shared-string index is invalid") from exc
        if cell_type in {"str", "e"}:
            return text
        try:
            return float(text)
        except ValueError:
            return text

    def _rows_read(
        self,
        stream: BinaryIO,
        shared: list[str],
        *,
        maximum_row_number: int | None = None,
    ) -> dict[int, dict[int, str | float | None]]:
        rows: dict[int, dict[int, str | float | None]] = {}
        row_tag = f"{{{_SPREADSHEET_NAMESPACE}}}row"
        cell_tag = f"{{{_SPREADSHEET_NAMESPACE}}}c"
        try:
            iterator = ElementTree.iterparse(stream, events=("end",))
            for _event, element in iterator:
                if element.tag != row_tag:
                    continue
                row_number = int(element.attrib.get("r", len(rows) + 1))
                values: dict[int, str | float | None] = {}
                for cell in element.findall(cell_tag):
                    reference = cell.attrib.get("r", "")
                    values[_column_index(reference)] = self._cell_value(cell, shared)
                rows[row_number] = values
                element.clear()
                if maximum_row_number is not None and row_number >= maximum_row_number:
                    break
        except ElementTree.ParseError as exc:
            raise ValueError(f"XLSX worksheet XML is invalid: {exc}") from exc
        return rows

    def _table_read(
        self,
        source: Path,
        requested_sheet: str,
        *,
        maximum_row_number: int | None = None,
    ) -> tuple[TabularTable, tuple[str, ...], str]:
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"XLSX source does not exist: {path}")
        try:
            with zipfile.ZipFile(path) as archive:
                shared = self._shared_strings(archive)
                entries = self._sheet_entries(archive)
                selected = next(
                    (entry for entry in entries if requested_sheet and entry[0] == requested_sheet),
                    entries[0] if not requested_sheet else None,
                )
                if selected is None:
                    raise ValueError(f"XLSX sheet {requested_sheet!r} does not exist")
                selected_name, sheet_path = selected
                with archive.open(sheet_path, "r") as stream:
                    rows = self._rows_read(
                        stream,
                        shared,
                        maximum_row_number=maximum_row_number,
                    )
        except (KeyError, OSError, zipfile.BadZipFile) as exc:
            raise ValueError(f"Unable to read XLSX workbook {path}: {exc}") from exc
        return TabularTable(rows), tuple(name for name, _path in entries), selected_name

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
        table, sheet_names, selected_sheet = self._table_read(
            Path(source),
            str(config.get("sheet_name", "")).strip(),
            maximum_row_number=maximum_row_number,
        )
        return Tabular_PreviewBuild(
            table,
            config,
            sheet_names=sheet_names,
            selected_sheet=selected_sheet,
            resolved_reader_config={"sheet_name": selected_sheet},
            maximum_rows=maximum_rows,
        )

    def parse(
        self, source: Path, config: Mapping[str, Any], context: TaskContext
    ) -> ParseResult:
        context.raise_if_cancelled()
        table, _sheet_names, selected_sheet = self._table_read(
            Path(source), str(config.get("sheet_name", "")).strip()
        )
        context.report_progress(0.45, "XLSX worksheet loaded")
        effective_config = {**dict(config), "sheet_name": selected_sheet}
        dataset = Tabular_MappingApply(
            table,
            effective_config,
            dataset_metadata={
                "source_path": str(Path(source).resolve()),
                "source_format": "XLSX",
                "sheet": selected_sheet,
                "tabular_mapping": effective_config,
            },
            plugin_id=self.descriptor.plugin_id,
        )
        quality = Dataset_QualityInspect(dataset)
        dataset = dataset.with_diagnostics(quality.diagnostics)
        context.report_progress(1.0, "XLSX mapped")
        return ParseResult(dataset, dataset.diagnostics)

    def validate(self, dataset: Dataset) -> list[Diagnostic]:
        return list(Dataset_QualityInspect(dataset).diagnostics)
