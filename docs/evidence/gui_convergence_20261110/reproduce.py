"""Fresh synthetic input -> ordinary GUI calculation -> saved replay -> no-Qt CLI export.

Run from the repository with .venv/Scripts/python.exe and an explicit output directory.
This is software integration evidence, never a physical load-cell measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from underline_retldc.app.settings import SettingsService
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.i18n.service import TranslationService


def wait(window: MainWindow) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        QApplication.processEvents()
        QTest.qWait(10)
        if window._active_task is None:
            return
    raise RuntimeError("The requested GUI operation did not finish")


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[3]
    source = output / "synthetic_20261110.csv"
    rows = ["time_s,thrust_N,pressure_Pa,temperature_degC\n"]
    for index in range(121):
        seconds = index / 20
        activity = max(0, 1 - abs(seconds - 3))
        rows.append(f"{seconds:.2f},{225 * activity:.6f},"
                    f"{1_800_000 * activity:.6f},{25 + 10 * activity:.6f}\n")
    data = "".join(rows).encode("utf-8")
    if source.exists() and source.read_bytes() != data:
        raise ValueError("Refusing to overwrite a different source input")
    source.write_bytes(data)
    source_hash = hashlib.sha256(data).hexdigest()
    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        TranslationService("en_US"), SettingsService(output / "settings.ini"),
        project_root=repo, bundled_plugin_directory=repo / "plugins",
        user_plugin_directory=output / "user_plugins",
    )
    errors: list[str] = []
    window._error_show = lambda error: errors.append(str(error))
    config = {
        "delimiter": ",", "header_row": 1, "data_start_row": 2,
        "time": {"mode": "column", "column": 0, "unit": "s"},
        "columns": [
            {"column": 0, "usage": "time"},
            {"column": 1, "usage": "data", "channel_id": "thrust",
             "quantity": "force", "role": "thrust", "unit": "N"},
            {"column": 2, "usage": "data", "channel_id": "pressure",
             "quantity": "pressure", "role": "chamber_pressure", "unit": "Pa"},
            {"column": 3, "usage": "data", "channel_id": "temperature",
             "quantity": "temperature", "role": "temperature", "unit": "°C"},
        ], "invalid_row_policy": "error",
    }
    window.import_page.set_source_path(source)
    window.import_page.set_parser_id("builtin.parser.generic_delimited")
    importer = window.registry.get("builtin.parser.generic_delimited")
    window.import_page.tabular_mapping_editor.set_preview(
        importer.preview(source, config), config=config,
    )
    window.import_page.parse_button.click()
    wait(window)
    assert not errors, errors
    window.setup_page.set_motor_metadata({
        "motor_designation": "Synthetic-225-20261110", "manufacturer": "Software fixture",
        "propellant_mass_kg": 0.18, "total_motor_mass_kg": 0.42,
        "diameter_mm": 54, "length_mm": 240,
    })
    window._regions_store({"pre": [0, 1], "active_test": [2, 4], "post": [5, 6]})
    window._workspace_select("thrust_analysis")
    assert window.session.processing_result is None
    assert window.calculate_action.isEnabled()
    window.calculate_action.trigger()
    wait(window)
    assert not errors, errors
    assert abs(window.session.analysis_result.metrics["total_impulse_ns"] - 225) < 1e-9
    project = output / "Synthetic_20261110.retldc.json"
    window._project_save_path(project)
    wait(window)
    assert not errors, errors
    window.close()
    app.processEvents()
    guard = output / "no_qt"
    guard.mkdir(exist_ok=True)
    (guard / "sitecustomize.py").write_text(
        "import sys\nclass Guard:\n def find_spec(self,name,*args):\n"
        "  if name.split('.')[0] in ('PySide6','pyqtgraph'): raise ImportError('Qt unavailable')\n"
        "sys.meta_path.insert(0,Guard())\n", encoding="utf-8",
    )
    motor = output / "motor.tdmotor.json"
    command = [sys.executable, "-X", "utf8", "-m", "underline_retldc.cli",
               "export", str(project), str(motor)]
    completed = subprocess.run(
        command, cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=35,
        env={**os.environ, "PYTHONPATH": os.pathsep.join((str(guard), str(repo / "src")))},
    )
    (output / "cli.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    assert completed.returncode == 0, completed.stderr
    assert source.read_bytes() == data
    package = json.loads(motor.read_text(encoding="utf-8"))
    assert package["source"]["sha256"] == source_hash
    assert abs(package["metrics"]["total_impulse_ns"] - 225) < 1e-9
    receipt = {
        "scope": "New synthetic software fixture; not a device measurement or calibration",
        "command": command, "exit_code": completed.returncode,
        "source_sha256": source_hash,
        "files": {path.name: {"bytes": path.stat().st_size,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for path in (source, project, motor)},
        "content_sha256": package["content_sha256"],
        "metrics": package["metrics"], "motor": package["motor"],
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
