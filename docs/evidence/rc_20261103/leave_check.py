"""Exercise actual Qt leave confirmation buttons on a disposable working project."""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from underline_retldc.app.settings import SettingsService
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.i18n.service import TranslationService

root = Path(__file__).resolve().parents[3]
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
app = QApplication([])
window = MainWindow(TranslationService("en_US"), SettingsService(out / "settings.ini"),
                    project_root=root, user_plugin_directory=out / "plugins")
window.show()
window.setup_page.motor_edits["propellant_mass_kg"].setText("0.15")
original = window.session
errors = []
window._error_show = lambda error: errors.append(str(error))
buttons = QMessageBox.StandardButton
observations = []


def choose(button):
    def respond():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        observations.append(dialog.text())
        assert dialog.button(button).isEnabled()
        dialog.button(button).click()
    QTimer.singleShot(25, window, respond)


choose(buttons.Cancel)
assert not window.close() and window.isVisible() and window.session is original
choose(buttons.Cancel)
window.open_project_action.trigger()
assert window.isVisible() and window.session is original
blocked = out / "ordinary-file"
blocked.write_text("original", encoding="utf8")
original.project_path = blocked / "project.retldc.json"
choose(buttons.Save)
assert not window.close()
for _ in range(1000):
    app.processEvents()
    QTest.qWait(5)
    if errors:
        break
assert errors and window.isVisible() and window.session is original
assert blocked.read_text(encoding="utf8") == "original"
choose(buttons.Discard)
window.close()
app.processEvents()
assert not window.isVisible() and len(observations) == 4
print(json.dumps({"confirmed": ["close.cancel", "open.cancel", "close.save_failure",
                               "close.discard"], "original_file_intact": True,
                  "prompts": observations, "save_failure": errors}, ensure_ascii=False))

