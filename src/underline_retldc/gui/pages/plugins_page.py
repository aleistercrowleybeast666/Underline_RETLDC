from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.registry import PluginRecord
from underline_retldc.i18n.service import TranslationService


class PluginsPage(QWidget):
    refresh_requested = Signal()
    install_requested = Signal()
    open_development_requested = Signal()
    open_user_requested = Signal()

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setObjectName("warningLabel")
        self.table = QTableWidget(0, 8)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.refresh_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.install_button = QPushButton()
        self.install_button.clicked.connect(self.install_requested)
        self.development_button = QPushButton()
        self.development_button.clicked.connect(self.open_development_requested)
        self.user_button = QPushButton()
        self.user_button.clicked.connect(self.open_user_requested)
        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.install_button)
        button_row.addWidget(self.development_button)
        button_row.addWidget(self.user_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.warning_label)
        layout.addLayout(button_row)
        layout.addWidget(self.table, 1)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.warning_label.setText(t("plugins.warning"))
        self.refresh_button.setText(t("common.refresh"))
        self.install_button.setText(t("plugins.install"))
        self.development_button.setText(t("plugins.open_development"))
        self.user_button.setText(t("plugins.open_user"))
        self.table.setHorizontalHeaderLabels(
            [
                t("plugins.column.name"),
                t("plugins.column.type"),
                t("plugins.column.id"),
                t("plugins.column.version"),
                t("plugins.column.api"),
                t("plugins.column.status"),
                t("plugins.column.source"),
                t("plugins.column.diagnostics"),
            ]
        )

    def set_records(self, records: tuple[PluginRecord, ...]) -> None:
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            descriptor = record.descriptor
            values = [
                self._translations.translate(
                    descriptor.translation_key or "", descriptor.name
                )
                if descriptor
                else "—",
                self._translations.translate(
                    f"plugin.type.{descriptor.plugin_type.value}",
                    descriptor.plugin_type.value,
                )
                if descriptor
                else "—",
                record.plugin_id,
                descriptor.version if descriptor else "—",
                descriptor.api_version if descriptor else "—",
                self._translations.translate(
                    f"plugin.status.{record.result.value}", record.result.value
                ),
                self._translations.translate(
                    f"plugin.source.{record.source_kind}", record.source_kind
                ),
                " | ".join(item.message for item in record.diagnostics),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
