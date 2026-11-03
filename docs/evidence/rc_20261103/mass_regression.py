"""Replay the 200 N s fixture and actually export through baseline/current GUI handlers."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from underline_retldc.app.release_smoke import _wait
from underline_retldc.app.settings import SettingsService
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.i18n.service import TranslationService

ROOT = Path(__file__).resolve().parents[3]
BASE = "351ab0b0167eb37bd6312c2bde79181d6225e97f"


def original(name, source, identities):
    raw = subprocess.check_output(["git", "show", BASE + ":" + source], cwd=ROOT)
    identities[source] = hashlib.sha256(raw).hexdigest()
    module = ModuleType(name)
    module.__file__ = str(ROOT / source)
    sys.modules[name] = module
    exec(compile(raw, module.__file__, "exec"), module.__dict__)
    return module


def run(epoch, output):
    output.mkdir(exist_ok=False, parents=True)
    app = QApplication.instance() or QApplication([])
    identities = {}
    cls = MainWindow
    if epoch == "before":
        snapshot = original("baseline_snapshot", "src/underline_retldc/app/export_snapshot.py",
                            identities)
        export = original("baseline_export", "src/underline_retldc/gui/pages/export_page.py",
                          identities)
        main = original("baseline_main", "src/underline_retldc/gui/main_window.py", identities)
        main.ExportSnapshot_Build = snapshot.ExportSnapshot_Build
        main.ExportDialog = export.ExportDialog
        cls = main.MainWindow
    window = cls(TranslationService("en_US"), SettingsService(output / "settings.ini"),
                 project_root=ROOT, user_plugin_directory=output / "plugins")
    errors = []
    window._error_show = lambda error: errors.append(str(error))
    project = ROOT / "tests/fixtures/motor_test_package/v1/synthetic_positive.retldc.json"
    QFileDialog.getOpenFileName = lambda *a, **k: (str(project), "")
    QMessageBox.information = lambda *a, **k: QMessageBox.StandardButton.Ok
    window._project_open_dialog()
    _wait(window, errors)
    window._locale_select("en_US")
    assert abs(window.session.analysis_result.metrics["total_impulse_ns"] - 200) < 1e-8
    old_isp = window.session.analysis_result.metrics["specific_impulse_s"]
    if epoch == "after":
        window.setup_page.motor_edits["propellant_mass_kg"].setText("0.30")
        assert window.session.analysis_result is None
        window._analysis_calculate()
        _wait(window, errors)
    window._export_dialog_show()
    if epoch == "before":
        window.export_dialog.eng_edits["propellant_mass_kg"].setText("0.30")
    else:
        assert window.export_dialog.eng_edits["propellant_mass_kg"].isReadOnly()
    window.export_dialog.set_output_locale("en_US")
    window.export_dialog.set_output_directory(output)
    window.export_dialog.set_selected_exporter_ids(["builtin.exporter.analysis_txt"])
    filename = window.export_dialog.export_filename("builtin.exporter.analysis_txt")
    window._export_execute()
    _wait(window, errors)
    report = (output / filename).read_text(encoding="utf8")
    selected = [line for line in report.splitlines()
                if "Specific Impulse [s]" in line or "Propellant Mass [kg]" in line]
    assert any("0.3" in row for row in selected)
    expected = old_isp if epoch == "before" else old_isp / 2
    assert any(str(round(expected, 2))[:4] in row
               for row in selected if "Specific Impulse" in row), selected
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    data = {"epoch": epoch, "checkout_commit": head, "baseline_commit": BASE,
            "baseline_source_sha256": identities,
            "initial_impulse_ns": 200.0, "initial_isp_s": old_isp, "report_rows": selected,
            "actual_export_sha256": hashlib.sha256((output / filename).read_bytes()).hexdigest()}
    (output / "identity.json").write_text(json.dumps(data, indent=2), encoding="utf8")
    print(json.dumps(data))
    window.task_manager.shutdown(wait=True)
    window._closing = True
    window.close()
    app.processEvents()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("epoch", choices=["before", "after"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.epoch, args.output.resolve())

