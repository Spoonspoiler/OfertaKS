"""Price evidence, promotion claims, and consumer-facing analysis models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


REGULAR = "REGULAR"
PROMOTION = "PROMOTION"
CLEARANCE = "CLEARANCE"
USER_OBSERVED = "USER_OBSERVED"
MERCHANT_PROVIDED = "MERCHANT_PROVIDED"
FLYER = "FLYER"
RECEIPT = "RECEIPT"
SHELF_LABEL = "SHELF_LABEL"
UNKNOWN = "UNKNOWN"

PRICE_CONTEXTS = frozenset(
    {
        REGULAR,
        PROMOTION,
        CLEARANCE,
        USER_OBSERVED,
        MERCHANT_PROVIDED,
        FLYER,
        RECEIPT,
        SHELF_LABEL,
        UNKNOWN,
    }
)

EXCEPTIONAL_DEAL = "EXCEPTIONAL_DEAL"
GOOD_DEAL = "GOOD_DEAL"
NORMAL_PRICE = "NORMAL_PRICE"
EXPENSIVE = "EXPENSIVE"
VERY_EXPENSIVE = "VERY_EXPENSIVE"
WEAK_PROMOTION = "WEAK_PROMOTION"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
CONFLICTED_DATA = "CONFLICTED_DATA"
BEST_NEARBY_PRICE = "BEST_NEARBY_PRICE"

RECENT_PRICE_INCREASE = "RECENT_PRICE_INCREASE"
PRICE_INCREASE_BEFORE_PROMOTION = "PRICE_INCREASE_BEFORE_PROMOTION"
ADVERTISED_DISCOUNT_MISMATCH = "ADVERTISED_DISCOUNT_MISMATCH"
PACKAGE_PRICE_UNCHANGED_UNIT_INCREASE = "PACKAGE_PRICE_UNCHANGED_UNIT_INCREASE"


@dataclass(frozen=True, slots=True)
class PromotionEvent:
    canonical_product_id: int
    promo_price: float
    observed_at: datetime
    id: int | None = None
    merchant_id: str | None = None
    chain_id: str | None = None
    advertised_reference_price: float | None = None
    advertised_discount_percent: float | None = None
    advertised_discount_amount: float | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    published_at: datetime | None = None
    source_type: str = FLYER
    source_id: str | None = None
    source_document_id: int | None = None
    source_url: str | None = None
    raw_offer_text: str | None = None
    geographic_scope: str = UNKNOWN
    confidence: float = 0.5
    dedupe_key: str | None = None


@dataclass(frozen=True, slots=True)
class PriceObservation:
    product_id: int
    price: float
    observed_at: datetime
    id: int | None = None
    store_id: str | None = None
    merchant_id: str | None = None
    chain_id: str | None = None
    unit_price: float | None = None
    quantity: float | None = None
    unit: str | None = None
    normal_price: float | None = None
    observation_context: str = REGULAR
    promotion_event_id: int | None = None
    raw_observation_id: int | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    source_type: str = UNKNOWN
    confidence_state: str = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class PriceAssessment:
    primary_status: str
    flags: tuple[str, ...]
    current_price: float
    current_unit_price: float | None
    reference_price: float | None
    reference_type: str | None
    difference_amount: float | None
    difference_percent: float | None
    advertised_discount_percent: float | None
    observed_discount_vs_reference_percent: float | None
    history_observation_count: int
    history_span_days: int
    reference_confidence: str
    explanation_key: str
    ranking_score: float
    stable_reference_price: float | None = None
    previous_price: float | None = None


@dataclass(frozen=True, slots=True)
class PriceChangeEvent:
    observed_at: datetime
    previous_price: float
    current_price: float
    change_percent: float
    kind: str
    previous_unit_price: float | None = None
    current_unit_price: float | None = None
