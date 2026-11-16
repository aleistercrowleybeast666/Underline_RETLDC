"""Place message boxes in their owning window's screen, in Qt logical pixels."""
from PySide6.QtWidgets import QWidget


def Dialog_CenterOnOwner(dialog: QWidget) -> None:
    owner = dialog.parentWidget()
    if owner is None or owner.window().screen() is None:
        return
    owner = owner.window()
    available = owner.screen().availableGeometry()
    frame = dialog.frameGeometry()
    width = max(1, available.width() - max(0, frame.width() - dialog.width()))
    height = max(1, available.height() - max(0, frame.height() - dialog.height()))
    dialog.setMinimumSize(min(dialog.minimumWidth(), width), min(dialog.minimumHeight(), height))
    dialog.resize(min(dialog.width(), width), min(dialog.height(), height))
    frame = dialog.frameGeometry()
    frame.moveCenter(owner.frameGeometry().center())
    dialog.move(
        max(available.left(), min(frame.left(), available.right() - frame.width() + 1)),
        max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1)),
    )
