from __future__ import annotations

from pathlib import Path
from threading import Event
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
from test_theory_overlay import _wait
from test_theory_overlay import window as window

from underline_retldc.core.project_data import SourceKind
from underline_retldc.gui.main_window import MainWindow


def _table(path: Path, *, reordered: bool = False) -> None:
    headers = ["Time (s)", "F (N)", "Pc (MPa)"]
    rows = [[i, value, value / 10] for i, value in enumerate([0, 10, 20, 10, 0])]
    if reordered:
        headers = [headers[2], headers[1], headers[0]]
        rows = [[row[2], row[1], row[0]] for row in rows]
    if path.suffix == ".txt":
        path.write_text("\n".join(",".join(map(str, row)) for row in [headers, *rows]),
                        encoding="utf8")
        return
    namespace = "http://schemas.openxmlformats.org"
    xml_rows = []
    for index, row in enumerate([headers, *rows], 1):
        cells = []
        for column, value in enumerate(row):
            address = f"{chr(65 + column)}{index}"
            if isinstance(value, str):
                cells.append(f'<c r="{address}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            else:
                cells.append(f'<c r="{address}"><v>{value}</v></c>')
        xml_rows.append(f'<row r="{index}">{"".join(cells)}</row>')
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", f'<Types xmlns="{namespace}/package/2006/'
                         'content-types"><Default Extension="xml" ContentType="application/xml"/>'
                         '</Types>')
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{namespace}/spreadsheetml/2006/'
                         f'main" xmlns:r="{namespace}/officeDocument/2006/relationships">'
                         '<sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{namespace}/'
                         f'package/2006/relationships"><Relationship Id="rId1" Type="{namespace}/'
                         'officeDocument/2006/relationships/worksheet" '
                         'Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{namespace}/spreadsheetml/'
                         f'2006/main"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>')


def _browse(window: MainWindow, monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *_a, **_k: ([str(path)], ""))
    window.import_page.browse_button.click()
    _wait(window)
    _select_text_parser(window, path)


def _select_text_parser(window: MainWindow, path: Path) -> None:
    # TXT probing remains conservative; choosing Generic Delimited is explicit.
    if path.suffix == ".txt" and window.import_page.selected_parser_id() is None:
        window.import_page.set_parser_id("builtin.parser.generic_delimited")
        _wait(window)


def _enable_preview(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(window, "_tabular_preview_refresh",
                        MainWindow._tabular_preview_refresh.__get__(window))


@pytest.mark.parametrize("extension", [".txt", ".xlsx"])
def test_toolbar_import_adds_theory_without_resetting_existing_project(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extension: str,
) -> None:
    _enable_preview(window, monkeypatch)
    first, second = tmp_path / f"first{extension}", tmp_path / f"second{extension}"
    _table(first)
    _table(second)
    _browse(window, monkeypatch, first)
    original = window.session.project_data
    assert len(original.sources) == 1
    window.import_page.new_kind_combo.setCurrentIndex(1)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *_a, **_k: ([str(second)], ""))
    window._source_open_dialog()
    _wait(window)
    _select_text_parser(window, second)
    assert set(original.sources) <= set(window.session.project_data.sources)
    assert len(window.session.project_data.sources) == 2
    assert window.session.project_data.primary_channels == original.primary_channels
    assert not window._test_errors


@pytest.mark.parametrize("extension", [".txt", ".xlsx"])
def test_second_experiment_preserves_existing_binding_and_saved_mapping(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extension: str,
) -> None:
    _enable_preview(window, monkeypatch)
    first, second = tmp_path / f"first{extension}", tmp_path / f"second{extension}"
    _table(first)
    _table(second)
    _browse(window, monkeypatch, first)
    original = window.session.project_data
    _browse(window, monkeypatch, second)
    if len(window.session.project_data.sources) != 2:
        window.import_page.parse_button.click()
        _wait(window)
    assert len(window.session.project_data.sources) == 2
    assert window.session.project_data.primary_channels == original.primary_channels
    assert window.session.project_data.sources[next(iter(original.sources))] == next(
        iter(original.sources.values())
    )
    assert not window._test_errors


@pytest.mark.parametrize("extension", [".txt", ".xlsx"])
def test_new_theory_detects_own_time_column_and_reimport_after_last_removal(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extension: str,
) -> None:
    _enable_preview(window, monkeypatch)
    first, second = tmp_path / f"first{extension}", tmp_path / f"second{extension}"
    _table(first)
    _table(second, reordered=True)
    _browse(window, monkeypatch, first)
    original = window.session.project_data
    window.import_page.new_kind_combo.setCurrentIndex(1)
    _browse(window, monkeypatch, second)
    assert len(window.session.project_data.sources) == 2
    theory = next(source for source in window.session.project_data.sources.values()
                  if source.source_kind == SourceKind.THEORETICAL)
    assert theory.parser_config["time"]["column"] == 2
    assert window.session.project_data.primary_channels == original.primary_channels
    while window.import_page.source_list.count():
        window.import_page.remove_source_button.click()
        _wait(window)
    window.import_page.new_kind_combo.setCurrentIndex(0)
    _browse(window, monkeypatch, second)
    assert len(window.session.project_data.sources) == 1
    source = next(iter(window.session.project_data.sources.values()))
    assert source.parser_config["time"]["column"] == 2
    assert not window._test_errors


@pytest.mark.parametrize("extension", [".txt", ".xlsx"])
def test_cancel_duplicate_and_failed_import_preserve_completed_results(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extension: str,
) -> None:
    _enable_preview(window, monkeypatch)
    first = tmp_path / f"first{extension}"
    _table(first)
    _browse(window, monkeypatch, first)
    window._regions_store({"pre": None, "active_test": [1, 3], "post": None})
    window._processing_apply()
    _wait(window)
    window._analysis_calculate()
    _wait(window)
    original = window.session.project_data
    analysis = window.session.analysis_result
    processing = window.session.processing_result
    regions = dict(window.session.regions)
    selection = window.import_page.selected_entry_id()
    mapping = window.import_page.parser_config()
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *_a, **_k: ([], ""))
    window._source_open_dialog()
    window._source_browse()
    assert window.import_page.selected_entry_id() == selection
    assert window.import_page.parser_config() == mapping
    _browse(window, monkeypatch, first)
    assert window.import_page.selected_entry_id() == selection
    assert window.session.project_data is original

    second = tmp_path / f"second{extension}"
    _table(second)
    _browse(window, monkeypatch, second)  # User accidentally leaves Experimental selected.
    assert window.session.analysis_result is analysis
    assert window.session.processing_result is processing
    assert window.session.regions == regions
    before_failure = window.session.project_data
    config = window.import_page.parser_config()
    config["time"] = {"mode": "column", "column": 999, "unit": "s"}
    config["columns"][0]["usage"] = "ignore"
    window.import_page.set_parser_config(config)
    window.import_page.parse_button.click()
    _wait(window)
    assert window._test_errors  # Real parser rejects the invalid time-column mapping.
    assert window.session.project_data is before_failure
    assert window.session.analysis_result is analysis
    assert window.session.processing_result is processing
    assert window.session.regions == regions


@pytest.mark.parametrize("remove_index", [0, 1])
def test_delete_either_source_then_reimport_preserves_other_source_mapping(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, remove_index: int,
) -> None:
    _enable_preview(window, monkeypatch)
    first, second = tmp_path / "first.xlsx", tmp_path / "second.xlsx"
    _table(first)
    _table(second, reordered=True)
    _browse(window, monkeypatch, first)
    window.import_page.new_kind_combo.setCurrentIndex(1)
    _browse(window, monkeypatch, second)
    previous = tuple(window.session.project_data.sources.values())
    survivor = previous[1 - remove_index]
    window.import_page.source_list.setCurrentRow(remove_index)
    window.import_page.remove_source_button.click()
    _wait(window)
    assert window.session.project_data.sources[survivor.id] is survivor
    assert window.import_page.parser_config() == dict(survivor.parser_config)
    window.import_page.new_kind_combo.setCurrentIndex(remove_index)
    _browse(window, monkeypatch, previous[remove_index].path)
    assert len(window.session.project_data.sources) == 2
    assert window.session.project_data.sources[survivor.id] is survivor
    restored = next(source for source in window.session.project_data.sources.values()
                    if source.id != survivor.id)
    assert restored.parser_config["time"]["column"] == (0 if remove_index == 0 else 2)
    assert not window._test_errors


@pytest.mark.parametrize("change", ["remove", "kind", "mapping", "new_project", "close"])
def test_delayed_parse_cannot_commit_after_import_input_changes(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    from test_theory_overlay import _experimental_import

    _experimental_import(window, tmp_path / "first.csv")
    original = window.session.project_data
    second = tmp_path / "second.txt"
    second.write_text("0,0\n1,10\n2,0\n", encoding="utf-8")
    window.import_page.add_source_paths([second])
    window.import_page.set_parser_id("builtin.parser.tr_f")
    window.import_page.set_parser_config(
        {"delimiter": ",", "time_unit": "s", "invalid_row_policy": "skip"}
    )
    parser = window.registry.get("builtin.parser.tr_f")
    original_parse = parser.parse
    started, release = Event(), Event()

    def delayed_parse(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return original_parse(*args, **kwargs)

    monkeypatch.setattr(parser, "parse", delayed_parse)
    window._source_parse()
    assert started.wait(2)
    try:
        if change == "remove":
            window.import_page.remove_source_button.click()
            window.import_page.add_source_paths([second])  # Same bytes, new pending identity.
        elif change == "kind":
            window.import_page.source_kind_combo.setCurrentIndex(1)
        elif change == "mapping":
            window.import_page.set_parser_config({"delimiter": ";", "time_unit": "s"})
        elif change == "new_project":
            window._project_new()
        else:
            window.close()
    finally:
        release.set()
    for _ in range(300):
        QApplication.processEvents()
        QTest.qWait(10)
        if window._active_task is None:
            break
    assert window._active_task is None
    if change == "new_project":
        assert not window.session.project_data.sources
    else:
        assert window.session.project_data is original
    assert not window._test_errors


def test_late_preview_does_not_overwrite_another_source_mapping(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_preview(window, monkeypatch)
    first, second = tmp_path / "first.xlsx", tmp_path / "second.xlsx"
    _table(first)
    _table(second, reordered=True)
    _browse(window, monkeypatch, first)
    original = window.session.project_data
    window.import_page.new_kind_combo.setCurrentIndex(1)
    window.import_page.add_source_paths([second])
    window._auto_preview_timer.stop()
    parser = window.registry.get("builtin.parser.generic_xlsx")
    preview = parser.preview
    started, release = Event(), Event()

    def delayed_preview(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return preview(*args, **kwargs)

    monkeypatch.setattr(parser, "preview", delayed_preview)
    window._tabular_auto_preview()
    assert started.wait(2)
    try:
        window.import_page.source_list.setCurrentRow(0)
        expected = window.import_page.parser_config()
    finally:
        release.set()
    _wait(window)
    assert window.import_page.parser_config() == expected
    assert expected["time"]["column"] == 0
    assert window.session.project_data is original
    window.import_page.source_list.setCurrentRow(1)
    _wait(window)
    assert window.import_page.parser_config()["time"]["column"] == 2
    assert len(window.session.project_data.sources) == 2
    assert not window._test_errors


@pytest.mark.parametrize("kind", [SourceKind.EXPERIMENTAL, SourceKind.THEORETICAL])
def test_two_column_txt_second_source_needs_explicit_parser_and_keeps_binding(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: SourceKind,
) -> None:
    for index in range(2):
        source = tmp_path / f"raw{index}.txt"
        source.write_text("0,0\n1,10\n2,0\n", encoding="utf-8")
        if index:
            original = window.session.project_data
            window.import_page.new_kind_combo.setCurrentIndex(
                window.import_page.new_kind_combo.findData(kind.value)
            )
        monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                            lambda *_a, path=source, **_k: ([str(path)], ""))
        window._source_browse()
        _wait(window)
        assert window.import_page.selected_parser_id() is None
        if index:
            assert window.session.project_data is original
        window.import_page.set_parser_id("builtin.parser.tr_f")
        window.import_page.parse_button.click()
        _wait(window)
        assert len(window.session.project_data.sources) == index + 1
    assert window.session.project_data.primary_channels == original.primary_channels
    assert not window._test_errors


def test_pending_mapping_drafts_keep_time_and_sheet_without_preview(
    window: MainWindow, tmp_path: Path,
) -> None:
    first, second = tmp_path / "first.xlsx", tmp_path / "second.xlsx"
    window.import_page.add_source_paths([first])
    window.import_page.set_parser_id("builtin.parser.generic_xlsx")
    config = {"sheet_name": "User sheet", "header_row": 4, "data_start_row": 5,
              "time": {"mode": "column", "column": 8, "unit": "ms"},
              "columns": [{"column": 8, "usage": "time"}]}
    window.import_page.set_parser_config(config)
    expected = window.import_page.parser_config()
    assert expected["sheet_name"] == "User sheet"
    assert expected["time"]["column"] == 8
    window.import_page.add_source_paths([second])
    assert window.import_page.parser_config()["columns"] == []
    window.import_page.source_list.setCurrentRow(0)
    assert window.import_page.parser_config() == expected
    window._import_pending_invalidate()


def test_edit_after_detection_cancels_queued_auto_import(
    window: MainWindow, tmp_path: Path,
) -> None:
    source = tmp_path / "first.xlsx"
    _table(source)
    window.import_page.add_source_paths([source])
    window.import_page.set_parser_id("builtin.parser.generic_xlsx")
    window._auto_preview_timer.stop()
    window._tabular_auto_preview()
    window._active_task.wait(timeout=5)
    window._task_poll()  # Deliver detection, leaving its automatic Parse timer queued.
    assert window._tabular_auto_parse_pending
    config = window.import_page.parser_config()
    config["data_start_row"] = 3
    window.import_page.set_parser_config(config)
    QApplication.processEvents()
    assert window._active_task is None
    assert not window.session.project_data.sources
    assert not window._tabular_auto_parse_pending
