"""Central localization package."""

from ofertaks.localization.i18n import (
    LANGUAGE_OPTIONS,
    SUPPORTED_LANGUAGES,
    Translator,
    detect_system_language,
    get_translator,
    set_language,
    t,
)

__all__ = [
    "LANGUAGE_OPTIONS",
    "SUPPORTED_LANGUAGES",
    "Translator",
    "detect_system_language",
    "get_translator",
    "set_language",
    "t",
]
