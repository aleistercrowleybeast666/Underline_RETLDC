from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal


class TranslationService(QObject):
    locale_changed = Signal(str)

    def __init__(self, locale: str = "zh_CN") -> None:
        super().__init__()
        self._bundles: dict[str, dict[str, str]] = {}
        self._resource_directory = Path(__file__).resolve().parent
        self._load_builtin("en_US")
        self._load_builtin("zh_CN")
        self._locale = locale

    @property
    def locale(self) -> str:
        return self._locale

    @property
    def available_locales(self) -> tuple[str, ...]:
        return ("zh_CN", "en_US")

    def set_locale(self, locale: str) -> None:
        if locale == self._locale:
            return
        self._locale = locale
        self.locale_changed.emit(locale)

    def translate(self, key: str, default: str | None = None, **values: Any) -> str:
        text = self._bundles.get(self._locale, {}).get(key)
        if text is None:
            text = self._bundles.get("en_US", {}).get(key)
        if text is None:
            text = default if default is not None else key
        try:
            return text.format(**values)
        except (KeyError, ValueError):
            return text

    def register_bundle(self, locale: str, bundle: Mapping[str, str]) -> None:
        self._bundles.setdefault(locale, {}).update(
            {str(key): str(value) for key, value in bundle.items()}
        )

    def load_plugin_directory(self, translation_directory: Path) -> None:
        translation_directory = Path(translation_directory)
        for source in translation_directory.glob("*.json"):
            try:
                payload = json.loads(source.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, Mapping):
                self.register_bundle(source.stem, payload)

    def _load_builtin(self, locale: str) -> None:
        source = self._resource_directory / f"{locale}.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"Translation resource {source} must contain an object")
        self.register_bundle(locale, payload)

