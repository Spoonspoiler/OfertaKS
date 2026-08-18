"""Community observation models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class QualityObservation:
    product_id: int | None
    merchant_id: str
    observed_at: datetime
    taste_score: float | None = None
    freshness_score: float | None = None
    appearance_score: float | None = None
    value_score: float | None = None
    comment: str | None = None
    confidence: float = 0.5
    confirmation_count: int = 0


@dataclass(slots=True)
class OriginObservation:
    country: str
    source: str
    observed_at: datetime
    product_id: int | None = None
    merchant_id: str | None = None
    raw_name: str | None = None
    normalized_name: str | None = None
    region: str | None = None
    producer: str | None = None
    confidence: float = 0.4


@dataclass(slots=True)
class UserPriceObservation:
    """A local, user-submitted price update awaiting any future sync."""

    merchant_name: str
    raw_name: str
    normalized_name: str
    price: float
    observed_at: datetime
    product_id: int | None = None
    merchant_id: str | None = None
    quantity: float | None = None
    unit: str | None = None
    origin_country: str | None = None
    origin_region: str | None = None
    origin_source: str = "UNKNOWN"
    origin_confidence: str = "unknown"
    photo_path: str | None = None
    quality: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class MerchantProductObservation:
    """Local availability evidence. Unlike a price update, price may be absent."""

    merchant_id: str
    raw_name: str
    normalized_name: str
    observed_at: datetime
    product_id: int | None = None
    price: float | None = None
    quantity: float | None = None
    unit: str | None = None
    origin_country: str | None = None
    origin_region: str | None = None
    origin_source: str = "USER_OBSERVATION"
    origin_confidence: str = "unknown"
    photo_path: str | None = None
    quality: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class MerchantReport:
    merchant_id: str
    report_type: str
    reported_at: datetime
    notes: str | None = None
