"""Portable-candidate checks using the normal Qt workspace and real offline plugins."""

from __future__ import annotations

import hashlib
import json
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLineEdit,
    QMessageBox,
)

from underline_retldc.app.release_smoke import ReleaseSmokeResult, _temporary_attribute, _wait
from underline_retldc.gui.main_window import MainWindow


def CandidateSmoke_Run(window: MainWindow, output: Path) -> ReleaseSmokeResult:
    checks: list[str] = []
    shots: list[str] = []
    errors: list[str] = []
    report = {
        "checks": checks,
        "screenshots": shots,
        "errors": errors,
        "theme": window._theme,
        "locale": window.translations.locale,
        "device_pixel_ratio": window.devicePixelRatioF(),
    }
    passed = False

    def check(name, outcome):
        if not outcome:
            raise AssertionError(name)
        checks.append(name)

    def capture(name, widget):
        QApplication.processEvents()
        filename = name + ".png"
        if not widget.grab().save(str(output / filename)):
            raise OSError(f"Unable to write screenshot {filename}")
        shots.append(filename)

    def edit_motor():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, QDialog):
            errors.append("Motor property dialog missing")
            return
        try:
            mass = dialog.findChild(QLineEdit, "motorDraft_propellant_mass_kg")
            diameter = dialog.findChild(QLineEdit, "motorDraft_diameter_mm")
            buttons = dialog.findChild(QDialogButtonBox)
            apply = buttons.button(QDialogButtonBox.StandardButton.Apply)
            QTest.keyClicks(mass, "0.15")
            diameter.setText("invalid")
            apply.click()
            check(
                "invalid_input_keeps_draft",
                dialog.isVisible() and mass.text() == "0.15" and diameter.hasFocus(),
            )
            diameter.setText("50")
            dialog.findChild(QLineEdit, "motorDraft_length_mm").setText("200")
            dialog.findChild(QLineEdit, "motorDraft_total_motor_mass_kg").setText("0.75")
            capture("motor-properties", dialog)
            apply.click()
        except Exception:
            errors.append(traceback.format_exc())
        finally:
            if dialog.isVisible():
                dialog.reject()

    try:
        with (
            _temporary_attribute(window, "_error_show", lambda e: errors.append(str(e))),
            _temporary_attribute(
                window, "_leave_decision", lambda: QMessageBox.StandardButton.Discard
            ),
        ):
            window.resize(980, 660)
            source = output / "measurements.csv"
            rows = ["Time (s),F (N),Pc (MPa),TC1 (K)"]
            for i in range(201):
                force = max(0, 100 - abs(i - 100) * 2)
                rows.append(f"{i / 50:.2f},{force},{force / 100:.3f},{293 + force}")
            source.write_text("\n".join(rows) + "\n", encoding="utf8")
            original = hashlib.sha256(source.read_bytes()).hexdigest()
            window.import_page.set_source_entries([(source, 0.0)])
            window._parser_detect()
            _wait(window, errors)
            check("physical_csv_import", window.session.raw_dataset.sample_count == 201)
            check("physical_csv_no_calibration_block", not window.setup_page.input_help.isVisible())
            QTimer.singleShot(60, window, edit_motor)
            window.setup_page.motor_properties.click()
            check(
                "applied_without_enter",
                not errors and window.session.motor_parameters.propellant_mass_kg == 0.15,
            )
            capture("project", window)
            window._workspace_select("thrust_analysis")
            window.process_page.detect_button.click()
            _wait(window, errors)
            check("shared_interval", bool(window.session.regions.get("active_test")))
            check("none_compensation", window.process_page.processor_id() is None)
            window.process_page.apply_button.click()
            _wait(window, errors)
            check("applied_and_analyzed", window.session.analysis_result is not None)
            accepted = window.session.analysis_result
            window.process_page.processor_combo.setCurrentIndex(1)
            check(
                "draft_preserves_previous_result",
                window._processing_draft() is not None
                and window.session.analysis_result is accepted,
            )
            capture("thrust-draft", window)
            window.process_page.restore_button.click()
            check("discard_draft", window._processing_draft() is None)
            for workspace in ("chamber_pressure", "temperature", "data_explorer"):
                window._workspace_select(workspace)
                if workspace != "data_explorer":
                    window.calculate_action.trigger()
                _wait(window, errors)
                capture(workspace, window)
            window._export_dialog_show()
            dialog = window.export_dialog
            dialog.set_selected_exporter_ids(
                ["builtin.exporter.treediagram_motor", "builtin.exporter.analysis_txt"]
            )
            dialog.set_output_directory(output / "export")
            check("read_only_export_mass", dialog.eng_edits["propellant_mass_kg"].isReadOnly())
            capture("export", dialog)
            dialog.export_button.click()
            _wait(window, errors)
            packages = list((output / "export").glob("*.tdmotor.json"))
            check(
                "real_motor_export",
                len(packages) == 1
                and json.loads(packages[0].read_text(encoding="utf8"))["content_sha256"],
            )
            project = output / "analysis.retldc.json"
            window._project_save_path(project)
            _wait(window, errors)
            window._project_new()
            with _temporary_attribute(
                QFileDialog, "getOpenFileName", lambda *a, **k: (str(project), "")
            ):
                window._project_open_dialog()
                _wait(window, errors)
            check("saved_stage_replayed", window.session.analysis_result is not None)
            check("immutable_input", hashlib.sha256(source.read_bytes()).hexdigest() == original)
            window._project_new()
            raw = output / "loadcell.txt"
            raw.write_text("\n".join(f"{i / 50},{i}" for i in range(101)), encoding="utf8")
            window.import_page.set_source_path(raw)
            window.import_page.set_parser_id("builtin.parser.tr_f")
            window.import_page.set_parser_config({"time_unit": "s", "invalid_row_policy": "error"})
            window._source_parse()
            _wait(window, errors)
            check("raw_requires_calibration", window.setup_page.input_help.isVisible())
            help_button = window.setup_page.input_help
            check("raw_action_inside_viewport",
                  help_button.visibleRegion().contains(help_button.rect().center()))
            capture("raw-action", window)
            window.setup_page.input_help.click()
            check("raw_editor_reachable", window.setup_page.calibration_combo.isVisible())
            capture("raw-calibration", window.setup_page.calibration_dialog)
            window.setup_page.set_calibration_config(
                "builtin.calibration.linear",
                {"parameters": {"K": 2.0, "B": 0.0}, "quantity": "force", "unit": "N"},
            )
            window.setup_page.apply_button.click()
            _wait(window, errors)
            check("raw_calibration_applied", window._input_blocker() is None)
            passed = True
    except Exception:
        errors.append(traceback.format_exc())
    finally:
        report["passed"] = passed
        (output / "candidate-check.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf8",
        )
    return ReleaseSmokeResult.SUCCESS if passed else ReleaseSmokeResult.FAILED
