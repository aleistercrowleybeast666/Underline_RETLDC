from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from underline_retldc.core.defaults import FACTORY_DEFAULTS, FACTORY_DISPLAY_UNITS
from underline_retldc.core.units import UnitDisplayMode, UnitDisplayMode_Normalize

THEME_LIGHT = FACTORY_DEFAULTS.theme
THEME_DARK = "dark"
THEME_IDS = (THEME_LIGHT, THEME_DARK)
UNIT_DISPLAY_ENGINEERING = UnitDisplayMode.ENGINEERING.value
UNIT_DISPLAY_SI_SCIENTIFIC = UnitDisplayMode.SI_SCIENTIFIC.value
UNIT_DISPLAY_MODE_IDS = (
    UNIT_DISPLAY_ENGINEERING,
    UNIT_DISPLAY_SI_SCIENTIFIC,
)


def Theme_Normalize(theme: str | None) -> str:
    value = str(theme or "").strip().lower()
    return value if value in THEME_IDS else THEME_LIGHT


class SettingsService:
    def __init__(self, settings_file: Path | None = None) -> None:
        if settings_file is None:
            self._settings = QSettings("Underline", "RETLDC")
        else:
            self._settings = QSettings(str(settings_file), QSettings.Format.IniFormat)

    def locale(self) -> str:
        return str(self._settings.value("ui/locale", FACTORY_DEFAULTS.locale))

    def set_locale(self, locale: str) -> None:
        self._settings.setValue("ui/locale", locale)
        self._settings.sync()

    def theme(self) -> str:
        return Theme_Normalize(str(self._settings.value("ui/theme", THEME_LIGHT)))

    def set_theme(self, theme: str) -> None:
        self._settings.setValue("ui/theme", Theme_Normalize(theme))
        self._settings.sync()

    def last_directory(self) -> Path:
        value = str(self._settings.value("files/last_directory", str(Path.home())))
        return Path(value)

    def set_last_directory(self, directory: Path) -> None:
        self._settings.setValue("files/last_directory", str(Path(directory)))
        self._settings.sync()

    def display_units(self) -> dict[str, str]:
        return {
            quantity: str(
                self._settings.value(f"units/display/{quantity}", default_unit)
            )
            for quantity, default_unit in FACTORY_DISPLAY_UNITS.items()
        }

    def set_display_unit(self, quantity: str, unit: str) -> None:
        self._settings.setValue(f"units/display/{quantity}", unit)
        self._settings.sync()

    def unit_display_mode(self) -> str:
        value = self._settings.value(
            "units/display_mode",
            FACTORY_DEFAULTS.unit_display_mode,
        )
        return UnitDisplayMode_Normalize(str(value)).value

    def set_unit_display_mode(self, mode: str) -> None:
        self._settings.setValue(
            "units/display_mode",
            UnitDisplayMode_Normalize(mode).value,
        )
        self._settings.sync()

    def tabular_auto_mapping(self) -> bool:
        return self._settings.value(
            "tabular/auto_mapping",
            FACTORY_DEFAULTS.tabular_auto_mapping,
            type=bool,
        )

    def set_tabular_auto_mapping(self, enabled: bool) -> None:
        self._settings.setValue("tabular/auto_mapping", bool(enabled))
        self._settings.sync()

    def tabular_auto_prefill(self) -> bool:
        return self._settings.value(
            "tabular/auto_prefill",
            FACTORY_DEFAULTS.tabular_auto_prefill,
            type=bool,
        )

    def set_tabular_auto_prefill(self, enabled: bool) -> None:
        self._settings.setValue("tabular/auto_prefill", bool(enabled))
        self._settings.sync()

    @staticmethod
    def missing_unit_policy() -> str:
        return FACTORY_DEFAULTS.missing_unit_policy

    @staticmethod
    def new_channel_calibration_id() -> str:
        return FACTORY_DEFAULTS.new_channel_calibration_id
