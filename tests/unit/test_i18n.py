import json
from pathlib import Path

from underline_retldc.i18n.service import TranslationService


def test_builtin_locales_switch_and_fallback() -> None:
    service = TranslationService("zh_CN")
    assert service.translate("page.import") == "导入"
    observed: list[str] = []
    service.locale_changed.connect(observed.append)
    service.set_locale("en_US")
    assert service.translate("page.import") == "Import"
    assert observed == ["en_US"]
    service.set_locale("fr_FR")
    assert service.translate("page.import") == "Import"
    assert service.translate("missing.key") == "missing.key"
    assert service.translate("missing.key", "Fallback") == "Fallback"


def test_plugin_bundle_can_extend_locale() -> None:
    service = TranslationService("zh_CN")
    service.register_bundle("zh_CN", {"example.parser.name": "示例解析器"})
    assert service.translate("example.parser.name") == "示例解析器"


def test_builtin_locale_keys_have_exact_parity() -> None:
    resource_directory = (
        Path(__file__).resolve().parents[2] / "src" / "underline_retldc" / "i18n"
    )
    english = json.loads((resource_directory / "en_US.json").read_text(encoding="utf-8"))
    chinese = json.loads((resource_directory / "zh_CN.json").read_text(encoding="utf-8"))
    assert set(english) == set(chinese)


def test_bundled_plugin_locale_bundles_have_parity_and_load() -> None:
    plugin_root = Path(__file__).resolve().parents[2] / "plugins"
    plugin_directories = sorted(
        path.parent for path in plugin_root.rglob("plugin.json")
    )
    assert plugin_directories
    service = TranslationService("zh_CN")
    for directory in plugin_directories:
        chinese_path = directory / "i18n" / "zh_CN.json"
        english_path = directory / "i18n" / "en_US.json"
        assert chinese_path.is_file()
        assert english_path.is_file()
        chinese = json.loads(chinese_path.read_text(encoding="utf-8"))
        english = json.loads(english_path.read_text(encoding="utf-8"))
        assert set(chinese) == set(english)
        service.load_plugin_directory(directory / "i18n")
    assert service.translate("parser.tr_f.name") == "TR_F — 时间 / 原始推力"
    service.set_locale("en_US")
    assert service.translate("calibration.linear.name") == "Linear Calibration"
