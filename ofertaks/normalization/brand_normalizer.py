"""Brand alias normalization."""

from __future__ import annotations

from ofertaks.utils.text import comparable_text

BRAND_ALIASES: dict[str, str] = {
    "coca cola": "Coca-Cola",
    "cocacola": "Coca-Cola",
    "coca-cola": "Coca-Cola",
    "lavazza": "Lavazza",
    "devolli": "Devolli",
    "peja": "Peja",
    "rugove": "Rugove",
    "rugova": "Rugove",
    "vita": "Vita",
    "alpsko": "Alpsko",
    "prince": "Prince",
    "nescafe": "Nescafe",
    "barilla": "Barilla",
    "rio mare": "Rio Mare",
}


def detect_brand(text: str) -> str | None:
    comparable = comparable_text(text)
    compact = comparable.replace(" ", "")
    for alias, brand in BRAND_ALIASES.items():
        alias_norm = comparable_text(alias)
        if alias_norm in comparable or alias_norm.replace(" ", "") in compact:
            return brand
    return None
