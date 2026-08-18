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
