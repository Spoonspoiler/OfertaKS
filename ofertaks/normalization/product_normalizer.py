"""Deterministic lightweight product normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ofertaks.normalization.brand_normalizer import detect_brand
from ofertaks.parsing.unit_parser import parse_quantity
from ofertaks.utils.categories import detect_category
from ofertaks.utils.text import comparable_text, normalize_whitespace

PACKAGING_WORDS = {
    "original",
    "classic",
    "pet",
    "shishe",
    "bottle",
    "kanaqe",
    "pakete",
    "paket",
    "pack",
    "ambalazh",
    "cope",
    "cop",
    "te",
    "me",
    "per",
}
UNIT_WORDS = {
    "ml",
    "l",
    "litra",
    "liter",
    "litre",
    "kg",
    "g",
    "gr",
    "gram",
    "pcs",
    "piece",
    "cope",
    "cop",
}


@dataclass(slots=True)
class NormalizedProduct:
    raw_name: str
    normalized_name: str
    brand: str | None
    quantity: float | None
    unit: str | None
    tokens: tuple[str, ...]
    category: str


def _remove_quantity_fragments(text: str) -> str:
    text = re.sub(
        r"\b\d+\s*x\s*\d+(?:[,.]\d+)?\s*(?:ml|litra|liter|litre|l|kg|g|gr|pcs|cope|cop)\b",
        " ",
        text,
    )
    text = re.sub(
        r"\b\d+(?:[,.]\d+)?\s*(?:ml|litra|liter|litre|l|kg|g|gr|pcs|cope|cop)\b",
        " ",
        text,
    )
    return text


def normalize_product_name(raw_name: str, raw_category: str | None = None) -> NormalizedProduct:
    comparable = comparable_text(raw_name)
    quantity = parse_quantity(raw_name)
    without_quantity = _remove_quantity_fragments(comparable)
    brand = detect_brand(raw_name)
    brand_words = set(comparable_text(brand).split()) if brand else set()
    tokens = []
    for token in without_quantity.split():
        if token.isdigit():
            continue
        if token in UNIT_WORDS or token in PACKAGING_WORDS:
            continue
        if token in brand_words:
            continue
        tokens.append(token)

    normalized_core = normalize_whitespace(" ".join(tokens))
    if brand:
        normalized_name = normalize_whitespace(f"{brand.casefold()} {normalized_core}")
    else:
        normalized_name = normalized_core or comparable

    category_input = " ".join(part for part in [raw_name, raw_category or ""] if part)
    return NormalizedProduct(
        raw_name=raw_name,
        normalized_name=normalized_name,
        brand=brand,
        quantity=quantity.quantity if quantity else None,
        unit=quantity.unit if quantity else None,
        tokens=tuple(tokens),
        category=detect_category(category_input),
    )
