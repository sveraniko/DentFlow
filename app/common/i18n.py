from __future__ import annotations

import json
from pathlib import Path

SUPPORTED_LOCALES = ("ru", "en")


class I18nService:
    def __init__(self, locales_path: Path, default_locale: str = "ru") -> None:
        self._default_locale = default_locale
        self._catalog: dict[str, dict[str, str]] = {}
        self._load(locales_path)

    def _load(self, locales_path: Path) -> None:
        for locale in SUPPORTED_LOCALES:
            locale_file = locales_path / f"{locale}.json"
            if not locale_file.exists():
                raise FileNotFoundError(f"Missing locale file: {locale_file}")
            self._catalog[locale] = json.loads(locale_file.read_text(encoding="utf-8"))

    def t(self, key: str, locale: str | None = None) -> str:
        requested = locale if locale in self._catalog else self._default_locale
        localized = self._catalog.get(requested, {}).get(key)
        if localized:
            return localized
        fallback = self._catalog.get(self._default_locale, {}).get(key)
        if fallback:
            return fallback
        return key
