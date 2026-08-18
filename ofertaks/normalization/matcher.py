"""Product equivalence scoring."""

from __future__ import annotations

from difflib import SequenceMatcher

from ofertaks.normalization.product_normalizer import (
    NormalizedProduct,
    normalize_product_name,
)


def _as_product(value: str | NormalizedProduct) -> NormalizedProduct:
    if isinstance(value, NormalizedProduct):
        return value
    return normalize_product_name(value)


def _quantity_score(a: NormalizedProduct, b: NormalizedProduct) -> float:
    if a.quantity is None or b.quantity is None:
        return 0.45
    if a.unit != b.unit:
        return 0.0
    larger = max(a.quantity, b.quantity)
    diff = abs(a.quantity - b.quantity)
    if larger == 0:
        return 0.0
    ratio = diff / larger
    if ratio <= 0.03:
        return 1.0
    if ratio <= 0.10:
        return 0.55
    return 0.0


def match_score(left: str | NormalizedProduct, right: str | NormalizedProduct) -> float:
    a = _as_product(left)
    b = _as_product(right)

    token_a = " ".join(a.tokens)
    token_b = " ".join(b.tokens)
    text_similarity = SequenceMatcher(None, token_a, token_b).ratio()
    token_overlap = 0.0
    if a.tokens and b.tokens:
        token_overlap = len(set(a.tokens) & set(b.tokens)) / max(
            len(set(a.tokens)), len(set(b.tokens))
        )
    name_score = max(text_similarity, token_overlap)

    if a.brand and b.brand:
        brand_score = 1.0 if a.brand == b.brand else 0.0
    elif a.brand or b.brand:
        brand_score = 0.45
    else:
        brand_score = 0.65

    quantity_score = _quantity_score(a, b)
    score = (0.48 * name_score) + (0.24 * brand_score) + (0.28 * quantity_score)

    if quantity_score == 0.0:
        score = min(score, 0.58)
    if brand_score == 0.0:
        score = min(score, 0.72)
    return round(max(0.0, min(1.0, score)), 3)


def is_strong_match(left: str | NormalizedProduct, right: str | NormalizedProduct) -> bool:
    return match_score(left, right) >= 0.82
