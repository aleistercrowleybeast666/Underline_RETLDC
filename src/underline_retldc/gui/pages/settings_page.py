from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from underline_retldc.app.settings import THEME_DARK, THEME_LIGHT, Theme_Normalize
from underline_retldc.app.version import FULL_NAME, __version__
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class SettingsPage(QWidget):
    locale_selected = Signal(str)
    theme_selected = Signal(str)

    def __init__(self, translations: TranslationService, theme: str = THEME_LIGHT) -> None:
        super().__init__()
        self._translations = translations
        self.language_group = QGroupBox()
        language_layout = QFormLayout(self.language_group)
        self.language_label = QLabel()
        self.language_combo = StandardComboBox()
        self.language_combo.addItem("简体中文", "zh_CN")
        self.language_combo.addItem("English", "en_US")
        self.language_combo.currentIndexChanged.connect(
            lambda _index: self.locale_selected.emit(str(self.language_combo.currentData()))
        )
        self.theme_label = QLabel()
        self.theme_combo = StandardComboBox()
        self.theme_combo.addItem("", THEME_LIGHT)
        self.theme_combo.addItem("", THEME_DARK)
        self.theme_combo.currentIndexChanged.connect(
            lambda _index: self.theme_selected.emit(str(self.theme_combo.currentData()))
        )
        self.saved_label = QLabel()
        language_layout.addRow(self.language_label, self.language_combo)
        language_layout.addRow(self.theme_label, self.theme_combo)
        language_layout.addRow(self.saved_label)

        self.about_group = QGroupBox()
        about_layout = QVBoxLayout(self.about_group)
        self.about_label = QLabel(f"{FULL_NAME}\n{__version__}\nPlugin API 1")
        about_layout.addWidget(self.about_label)
        layout = QVBoxLayout(self)
        layout.addWidget(self.language_group)
        layout.addWidget(self.about_group)
        layout.addStretch(1)
        self.set_locale(translations.locale)
        self.set_theme(theme)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.language_group.setTitle(t("settings.language"))
        self.language_label.setText(t("settings.language"))
        self.theme_label.setText(t("settings.theme"))
        self.theme_combo.setItemText(0, t("theme.light"))
        self.theme_combo.setItemText(1, t("theme.dark"))
        self.saved_label.setText(t("settings.locale_saved"))
        self.about_group.setTitle(t("settings.about"))

    def set_locale(self, locale: str) -> None:
        index = self.language_combo.findData(locale)
        if index < 0:
            index = self.language_combo.findData("en_US")
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(index)
        self.language_combo.blockSignals(False)

    def set_theme(self, theme: str) -> None:
        index = self.theme_combo.findData(Theme_Normalize(theme))
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(max(0, index))
        self.theme_combo.blockSignals(False)
