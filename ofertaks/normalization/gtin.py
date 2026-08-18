"""GTIN normalization and validation for safe packaged-product identity."""

from __future__ import annotations

from ofertaks.utils.categories import FRUIT_VEGETABLE

GTIN_8 = "GTIN_8"
GTIN_12 = "GTIN_12"
GTIN_13 = "GTIN_13"
GTIN_14 = "GTIN_14"
GTIN_UNKNOWN = "UNKNOWN"

VERIFIED_GTIN = "VERIFIED_GTIN"
PROVISIONAL_NO_GTIN = "PROVISIONAL_NO_GTIN"
GTIN_CONFLICT = "GTIN_CONFLICT"
GTIN_NOT_APPLICABLE = "GTIN_NOT_APPLICABLE"

PACKAGED = "PACKAGED"
FRESH_BULK_ARTISANAL = "FRESH_BULK_ARTISANAL"

_GTIN_TYPES = {8: GTIN_8, 12: GTIN_12, 13: GTIN_13, 14: GTIN_14}
# Product category alone is not enough to declare most meat or bakery goods
# unscannable: they are often packaged. Fruit and vegetables are the only
# current safe automatic fresh/bulk default; other cases stay provisional
# unless a caller explicitly selects the fresh/bulk strategy.
_FRESH_BULK_CATEGORIES = frozenset({FRUIT_VEGETABLE})


def normalize_gtin(value: str | None) -> str | None:
    """Return a digits-only GTIN while preserving leading zeroes."""

    if value is None:
        return None
    normalized = value.strip().replace(" ", "").replace("-", "")
    return normalized or None


def gtin_type(value: str | None) -> str:
    normalized = normalize_gtin(value)
    return _GTIN_TYPES.get(len(normalized or ""), GTIN_UNKNOWN)


def is_valid_gtin(value: str | None) -> bool:
    normalized = normalize_gtin(value)
    if not normalized or not normalized.isascii() or not normalized.isdigit() or len(normalized) not in _GTIN_TYPES:
        return False
    total = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(normalized[:-1]))
    )
    expected = (10 - total % 10) % 10
    return int(normalized[-1]) == expected


def validate_gtin(value: str | None) -> str:
    normalized = normalize_gtin(value)
    if not is_valid_gtin(normalized):
        raise ValueError("A GTIN must contain 8, 12, 13, or 14 digits with a valid check digit")
    return normalized  # type: ignore[return-value]


def identity_strategy_for(category: str | None, barcode_gtin: str | None = None) -> str:
    """Keep fresh/bulk identity separate when no scannable code is available."""

    if barcode_gtin:
        return PACKAGED
    return FRESH_BULK_ARTISANAL if category in _FRESH_BULK_CATEGORIES else PACKAGED
