"""Text helpers used by parsing, normalization, and UI."""

from __future__ import annotations

import re
import unicodedata


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def clean_text(value: str) -> str:
    return normalize_whitespace(value.replace("\xa0", " "))


def comparable_text(value: str) -> str:
    value = strip_accents(value.casefold())
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return normalize_whitespace(value)
