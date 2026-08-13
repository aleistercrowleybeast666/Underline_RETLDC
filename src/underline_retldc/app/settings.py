from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_IDS = (THEME_LIGHT, THEME_DARK)


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
        return str(self._settings.value("ui/locale", "zh_CN"))

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
