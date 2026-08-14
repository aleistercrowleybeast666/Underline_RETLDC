from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.app.settings import (
    THEME_DARK,
    THEME_LIGHT,
    UNIT_DISPLAY_ENGINEERING,
    UNIT_DISPLAY_SI_SCIENTIFIC,
    Theme_Normalize,
)
from underline_retldc.app.version import FULL_NAME, __version__
from underline_retldc.core.defaults import FACTORY_DISPLAY_UNITS
from underline_retldc.core.units import Unit_ChoicesForQuantity
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class SettingsPage(QWidget):
    locale_selected = Signal(str)
    theme_selected = Signal(str)
    display_unit_selected = Signal(str, str)
    unit_display_mode_selected = Signal(str)
    tabular_auto_mapping_selected = Signal(bool)
    tabular_auto_prefill_selected = Signal(bool)

    def __init__(
        self,
        translations: TranslationService,
        theme: str = THEME_LIGHT,
        display_units: dict[str, str] | None = None,
        unit_display_mode: str = UNIT_DISPLAY_ENGINEERING,
        tabular_auto_mapping: bool = True,
        tabular_auto_prefill: bool = True,
    ) -> None:
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

        self.units_group = QGroupBox()
        units_layout = QFormLayout(self.units_group)
        self.missing_unit_label = QLabel()
        self.missing_unit_value = QLabel()
        units_layout.addRow(self.missing_unit_label, self.missing_unit_value)
        self.unit_display_mode_label = QLabel()
        self.unit_display_mode_combo = StandardComboBox()
        self.unit_display_mode_combo.addItem("", UNIT_DISPLAY_ENGINEERING)
        self.unit_display_mode_combo.addItem("", UNIT_DISPLAY_SI_SCIENTIFIC)
        self.unit_display_mode_combo.currentIndexChanged.connect(
            lambda _index: self.unit_display_mode_selected.emit(
                str(self.unit_display_mode_combo.currentData())
            )
        )
        units_layout.addRow(self.unit_display_mode_label, self.unit_display_mode_combo)
        self.display_unit_labels: dict[str, QLabel] = {}
        self.display_unit_combos: dict[str, StandardComboBox] = {}
        selected_units = {**FACTORY_DISPLAY_UNITS, **dict(display_units or {})}
        for quantity in ("force", "pressure", "temperature", "length", "area", "mass"):
            label = QLabel()
            combo = StandardComboBox()
            for unit in Unit_ChoicesForQuantity(quantity, include_non_engineering=False):
                combo.addItem(unit, unit)
            index = combo.findData(selected_units[quantity])
            combo.setCurrentIndex(max(0, index))
            combo.currentIndexChanged.connect(
                lambda _index, key=quantity, widget=combo: self.display_unit_selected.emit(
                    key, str(widget.currentData())
                )
            )
            self.display_unit_labels[quantity] = label
            self.display_unit_combos[quantity] = combo
            units_layout.addRow(label, combo)

        self.tabular_group = QGroupBox()
        tabular_layout = QVBoxLayout(self.tabular_group)
        self.tabular_auto_mapping_check = QCheckBox()
        self.tabular_auto_mapping_check.setChecked(bool(tabular_auto_mapping))
        self.tabular_auto_mapping_check.toggled.connect(
            self.tabular_auto_mapping_selected
        )
        self.tabular_auto_prefill_check = QCheckBox()
        self.tabular_auto_prefill_check.setChecked(bool(tabular_auto_prefill))
        self.tabular_auto_prefill_check.toggled.connect(
            self.tabular_auto_prefill_selected
        )
        tabular_layout.addWidget(self.tabular_auto_mapping_check)
        tabular_layout.addWidget(self.tabular_auto_prefill_check)

        self.about_group = QGroupBox()
        about_layout = QVBoxLayout(self.about_group)
        self.about_label = QLabel(f"{FULL_NAME}\n{__version__}\nPlugin API 1")
        about_layout.addWidget(self.about_label)
        layout = QVBoxLayout(self)
        layout.addWidget(self.language_group)
        layout.addWidget(self.units_group)
        layout.addWidget(self.tabular_group)
        layout.addWidget(self.about_group)
        layout.addStretch(1)
        self.set_locale(translations.locale)
        self.set_theme(theme)
        self.set_unit_display_mode(unit_display_mode)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.language_group.setTitle(t("settings.language"))
        self.language_label.setText(t("settings.language"))
        self.theme_label.setText(t("settings.theme"))
        self.theme_combo.setItemText(0, t("theme.light"))
        self.theme_combo.setItemText(1, t("theme.dark"))
        self.saved_label.setText(t("settings.locale_saved"))
        self.units_group.setTitle(t("settings.units"))
        self.missing_unit_label.setText(t("settings.missing_unit"))
        self.missing_unit_value.setText(t("settings.missing_unit_si"))
        self.unit_display_mode_label.setText(t("settings.unit_display_mode"))
        self.unit_display_mode_combo.setItemText(
            0, t("settings.unit_display_engineering")
        )
        self.unit_display_mode_combo.setItemText(
            1, t("settings.unit_display_si_scientific")
        )
        for quantity, label in self.display_unit_labels.items():
            label.setText(t(f"quantity.{quantity}"))
        self.tabular_group.setTitle(t("settings.tabular"))
        self.tabular_auto_mapping_check.setText(t("settings.tabular_auto_mapping"))
        self.tabular_auto_prefill_check.setText(t("settings.tabular_auto_prefill"))
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

    def set_display_units(self, display_units: dict[str, str]) -> None:
        for quantity, unit in display_units.items():
            combo = self.display_unit_combos.get(quantity)
            if combo is None:
                continue
            index = combo.findData(unit)
            if index >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)

    def set_unit_display_mode(self, mode: str) -> None:
        index = self.unit_display_mode_combo.findData(mode)
        self.unit_display_mode_combo.blockSignals(True)
        self.unit_display_mode_combo.setCurrentIndex(max(0, index))
        self.unit_display_mode_combo.blockSignals(False)
        engineering = (
            self.unit_display_mode_combo.currentData()
            == UNIT_DISPLAY_ENGINEERING
        )
        for combo in self.display_unit_combos.values():
            combo.setEnabled(engineering)
