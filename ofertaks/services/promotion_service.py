"""Truthful promotion classification from robust historical price references."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

from ofertaks.database.repository import Repository


@dataclass(frozen=True, slots=True)
class PriceReferences:
    count: int
    median_30d: float | None
    median_90d: float | None
    median_365d: float | None
    median_all_time: float | None
    minimum_all_time: float | None


@dataclass(frozen=True, slots=True)
class PromotionAssessment:
    classification: str
    reference_price: float | None
    references: PriceReferences


class PromotionAnalysisService:
    def __init__(self, repository: Repository, min_history: int = 3):
        self.repository = repository
        self.min_history = min_history

    def references_for_product(self, product_id: int, now: datetime | None = None) -> PriceReferences:
        now = now or datetime.now(UTC)
        rows = self.repository.historical_prices(product_id)
        entries = [(float(row["price"]), self._as_datetime(row["observed_at"])) for row in rows]

        def window(days: int) -> float | None:
            values = [price for price, observed_at in entries if observed_at >= now - timedelta(days=days)]
            return round(float(median(values)), 2) if values else None

        all_prices = [price for price, _ in entries]
        return PriceReferences(
            count=len(all_prices),
            median_30d=window(30),
            median_90d=window(90),
            median_365d=window(365),
            median_all_time=round(float(median(all_prices)), 2) if all_prices else None,
            minimum_all_time=min(all_prices) if all_prices else None,
        )

    def assess(
        self,
        product_id: int,
        current_price: float,
        advertised_normal_price: float | None = None,
        now: datetime | None = None,
    ) -> PromotionAssessment:
        references = self.references_for_product(product_id, now)
        if references.count < self.min_history:
            return PromotionAssessment("INSUFFICIENT_HISTORY", None, references)
        reference = references.median_90d or references.median_365d or references.median_all_time
        if reference is None:
            return PromotionAssessment("INSUFFICIENT_HISTORY", None, references)
        ratio = current_price / reference
        if ratio <= 0.80:
            classification = "EXCEPTIONAL_PRICE"
        elif ratio <= 0.95:
            classification = "GOOD_PRICE"
        elif advertised_normal_price and advertised_normal_price > current_price and ratio >= 0.98:
            classification = "PROMOTION_WEAK"
        elif ratio > 1.05:
            classification = "ABOVE_USUAL"
        else:
            classification = "NORMAL_PRICE"
        return PromotionAssessment(classification, reference, references)

    def _as_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
