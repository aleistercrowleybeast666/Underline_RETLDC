"""Opt-in release validation using generated data and the real desktop workflow."""

from __future__ import annotations

import json
import time
import traceback
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import IntEnum
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QStyle,
    QStyleOptionSlider,
)

from underline_retldc.core.project import Project_Load
from underline_retldc.core.project_data import SourceKind
from underline_retldc.core.registry import PluginLoadResult
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.gui.plugin_install_dialog import PluginInstallPreviewDialog


class ReleaseSmokeResult(IntEnum):
    SUCCESS = 0
    FAILED = 1


@contextmanager
def _temporary_attribute(target: Any, name: str, value: Any) -> Iterator[Any]:
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield original
    finally:
        setattr(target, name, original)


def _wait(window: MainWindow, errors: list[str], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    idle = 0
    while time.monotonic() < deadline:
        QApplication.processEvents()
        QTest.qWait(20)
        if errors:
            raise AssertionError("\n".join(errors))
        idle = idle + 1 if window._active_task is None else 0
        if idle >= 5:
            return
    raise TimeoutError("Release smoke task did not finish")


def _xlsx_write(destination: Path, *, time_last: bool = False) -> None:
    headers = ("Time (s)", "Pc (MPa)", "F (N)", "e (mm)", "Ab (mm²)", "Kn", "TC1 (K)")
    if time_last:
        headers = (*headers[1:], headers[0])
    data = []
    for index, timestamp in enumerate(np.linspace(0.0, 10.0, 4001), start=2):
        activity = max(0.0, 1.0 - abs(float(timestamp) - 5.0) / 3.0)
        row = (
            timestamp,
            activity * 9.0,
            activity * 2000.0,
            timestamp,
            20.0,
            3.0,
            300.0 + activity * 100.0,
        )
        if time_last:
            row = (*row[1:], row[0])
        cells = "".join(
            f'<c r="{chr(65 + column)}{index}"><v>{value}</v></c>'
            for column, value in enumerate(row)
        )
        data.append(f'<row r="{index}">{cells}</row>')
    header = "".join(
        f'<c r="{chr(65 + column)}1" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
        for column, value in enumerate(headers)
    )
    namespace = "http://schemas.openxmlformats.org"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'<Types xmlns="{namespace}/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{namespace}/spreadsheetml/2006/main" '
            f'xmlns:r="{namespace}/officeDocument/2006/relationships">'
            '<sheets><sheet name="Result" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{namespace}/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{namespace}/officeDocument/2006/'
            'relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{namespace}/spreadsheetml/2006/main"><sheetData>'
            f'<row r="1">{header}</row>{"".join(data)}</sheetData></worksheet>',
        )


def _import_lifecycle_check(
    window: MainWindow, output: Path, errors: list[str], check: Callable[[str, bool], None],
) -> None:
    """Native/portable import acceptance with separately generated TXT and XLSX inputs."""
    page = window.import_page
    for extension in ("txt", "xlsx"):
        paths = [output / f"import_{index}.{extension}" for index in range(2)]
        for index, path in enumerate(paths):
            if extension == "txt":
                path.write_text("0,0\n1,10\n2,0\n", encoding="utf-8")
            else:
                _xlsx_write(path, time_last=bool(index))
        for kind in (SourceKind.EXPERIMENTAL, SourceKind.THEORETICAL):
            window._project_new()
            page.new_kind_combo.setCurrentIndex(0)
            prefix = f"import_{extension}_{kind.value}"

            def browse(path: Path, *, toolbar: bool = False,
                       raw_text: bool = extension == "txt") -> None:
                with _temporary_attribute(
                    QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(path)], "")
                ):
                    if toolbar:
                        window._source_open_dialog()
                    else:
                        page.browse_button.click()
                    _wait(window, errors)
                if raw_text:
                    page.set_parser_id("builtin.parser.tr_f")
                    page.parse_button.click()
                    _wait(window, errors)

            browse(paths[0])
            first = window.session.project_data
            check(f"{prefix}_first", len(first.sources) == 1)
            page.new_kind_combo.setCurrentIndex(page.new_kind_combo.findData(kind.value))
            browse(paths[1], toolbar=True)
            check(f"{prefix}_append", len(window.session.project_data.sources) == 2)
            check(f"{prefix}_bindings", window.session.project_data.primary_channels
                  == first.primary_channels)
            if extension == "xlsx":
                check(f"{prefix}_own_time_column", page.parser_config()["time"]["column"] == 6)
            before = window.session.project_data
            selected = page.selected_entry_id()
            with _temporary_attribute(QFileDialog, "getOpenFileNames", lambda *a, **k: ([], "")):
                window._source_open_dialog()
            check(f"{prefix}_cancel", window.session.project_data is before
                  and page.selected_entry_id() == selected)
            with _temporary_attribute(
                QFileDialog, "getOpenFileNames", lambda *a, path=paths[1], **k: ([str(path)], "")
            ):
                window._source_browse()
                _wait(window, errors)
            check(f"{prefix}_duplicate", window.session.project_data is before
                  and page.selected_entry_id() == selected)
            page.remove_source_button.click()
            _wait(window, errors)
            check(f"{prefix}_remove", len(window.session.project_data.sources) == 1)
            browse(paths[1])
            check(f"{prefix}_reimport", len(window.session.project_data.sources) == 2)
            while page.source_list.count():
                page.remove_source_button.click()
                _wait(window, errors)
            browse(paths[1])
            check(f"{prefix}_reimport_after_empty", len(window.session.project_data.sources) == 1)
            if extension == "xlsx":
                check(f"{prefix}_time_after_empty", page.parser_config()["time"]["column"] == 6)
    window._project_new()


def _plugin_zip_write(destination: Path) -> str:
    plugin_id = "release.smoke.parser"
    manifest = {
        "plugin_id": plugin_id,
        "plugin_type": "parser",
        "api_version": "1",
        "version": "1.0.0",
        "entry": "plugin:SmokeParser",
        "name": "Release Smoke Parser",
    }
    code = (
        "from underline_retldc.plugin_api.common import PluginDescriptor, PluginType, ProbeResult\n"
        "from underline_retldc.plugin_api.parser import ParserPlugin\n"
        "class SmokeParser(ParserPlugin):\n"
        "    @property\n"
        "    def descriptor(self):\n"
        f"        return PluginDescriptor({plugin_id!r}, PluginType.PARSER, "
        "'1.0.0', '1', 'Release Smoke Parser', '')\n"
        "    def probe(self, source, context): return ProbeResult(0.0, 'smoke')\n"
        "    def config_schema(self): return {'type': 'object'}\n"
        "    def parse(self, source, config, context): raise NotImplementedError\n"
        "    def validate(self, dataset): return []\n"
    )
    with zipfile.ZipFile(destination, "w") as archive:
        archive.writestr("wrapper/parser/plugin.json", json.dumps(manifest))
        archive.writestr("wrapper/parser/plugin.py", code)
    return plugin_id


def _source_workflow_check(
    window: MainWindow,
    output: Path,
    source: Path,
    errors: list[str],
    report: dict[str, Any],
    check: Callable[[str, bool], None],
) -> None:
    """Exercise v0.1 Source controls with the generated fixture, also inside the EXE."""
    original_bytes = source.read_bytes()
    experimental_metrics = dict(window.session.analysis_result.metrics)
    bindings = window.session.project_data.primary_channels
    regions = dict(window.session.regions)
    processing = window.session.processing_result
    exports = window.export_dialog.selected_exporter_ids()
    page = window.import_page
    page.new_kind_combo.setCurrentIndex(page.new_kind_combo.findData("theoretical"))
    with _temporary_attribute(
        QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(source)], "")
    ):
        page.browse_button.click()
        _wait(window, errors)
    if len(window.session.project_data.sources) != 2:
        page.parse_button.click()
        _wait(window, errors)
    check("source_dual_origin_import", len(window.session.project_data.sources) == 2)
    theory = next(item for item in window.session.project_data.sources.values()
                  if item.source_kind == SourceKind.THEORETICAL)
    profiles: dict[str, dict[str, Any]] = {}
    window._locale_select("en_US")
    window.resize(1280, 820)
    for result_page in (window.analyze_page, *window._measurement_pages()):
        controls = result_page.source_analysis
        check(f"source_two_roles_{controls.workspace_id}", (
            controls.source_combo.count() == 2
            and [controls.source_combo.itemText(i) for i in range(2)]
            == ["Experimental", "Theoretical"]
        ))
        controls.source_combo.setCurrentIndex(controls.source_combo.findData(theory.id))
        check(f"source_parameters_visible_{controls.workspace_id}",
              not controls.parameter_scroll.isHidden())
        if controls.workspace_id == "data_explorer":
            reference = next(item.reference.stable_id for item in controls._available()
                             if item.dataset.channel(item.channel_id).semantic_role == "thrust")
            controls.channel_combo.setCurrentIndex(controls.channel_combo.findData(reference))
        check(f"source_project_mass_{controls.workspace_id}",
              controls.config().propellant_mass_kg is None
              and controls.config().mass_source == "project")
        check(f"source_compact_controls_{controls.workspace_id}",
              not hasattr(controls, "mass_spin") and not hasattr(controls, "stage_combo")
              and not hasattr(controls, "processor_combo") and controls.notice.isHidden())
        result_page.calculate_button.click()
        _wait(window, errors)
        state = controls.selected_state()
        check(f"source_calculated_{controls.workspace_id}", state is not None and state.completed)
        profiles[controls.workspace_id] = {
            key: dict(value.metrics) for key, value in state.results.items()
        }
        check(f"source_result_table_{controls.workspace_id}",
              result_page.metrics_table.rowCount() > 0)
        window._workspace_select(controls.workspace_id)
        _wait(window, errors)
        if controls.workspace_id in {"thrust_analysis", "chamber_pressure"}:
            filename = f"source_{controls.workspace_id}.png"
            window.grab().save(str(output / filename))
            report["screenshots"].append({"file": filename, "actual_size": [1280, 820]})
    thrust_metrics = next(iter(profiles["thrust_analysis"].values()))
    check("source_full_record_impulse", np.isclose(thrust_metrics["total_impulse_ns"], 6000.0))
    check("source_missing_mass_isp_unavailable", thrust_metrics["specific_impulse_s"] is None)
    check("source_import_preserves_processing", window.session.processing_result is processing)
    overlay = window.process_page.theory_overlay
    for shift in (-0.375, 1.25):
        overlay.shift_spin.setValue(shift)
        _wait(window, errors)
        check(f"source_shift_{shift}", np.isclose(
            window.session.project_data.sources[theory.id].display_transform.shift_s, shift
        ))
    overlay.align_button.click()
    _wait(window, errors)
    detection = window.session.project_data.sources[theory.id].display_transform.detected_test
    check("source_test_start_aligned", detection is not None and np.isclose(
        overlay.shift_spin.value(), regions["active_test"][0] - detection.regions.burn.start,
    ))
    aligned = overlay.shift_spin.value()
    overlay.align_button.click()
    check("source_alignment_idempotent", overlay.shift_spin.value() == aligned)
    window._workspace_select("thrust_analysis")
    window.thrust_analysis_page.shell.controls_scroll.ensureWidgetVisible(overlay.shift_slider)
    QApplication.processEvents()
    slider = overlay.shift_slider
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    handle = slider.style().subControlRect(
        QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, slider,
    )
    QTest.mousePress(slider, Qt.MouseButton.LeftButton, pos=handle.center())
    QTest.mouseMove(slider, handle.center() + QPoint(30, 0), delay=30)
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=handle.center() + QPoint(30, 0))
    check("source_slider_fine_tune", overlay.shift_spin.value() != aligned)
    check("source_shared_shift", all(
        page.theory_overlay.shift_spin.value() == overlay.shift_spin.value()
        for page in window._measurement_pages()
    ))
    overlay.shift_spin.setValue(.5)
    overlay.curve_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    check("source_hidden", bool(
        window.session.project_data.sources[theory.id].display_transform.hidden_curve_ids
    ))
    overlay.curve_list.item(0).setCheckState(Qt.CheckState.Checked)
    check("source_visible", not (
        window.session.project_data.sources[theory.id].display_transform.hidden_curve_ids
    ))
    for workspace_id, expected in profiles.items():
        state = window.session.source_analyses[f"{theory.id}/{workspace_id}"]
        check(f"source_display_preserves_{workspace_id}", {
            key: dict(value.metrics) for key, value in state.results.items()
        } == expected)
    check("source_experiment_isolation", (
        window.session.project_data.primary_channels == bindings
        and window.session.regions == regions
        and dict(window.session.analysis_result.metrics) == experimental_metrics
        and window.export_dialog.selected_exporter_ids() == exports
    ))
    project = output / "source_workflow.json"
    window._project_save_path(project)
    _wait(window, errors)
    window._project_new()
    with _temporary_attribute(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(project), "")
    ):
        window._project_open_dialog()
        _wait(window, errors)
    check("source_reopen_display", (
        window.session.project_data.sources[theory.id].display_transform.detected_test is not None
        and window.session.project_data.sources[theory.id].display_transform.shift_s == .5
    ))
    for workspace_id, expected in profiles.items():
        state = window.session.source_analyses[f"{theory.id}/{workspace_id}"]
        check(f"source_reopened_{workspace_id}", state.completed and {
            key: dict(value.metrics) for key, value in state.results.items()
        } == expected)
    window.process_page.theory_overlay.reset_button.click()
    check("source_reset_timing", not (
        window.session.project_data.sources[theory.id].display_transform.zero_start
        or window.session.project_data.sources[theory.id].display_transform.shift_s
    ))
    shared_processing = window.session.processing_result
    controls = window.analyze_page.source_analysis
    for mass in (.1, .2, None):
        window.setup_page.motor_edits["propellant_mass_kg"].setText(
            str(mass) if mass is not None else "",
        )
        key = f"{theory.id}/thrust_analysis"
        check(f"shared_mass_invalidates_{mass}", window.session.analysis_result is None
              and not window.session.source_analyses[key].completed)
        controls.source_combo.setCurrentIndex(0)
        window.analyze_page.calculate_button.click()
        _wait(window, errors)
        controls.source_combo.setCurrentIndex(controls.source_combo.findData(theory.id))
        window.analyze_page.calculate_button.click()
        _wait(window, errors)
        state = controls.selected_state()
        check(f"shared_mass_calculated_{mass}", state is not None and state.completed)
        for origin, result in (
            ("experimental", window.session.analysis_result),
            ("theoretical", next(iter(state.results.values()))),
        ):
            impulse = result.metrics["total_impulse_ns"]
            isp = result.metrics["specific_impulse_s"]
            check(f"shared_mass_isp_{origin}_{mass}",
                  isp is None if mass is None else np.isclose(isp, impulse / (mass * 9.80665)))
        check(f"shared_mass_preserves_inputs_{mass}", (
            window.session.processing_result is shared_processing
            and window.session.project_data.primary_channels == bindings
            and window.session.regions == regions
        ))
    row = next(index for index in range(page.source_list.count())
               if page.source_list.item(index).data(page.SOURCE_ID_ROLE) == theory.id)
    page.source_list.setCurrentRow(row)
    page.remove_source_button.click()
    _wait(window, errors)
    check("source_precise_removal", (
        len(window.session.project_data.sources) == 1
        and theory.id not in window.session.project_data.sources
        and not window.session.source_analyses
        and dict(window.session.analysis_result.metrics) == experimental_metrics
        and window.session.project_data.primary_channels == bindings
    ))
    window._project_save_path(project)
    _wait(window, errors)
    window._project_new()
    with _temporary_attribute(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(project), "")
    ):
        window._project_open_dialog()
        _wait(window, errors)
    check("source_removal_reopened", (
        len(window.session.project_data.sources) == 1
        and not window.session.source_analyses
        and dict(window.session.analysis_result.metrics) == experimental_metrics
    ))
    check("source_original_bytes_preserved", source.read_bytes() == original_bytes)
    report["source_workflow"] = {
        "fixture": "generated_4001.xlsx; generated synthetic data, not supplied Library files",
        "scientific_stubs": False,
        "automatic_preview_enabled": True,
        "profiles": profiles,
        "propellant_mass_supplied": False,
    }


def ReleaseSmoke_Run(window: MainWindow, output: Path) -> ReleaseSmokeResult:
    """Write a report and screenshots; never touch user sources or saved settings."""
    output.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    report: dict[str, Any] = {"passed": False, "checks": [], "screenshots": []}

    def check(name: str, passed: bool) -> None:
        if not passed:
            raise AssertionError(name)
        report["checks"].append(name)

    try:
        with (
            _temporary_attribute(window, "_error_show", lambda error: errors.append(str(error))),
            _temporary_attribute(
                QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok
            ),
        ):
            _wait(window, errors)
            check("product_title", window.windowTitle() == "Underline RETLDC — 0.1.0")
            check("default_correction_none", window.process_page.processor_id() is None)
            report["plugin_loaded_at_start"] = any(
                record.plugin_id == "release.smoke.parser"
                and record.result is PluginLoadResult.LOADED
                for record in window.registry.records
            )
            source = output / "generated_4001.xlsx"
            _xlsx_write(source)
            window.import_page.set_source_entries([(source, 0.0)])
            window._parser_detect()
            _wait(window, errors)
            dataset = window.session.raw_dataset
            check("xlsx_auto_parse", dataset is not None and dataset.sample_count == 4001)
            roles = [channel.semantic_role for channel in dataset.channels.values()]
            check("auxiliary_columns_preserved", roles.count("auxiliary") == 3)
            check(
                "advanced_collapsed",
                not window.import_page.tabular_mapping_editor.advanced_button.isChecked(),
            )
            thrust = next(ch for ch in dataset.channels.values() if ch.semantic_role == "thrust")
            pressure = next(
                ch for ch in dataset.channels.values() if ch.semantic_role == "chamber_pressure"
            )
            report["generated_fixture_metrics"] = {
                "samples": dataset.sample_count,
                "peak_thrust_n": float(np.max(thrust.values)),
                "peak_pressure_mpa": float(np.max(pressure.values)),
                "full_raw_impulse_ns": float(np.trapezoid(thrust.values, dataset.time)),
            }
            check(
                "generated_fixture_numbers",
                np.isclose(np.max(thrust.values), 2000.0)
                and np.isclose(np.max(pressure.values), 9.0)
                and np.isclose(np.trapezoid(thrust.values, dataset.time), 6000.0),
            )
            window.process_page.detect_button.click()
            _wait(window, errors)
            check("automatic_interval", bool(window.session.regions.get("active_test")))
            report["automatic_interval"] = list(window.session.regions["active_test"])
            start_edit = window.process_page.region_edits["active_test"][0]
            start_edit.setValue(start_edit.value() + 0.1)
            report["manual_interval"] = list(window.session.regions["active_test"])
            check("manual_experiment_start", (
                window.session.segmentation_manually_modified
                and np.isclose(report["manual_interval"][0],
                               report["automatic_interval"][0] + 0.1)
            ))
            window.process_page.apply_button.click()
            _wait(window, errors)
            window.analyze_page.calculate_button.click()
            _wait(window, errors)
            report["accepted_interval_metrics"] = dict(window.session.analysis_result.metrics)
            window.chamber_pressure_page.calculate_button.click()
            window.temperature_page.calculate_button.click()
            _wait(window, errors)
            _source_workflow_check(window, output, source, errors, report, check)
            reference = window.chamber_pressure_page
            check("reference_default", np.isclose(reference.reference_pressure_pa, 101325.0))
            reference.reference_spin.setValue(0.2)
            check("reference_edit", np.isclose(reference.reference_pressure_pa, 200000.0))
            window._display_unit_select("pressure", "Pa")
            check("reference_unit_invariant", np.isclose(reference.reference_pressure_pa, 200000.0))
            window._display_unit_select("pressure", "MPa")
            for theme in ("light", "dark"):
                window._theme_select(theme)
                for locale in ("zh_CN", "en_US"):
                    window._locale_select(locale)
                    for width, height in ((980, 640), (1280, 820)):
                        window.resize(width, height)
                        for page_id in ("thrust_analysis", "chamber_pressure", "temperature"):
                            window._workspace_select(page_id)
                            _wait(window, errors)
                            page = window.stack.currentWidget()
                            shell = page.shell
                            check(
                                f"layout_{theme}_{locale}_{width}_{page_id}",
                                shell.plot.width() >= 250
                                and shell.results.width() >= 220
                                and not shell.splitter.childrenCollapsible(),
                            )
                            filename = f"{theme}_{locale}_{width}_{page_id}.png"
                            window.grab().save(str(output / filename))
                            report["screenshots"].append(
                                {
                                    "file": filename,
                                    "requested_size": [width, height],
                                    "actual_size": [window.width(), window.height()],
                                }
                            )
                            if page_id == "chamber_pressure":
                                shell.controls_scroll.ensureWidgetVisible(reference.reference_spin)
                                QApplication.processEvents()
                                check(
                                    f"reference_control_{theme}_{locale}_{width}",
                                    reference.reference_spin.width() >= 100
                                    and reference.reference_spin.isVisible(),
                                )
                                window.grab().save(str(output / f"reference_{filename}"))
                                shell.controls_scroll.verticalScrollBar().setValue(0)
            window._locale_select("en_US")
            dialog = window.export_dialog
            window._export_dialog_show()
            QApplication.processEvents()
            available_exports = {
                key for key, checkbox in dialog.exporter_checks.items() if checkbox.isEnabled()
            }
            check("export_open_selects_all",
                  set(dialog.selected_exporter_ids()) == available_exports)
            first_export = next(iter(available_exports))
            dialog.exporter_checks[first_export].setChecked(False)
            window._export_availability_update()
            check("export_manual_uncheck_survives_refresh",
                  not dialog.exporter_checks[first_export].isChecked())
            dialog.select_all_button.click()
            check("export_select_all_button",
                  set(dialog.selected_exporter_ids()) == available_exports)
            check("export_locked_items_unchecked", all(
                checkbox.isEnabled() or not checkbox.isChecked()
                for checkbox in dialog.exporter_checks.values()
            ))
            dialog.exporter_checks[first_export].setChecked(False)
            dialog.hide()
            window._locale_select("zh_CN")
            window._export_dialog_show()
            QApplication.processEvents()
            check("export_reopen_selects_all",
                  set(dialog.selected_exporter_ids()) == available_exports)
            check("export_select_all_zh_label", dialog.select_all_button.text() == "全选")
            dialog.grab().save(str(output / "export_select_all.png"))
            report["screenshots"].append({"file": "export_select_all.png"})
            dialog.hide()
            window._locale_select("en_US")
            window.export_dialog.set_output_directory(output / "exports")
            window.export_dialog.set_output_locale("en_US")
            ids = (
                "builtin.exporter.csv",
                "builtin.exporter.analysis_json",
                "builtin.exporter.analysis_txt",
                "builtin.exporter.thrust_png",
                "builtin.exporter.chamber_pressure_png",
                "builtin.exporter.temperature_png",
            )
            window.export_dialog.set_selected_exporter_ids(ids)
            window._export_execute()
            _wait(window, errors)
            check(
                "formal_exports",
                all(
                    (output / "exports" / window.export_dialog.export_filename(plugin_id)).is_file()
                    for plugin_id in ids
                ),
            )
            window.process_page.set_processing_config(
                "builtin.processor.vertical_linear_baseline", {}
            )
            window.process_page.apply_button.click()
            _wait(window, errors)
            project = output / "explicit_processor.json"
            window._project_save_path(project)
            _wait(window, errors)
            check(
                "explicit_processor_saved",
                Project_Load(project).processors[0].id
                == "builtin.processor.vertical_linear_baseline",
            )
            window._project_new()
            with _temporary_attribute(
                QFileDialog, "getOpenFileName", lambda *a, **k: (str(project), "")
            ):
                window._project_open_dialog()
                _wait(window, errors)
            check(
                "explicit_processor_restored",
                window.process_page.processor_id() == "builtin.processor.vertical_linear_baseline",
            )
            check(
                "pressure_reference_restored",
                np.isclose(window.chamber_pressure_page.reference_pressure_pa, 200000.0),
            )
            package = output / "generated_plugin.zip"
            plugin_id = _plugin_zip_write(package)

            def message_exec(box: QMessageBox) -> int:
                button = box.button(QMessageBox.StandardButton.Yes)
                if button is None:
                    button = box.button(QMessageBox.StandardButton.Ok)
                QTimer.singleShot(0, button.click)
                return original_message_exec(box)

            def preview_exec(dialog: PluginInstallPreviewDialog) -> int:
                QTimer.singleShot(0, dialog.install_button.click)
                return original_preview_exec(dialog)

            if not report["plugin_loaded_at_start"]:
                with (
                    _temporary_attribute(
                        QInputDialog,
                        "getItem",
                        lambda *a, **k: (
                            window.translations.translate("plugins.install_source_zip"),
                            True,
                        ),
                    ),
                    _temporary_attribute(
                        QFileDialog, "getOpenFileName", lambda *a, **k: (str(package), "")
                    ),
                    _temporary_attribute(
                        QMessageBox, "exec", message_exec
                    ) as original_message_exec,
                    _temporary_attribute(
                        PluginInstallPreviewDialog, "exec", preview_exec
                    ) as original_preview_exec,
                    _temporary_attribute(
                        QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok
                    ),
                ):
                    window._plugin_install_dialog()
                    check("plugin_global_progress", window._active_task is not None)
                    _wait(window, errors)
            check(
                "plugin_loaded",
                any(
                    record.plugin_id == plugin_id and record.result is PluginLoadResult.LOADED
                    for record in window.registry.records
                ),
            )
            window._plugins_refresh()
            _wait(window, errors)
            check("plugin_rediscovered", window.registry.get(plugin_id) is not None)
            window._source_removed(str(source))
            check(
                "source_removal",
                not window.session.project_data.sources
                and window.session.analysis_result is None
                and not window.chamber_pressure_page.analysis_plot._series,
            )
            _import_lifecycle_check(window, output, errors, check)
            report["passed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ReleaseSmokeResult.SUCCESS if report["passed"] else ReleaseSmokeResult.FAILED
