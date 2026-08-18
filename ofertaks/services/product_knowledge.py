"""Canonical product identity rules that keep exact and comparable products separate."""

from __future__ import annotations

from dataclasses import dataclass

from ofertaks.models.knowledge import (
    CATEGORY_EQUIVALENT,
    EXACT_PRODUCT,
    SAME_PRODUCT_FAMILY,
    SAME_VARIANT_DIFFERENT_SIZE,
    UNRELATED,
    CanonicalProduct,
)
from ofertaks.normalization.product_normalizer import NormalizedProduct, normalize_product_name
from ofertaks.utils.text import comparable_text


@dataclass(frozen=True, slots=True)
class ProductRelation:
    relationship: str
    confidence: float

    @property
    def is_exact(self) -> bool:
        return self.relationship == EXACT_PRODUCT


@dataclass(frozen=True, slots=True)
class _Identity:
    brand: str | None
    family: str
    variant: str | None
    category: str | None
    quantity: float | None
    unit: str | None
    barcode_gtin: str | None


def _without_brand(value: str, brand: str | None) -> str:
    if not brand:
        return value
    brand_words = comparable_text(brand).split()
    return " ".join(token for token in value.split() if token not in brand_words).strip()


def _identity(value: str | NormalizedProduct | CanonicalProduct) -> _Identity:
    if isinstance(value, CanonicalProduct):
        name = _without_brand(comparable_text(value.canonical_name), value.brand)
        family = comparable_text(value.product_family) if value.product_family else name
        return _Identity(
            brand=value.brand,
            family=family,
            variant=comparable_text(value.variant) if value.variant else None,
            category=value.category,
            quantity=value.quantity,
            unit=value.unit,
            barcode_gtin=value.barcode_gtin,
        )
    normalized = value if isinstance(value, NormalizedProduct) else normalize_product_name(value)
    family = " ".join(normalized.tokens) or _without_brand(normalized.normalized_name, normalized.brand)
    return _Identity(
        brand=normalized.brand,
        family=family,
        variant=None,
        category=normalized.category,
        quantity=normalized.quantity,
        unit=normalized.unit,
        barcode_gtin=None,
    )


def classify_product_relationship(
    left: str | NormalizedProduct | CanonicalProduct,
    right: str | NormalizedProduct | CanonicalProduct,
) -> ProductRelation:
    """Classify a comparison conservatively; comparable never silently means exact."""

    a, b = _identity(left), _identity(right)
    if a.barcode_gtin and b.barcode_gtin and a.barcode_gtin == b.barcode_gtin:
        return ProductRelation(EXACT_PRODUCT, 1.0)

    same_brand = a.brand == b.brand if a.brand and b.brand else not a.brand and not b.brand
    same_family = bool(a.family and a.family == b.family)
    same_variant = a.variant == b.variant if a.variant and b.variant else not a.variant and not b.variant
    same_unit = a.unit == b.unit if a.unit and b.unit else a.unit is None and b.unit is None
    same_quantity = (
        a.quantity is not None and b.quantity is not None and same_unit and abs(a.quantity - b.quantity) <= 0.001
    )
    comparable_category = bool(a.category and a.category == b.category)

    # Two distinct verified codes identify two distinct purchasable products.
    # They can still be comparable, but never silently become an exact match.
    distinct_gtins = bool(a.barcode_gtin and b.barcode_gtin and a.barcode_gtin != b.barcode_gtin)
    if distinct_gtins:
        if same_brand and same_family:
            return ProductRelation(SAME_PRODUCT_FAMILY, 0.82)
        if comparable_category and a.family and b.family:
            return ProductRelation(CATEGORY_EQUIVALENT, 0.56)
        return ProductRelation(UNRELATED, 0.0)

    if same_brand and same_family and same_variant and same_quantity:
        return ProductRelation(EXACT_PRODUCT, 0.98)
    if same_brand and same_family and same_variant and a.quantity is not None and b.quantity is not None and not same_quantity:
        return ProductRelation(SAME_VARIANT_DIFFERENT_SIZE, 0.94)
    if same_brand and (same_family or comparable_category):
        return ProductRelation(SAME_PRODUCT_FAMILY, 0.76 if same_family else 0.62)
    if comparable_category and a.family and b.family:
        return ProductRelation(CATEGORY_EQUIVALENT, 0.56)
    return ProductRelation(UNRELATED, 0.0)
