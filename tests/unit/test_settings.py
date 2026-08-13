from pathlib import Path

from underline_retldc.app.settings import THEME_DARK, THEME_LIGHT, SettingsService


def test_theme_defaults_to_light_and_persists_dark(tmp_path: Path) -> None:
    source = tmp_path / "settings.ini"
    settings = SettingsService(source)
    assert settings.theme() == THEME_LIGHT

    settings.set_theme(THEME_DARK)
    assert settings.theme() == THEME_DARK
    assert SettingsService(source).theme() == THEME_DARK


def test_invalid_theme_falls_back_to_light(tmp_path: Path) -> None:
    source = tmp_path / "settings.ini"
    settings = SettingsService(source)
    settings.set_theme("unexpected-theme")
    assert settings.theme() == THEME_LIGHT
    assert SettingsService(source).theme() == THEME_LIGHT
