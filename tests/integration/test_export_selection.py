from collections.abc import Iterator

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from underline_retldc.gui.pages.export_page import ExportDialog, ExportOption
from underline_retldc.i18n.service import TranslationService


@pytest.fixture
def dialog() -> Iterator[ExportDialog]:
    app = QApplication.instance() or QApplication([])
    result = ExportDialog(TranslationService("zh_CN"))
    result._export_options_set((
        ExportOption("example.available", "available.csv", "", (), default_selected=False),
        ExportOption("example.capability", "capability.csv", "", (),
                     required_capability_ids=("measurement_ready",)),
        ExportOption("example.analysis", "analysis.txt", "", ("analysis_ready",)),
    ))
    yield result
    result.close()
    result.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def _available(dialog: ExportDialog) -> set[str]:
    return {key for key, checkbox in dialog.exporter_checks.items() if checkbox.isEnabled()}


def test_open_selects_all_available_and_reopen_resets_only_when_opened(
    dialog: ExportDialog,
) -> None:
    assert dialog.selected_exporter_ids() == ()
    dialog.show()
    QApplication.processEvents()
    assert set(dialog.selected_exporter_ids()) == _available(dialog) == {"example.available"}
    checkbox = dialog.exporter_checks["example.available"]
    checkbox.setChecked(False)
    dialog.set_completed_capability_ids(())
    dialog.retranslate()
    dialog.show()  # Raising an already-visible window must keep its manual selection.
    assert not checkbox.isChecked()
    assert not dialog.export_button.isEnabled()
    dialog.hide()
    dialog.show()
    QApplication.processEvents()
    assert checkbox.isChecked()
    assert dialog.export_button.isEnabled()
    assert dialog.select_all_button.text() == "全选"
    dialog._translations.set_locale("en_US")
    dialog.retranslate()
    assert dialog.select_all_button.text() == "Select All"


def test_select_all_button_restores_available_choices_and_skips_locked_items(
    dialog: ExportDialog,
) -> None:
    dialog.show()
    dialog.set_completed_capability_ids(("measurement_ready",))
    dialog.set_completed_analysis_ids(("analysis_ready",))
    for checkbox in dialog.exporter_checks.values():
        checkbox.setChecked(False)
    dialog.select_all_button.click()
    assert set(dialog.selected_exporter_ids()) == _available(dialog)
    assert len(dialog.selected_exporter_ids()) == 3
    dialog.set_completed_capability_ids(())
    dialog.set_completed_analysis_ids(())
    dialog.select_all_button.click()
    assert dialog.selected_exporter_ids() == ("example.available",)
    for key in ("example.capability", "example.analysis"):
        assert not dialog.exporter_checks[key].isEnabled()
        assert not dialog.exporter_checks[key].isChecked()


def test_manual_uncheck_is_preserved_after_select_all_and_availability_refresh(
    dialog: ExportDialog,
) -> None:
    dialog.select_all_available()
    dialog.exporter_checks["example.available"].setChecked(False)
    dialog.set_completed_capability_ids(("measurement_ready",))
    assert not dialog.exporter_checks["example.available"].isChecked()
    dialog.set_completed_capability_ids(("measurement_ready",))
    assert not dialog.exporter_checks["example.available"].isChecked()
    dialog.select_all_button.click()
    assert set(dialog.selected_exporter_ids()) == {"example.available", "example.capability"}


def test_empty_or_all_unavailable_disables_selection_and_export(dialog: ExportDialog) -> None:
    dialog._export_options_set(tuple(
        option for option in dialog._options if option.plugin_id != "example.available"
    ))
    dialog.show()
    QApplication.processEvents()
    dialog.select_all_available()
    assert dialog.selected_exporter_ids() == ()
    assert not dialog.select_all_button.isEnabled()
    assert not dialog.export_button.isEnabled()
    dialog._export_options_set(())
    dialog.select_all_available()
    assert dialog.selected_exporter_ids() == ()
    assert not dialog.select_all_button.isEnabled()
    assert not dialog.export_button.isEnabled()
