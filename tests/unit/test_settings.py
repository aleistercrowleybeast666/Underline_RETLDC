from pathlib import Path

from underline_retldc.app.settings import (
    THEME_DARK,
    THEME_LIGHT,
    UNIT_DISPLAY_ENGINEERING,
    UNIT_DISPLAY_SI_SCIENTIFIC,
    SettingsService,
)


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


def test_tabular_auto_mapping_preferences_default_on_and_persist(
    tmp_path: Path,
) -> None:
    source = tmp_path / "settings.ini"
    settings = SettingsService(source)
    assert settings.tabular_auto_mapping()
    assert settings.tabular_auto_prefill()
    settings.set_tabular_auto_mapping(False)
    settings.set_tabular_auto_prefill(False)
    reopened = SettingsService(source)
    assert not reopened.tabular_auto_mapping()
    assert not reopened.tabular_auto_prefill()


def test_scientific_factory_defaults_are_centralized(tmp_path: Path) -> None:
    settings = SettingsService(tmp_path / "settings.ini")
    assert settings.locale() == "zh_CN"
    assert settings.new_channel_calibration_id() == "builtin.calibration.identity"
    assert settings.missing_unit_policy() == "canonical_si_by_quantity"
    assert settings.display_units() == {
        "force": "N",
        "pressure": "MPa",
        "temperature": "°C",
        "length": "mm",
        "area": "mm²",
        "mass": "kg",
    }
    assert settings.unit_display_mode() == UNIT_DISPLAY_ENGINEERING


def test_unit_display_mode_persists_and_invalid_values_fall_back(
    tmp_path: Path,
) -> None:
    source = tmp_path / "settings.ini"
    settings = SettingsService(source)
    settings.set_unit_display_mode(UNIT_DISPLAY_SI_SCIENTIFIC)
    assert SettingsService(source).unit_display_mode() == (
        UNIT_DISPLAY_SI_SCIENTIFIC
    )
    settings.set_unit_display_mode("unexpected")
    assert settings.unit_display_mode() == UNIT_DISPLAY_ENGINEERING
