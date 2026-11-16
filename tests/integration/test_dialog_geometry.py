from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from underline_retldc.gui.theme import Theme_Apply


def test_warning_is_centered_on_owner_and_cancel_stays_cancel() -> None:
    app = QApplication.instance() or QApplication([])
    Theme_Apply(app, 'light')
    owner = QWidget()
    owner.setGeometry(60, 40, 600, 420)
    owner.show()
    observed: list[bool] = []

    def inspect() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        observed.append(
            (dialog.frameGeometry().center() - owner.frameGeometry().center()).manhattanLength()
            <= 2
        )
        assert owner.screen().availableGeometry().contains(dialog.frameGeometry())
        dialog.button(QMessageBox.StandardButton.Cancel).click()

    QTimer.singleShot(25, inspect)
    result = QMessageBox.warning(
        owner, 'Unsaved project', 'Save changes before closing?',
        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    assert observed == [True]
    assert result == QMessageBox.StandardButton.Cancel
    owner.close()
