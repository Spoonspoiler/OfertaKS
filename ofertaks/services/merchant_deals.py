"""Bounded, consumer-first current-deal summaries for map merchants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ofertaks.community.observations import freshness_state
from ofertaks.database.repository import Repository
from ofertaks.models.pricing import (
    BEST_NEARBY_PRICE,
    EXCEPTIONAL_DEAL,
    GOOD_DEAL,
    INSUFFICIENT_HISTORY,
    NORMAL_PRICE,
    WEAK_PROMOTION,
    PriceAssessment,
)
from ofertaks.services.price_integrity import PriceIntegrityService


@dataclass(frozen=True, slots=True)
class MerchantDeal:
    merchant_id: str
    product_id: int
    raw_name: str
    price: float
    unit_price: float | None
    observed_at: datetime
    assessment: PriceAssessment
    best_nearby: bool
    origin_country: str | None = None


@dataclass(frozen=True, slots=True)
class MerchantDealSummary:
    merchant_id: str
    exceptional_deal_count: int
    good_deal_count: int
    normal_price_count: int
    weak_promotion_count: int
    price_integrity_warning_count: int
    recent_price_observation_count: int
    best_deals: tuple[MerchantDeal, ...]
    warnings: tuple[MerchantDeal, ...]
    generated_at: datetime


class MerchantDealSummaryService:
    """Derive map summaries from current local evidence only.

    The ranking has no input for partner, chain size, payment, or commercial
    relationship. A merchant competes only on evidence, product identity,
    freshness, and price.
    """

    def __init__(self, repository: Repository, integrity: PriceIntegrityService | None = None):
        self.repository = repository
        self.integrity = integrity or PriceIntegrityService(repository)

    def summaries_for_merchants(
        self, merchant_ids: list[str], now: datetime | None = None
    ) -> dict[str, MerchantDealSummary]:
        now = now or datetime.now(UTC)
        current = self.repository.current_merchant_prices(merchant_ids)
        current_by_product: dict[int, list[dict]] = {}
        for row in current:
            current_by_product.setdefault(int(row["product_id"]), []).append(row)
        deals_by_merchant: dict[str, list[MerchantDeal]] = {merchant_id: [] for merchant_id in merchant_ids}
        for row in current:
            product_id = int(row["product_id"])
            observed_at = self._as_datetime(row["observed_at"])
            category = self.repository.product_category(product_id)
            freshness = freshness_state(observed_at, category, now)
            if freshness.stale:
                continue
            promotion = self._merchant_promotion(product_id, row["merchant_id"], now)
            assessment = self.integrity.assess(
                product_id,
                float(row["price"]),
                current_unit_price=row.get("unit_price"),
                quantity=row.get("quantity"),
                unit=row.get("unit"),
                promotion=promotion,
                observed_at=now,
                merchant_id=row["merchant_id"],
                chain_id=row.get("chain_id"),
            )
            deals_by_merchant.setdefault(row["merchant_id"], []).append(
                MerchantDeal(
                    merchant_id=row["merchant_id"],
                    product_id=product_id,
                    raw_name=row["raw_name"],
                    price=float(row["price"]),
                    unit_price=self.integrity._current_unit_value(row),
                    observed_at=observed_at,
                    assessment=assessment,
                    best_nearby=self.integrity.best_nearby(row["merchant_id"], product_id, current_by_product[product_id]),
                    origin_country=row.get("origin_country"),
                )
            )
        return {merchant_id: self._summary(merchant_id, deals_by_merchant.get(merchant_id, []), now) for merchant_id in merchant_ids}

    def _merchant_promotion(self, product_id: int, merchant_id: str, now: datetime) -> dict | None:
        events = self.repository.active_promotion_events(product_id, merchant_id=merchant_id, now=now)
        return events[0] if events else None

    def _summary(self, merchant_id: str, deals: list[MerchantDeal], now: datetime) -> MerchantDealSummary:
        ranked = sorted(deals, key=self._deal_sort_key)
        warnings = [
            deal
            for deal in ranked
            if deal.assessment.primary_status == WEAK_PROMOTION or deal.assessment.flags
        ]
        highlights = [
            deal
            for deal in ranked
            if deal.assessment.primary_status in {EXCEPTIONAL_DEAL, GOOD_DEAL} or deal.best_nearby
        ]
        return MerchantDealSummary(
            merchant_id=merchant_id,
            exceptional_deal_count=sum(deal.assessment.primary_status == EXCEPTIONAL_DEAL for deal in deals),
            good_deal_count=sum(deal.assessment.primary_status == GOOD_DEAL for deal in deals),
            normal_price_count=sum(deal.assessment.primary_status == NORMAL_PRICE for deal in deals),
            weak_promotion_count=sum(deal.assessment.primary_status == WEAK_PROMOTION for deal in deals),
            price_integrity_warning_count=len(warnings),
            recent_price_observation_count=len(deals),
            best_deals=tuple(highlights[:4]),
            warnings=tuple(warnings[:3]),
            generated_at=now,
        )

    @staticmethod
    def _deal_sort_key(deal: MerchantDeal) -> tuple[int, int, float, float]:
        status_order = {
            EXCEPTIONAL_DEAL: 0,
            GOOD_DEAL: 1,
            INSUFFICIENT_HISTORY: 3,
        }.get(deal.assessment.primary_status, 2)
        nearby_order = 0 if deal.best_nearby else 1
        return (status_order, nearby_order, -deal.assessment.ranking_score, deal.price)

    @staticmethod
    def _as_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
