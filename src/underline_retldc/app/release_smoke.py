"""Opt-in release validation using generated data and the real desktop workflow."""

from __future__ import annotations

import json
import time
import traceback
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from enum import IntEnum
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from underline_retldc.core.project import Project_Load
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


def _xlsx_write(destination: Path) -> None:
    headers = ("Time (s)", "Pc (MPa)", "F (N)", "e (mm)", "Ab (mm²)", "Kn", "TC1 (K)")
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
            check("product_title", window.windowTitle() == "Underline RETLDC — 0.0.4")
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
            window.process_page.apply_button.click()
            _wait(window, errors)
            window.analyze_page.calculate_button.click()
            _wait(window, errors)
            report["automatic_interval"] = window.session.regions["active_test"]
            report["automatic_interval_metrics"] = dict(window.session.analysis_result.metrics)
            window.chamber_pressure_page.calculate_button.click()
            window.temperature_page.calculate_button.click()
            _wait(window, errors)
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
            report["passed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ReleaseSmokeResult.SUCCESS if report["passed"] else ReleaseSmokeResult.FAILED
