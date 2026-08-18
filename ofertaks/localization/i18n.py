"""Lightweight translation service."""

from __future__ import annotations

import locale
import logging
from dataclasses import dataclass
from typing import Any

from ofertaks.localization.strings_en import STRINGS as EN_STRINGS
from ofertaks.localization.strings_fr import STRINGS as FR_STRINGS
from ofertaks.localization.strings_sq import STRINGS as SQ_STRINGS

LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("sq", "en", "fr")
LANGUAGE_OPTIONS = {
    "sq": "Shqip",
    "en": "English",
    "fr": "Français",
}
TRANSLATIONS = {
    "en": EN_STRINGS,
    "fr": FR_STRINGS,
    "sq": SQ_STRINGS,
}
FALLBACK_LANGUAGE = "en"
LANGUAGE_PREFERENCE_KEY = "language"


def detect_system_language() -> str:
    language = (locale.getlocale()[0] or "").casefold()
    if language.startswith("sq"):
        return "sq"
    if language.startswith("fr"):
        return "fr"
    if language.startswith("en"):
        return "en"
    return FALLBACK_LANGUAGE


@dataclass
class Translator:
    language: str

    @classmethod
    def from_repository(cls, repository: Any) -> "Translator":
        saved = repository.get_preference(LANGUAGE_PREFERENCE_KEY)
        language = normalize_language(saved) if saved else detect_system_language()
        return cls(language=language)

    def set_language(self, language: str) -> None:
        self.language = normalize_language(language)

    def translate(self, key: str, language: str | None = None) -> str:
        active = normalize_language(language or self.language)
        value = TRANSLATIONS.get(active, {}).get(key)
        if value is not None:
            return value
        fallback = TRANSLATIONS[FALLBACK_LANGUAGE].get(key)
        if fallback is not None:
            LOGGER.debug("Missing translation key %s for language %s", key, active)
            return fallback
        LOGGER.debug("Missing translation key %s", key)
        return key


def normalize_language(language: str | None) -> str:
    if language in SUPPORTED_LANGUAGES:
        return language
    return FALLBACK_LANGUAGE


_translator = Translator(language=detect_system_language())


def get_translator() -> Translator:
    return _translator


def set_language(language: str) -> None:
    _translator.set_language(language)


def t(key: str, language: str | None = None) -> str:
    return _translator.translate(key, language)
