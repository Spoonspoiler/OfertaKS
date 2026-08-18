"""Viewport, filter, and product-evidence logic for the OfertaKS map overlay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from ofertaks.community.observations import freshness_state
from ofertaks.database.repository import Repository
from ofertaks.models.community import MerchantReport
from ofertaks.models.merchant import (
    BAKERY,
    BUTCHER,
    CONVENIENCE,
    COMMUNITY_UNVERIFIED,
    DAIRY,
    FARM,
    FISH,
    FRUIT_VEGETABLE,
    GROCERY,
    MARKET,
    MARKET_STALL,
    SOURCE_COMMUNITY,
    SPECIALTY_FOOD,
    STREET_VENDOR,
    SUPERMARKET,
    Merchant,
    INDEPENDENT_LOCAL,
    LOCAL_CHAIN,
)
from ofertaks.services.comparison_service import classify_price_status
from ofertaks.services.history_service import HistoryService
from ofertaks.services.merchant_deals import MerchantDealSummary, MerchantDealSummaryService
from ofertaks.services.recommendations import ConsumerRecommendationService

ALL_FOOD_FILTER = "all_food"
MAP_FILTER_TYPES = {
    ALL_FOOD_FILTER: None,
    "supermarkets": (SUPERMARKET, CONVENIENCE),
    "local_shops": None,
    "markets": (MARKET, MARKET_STALL),
    "fruit_vegetables": (FRUIT_VEGETABLE,),
    "bakeries": (BAKERY,),
    "butchers_fish": (BUTCHER, FISH),
    "best_deals": None,
    "price_warnings": None,
}

AVAILABILITY_CURRENT = "CURRENT"
AVAILABILITY_STALE = "STALE"
AVAILABILITY_UNKNOWN = "UNKNOWN"

MARKER_CODES = {
    SUPERMARKET: "SM",
    CONVENIENCE: "LS",
    GROCERY: "LS",
    FRUIT_VEGETABLE: "FV",
    MARKET: "MK",
    MARKET_STALL: "MK",
    BAKERY: "BK",
    BUTCHER: "BT",
    FISH: "FS",
    FARM: "FM",
    DAIRY: "DY",
    SPECIALTY_FOOD: "SF",
    STREET_VENDOR: "LS",
}


@dataclass(slots=True)
class MapMerchantResult:
    merchant: dict
    availability: str
    observation: dict | None
    price_status_key: str
    price_status_color: str
    marker_code: str
    deal_summary: MerchantDealSummary | None = None


class MapService:
    def __init__(self, repository: Repository):
        self.repository = repository
        self.deals = MerchantDealSummaryService(repository)
        self.recommendations = ConsumerRecommendationService(repository)

    def viewport_merchants(
        self,
        bbox: tuple[float, float, float, float],
        filter_id: str = ALL_FOOD_FILTER,
        product_id: int | None = None,
        limit: int = 80,
    ) -> list[MapMerchantResult]:
        min_lat, min_lon, max_lat, max_lon = bbox
        types = MAP_FILTER_TYPES.get(filter_id)
        merchants = self.repository.find_merchants_in_bbox(
            min_lat, min_lon, max_lat, max_lon, types, limit
        )
        if filter_id == "local_shops":
            merchants = [
                merchant
                for merchant in merchants
                if merchant.get("ownership_type") in {INDEPENDENT_LOCAL, LOCAL_CHAIN}
            ]
        evidence = self.repository.latest_product_evidence(product_id) if product_id else {}
        category = self.repository.product_category(product_id) if product_id else None
        history = HistoryService(self.repository).stats_for_product(product_id) if product_id else None
        summaries = self.deals.summaries_for_merchants([merchant["id"] for merchant in merchants])
        results = [
            self._result_for(
                merchant,
                evidence.get(merchant["id"]),
                category,
                history,
                summaries.get(merchant["id"]),
            )
            for merchant in merchants
        ]
        if filter_id == "best_deals":
            results = [
                result
                for result in results
                if result.deal_summary
                and (
                    result.deal_summary.exceptional_deal_count
                    or result.deal_summary.good_deal_count
                    or any(deal.best_nearby for deal in result.deal_summary.best_deals)
                )
            ]
        elif filter_id == "price_warnings":
            results = [
                result
                for result in results
                if result.deal_summary and result.deal_summary.price_integrity_warning_count
            ]
        recommended_ids = {
            item.merchant_id for item in self.recommendations.recommend(product_id) if item.recommended
        } if product_id else set()
        return sorted(
            results,
            key=lambda result: (
                0 if result.merchant["id"] in recommended_ids else 1,
                -(result.deal_summary.exceptional_deal_count if result.deal_summary else 0),
                -(result.deal_summary.good_deal_count if result.deal_summary else 0),
                result.merchant["name"],
            ),
        )

    def add_community_merchant(
        self,
        *,
        name: str,
        merchant_type: str,
        latitude: float,
        longitude: float,
        description: str | None = None,
        opening_hours: str | None = None,
        photo_path: str | None = None,
        ownership_type: str = "UNKNOWN",
    ) -> str:
        if not name.strip():
            raise ValueError("A display name is required")
        merchant = Merchant(
            id=f"community-{uuid4().hex}",
            name=name.strip(),
            merchant_type=merchant_type,
            chain_id=None,
            latitude=latitude,
            longitude=longitude,
            ownership_type=ownership_type,
            city="Prishtina",
            opening_hours={"raw": opening_hours} if opening_hours else None,
            community_added=True,
            verification_status=COMMUNITY_UNVERIFIED,
            community_status=COMMUNITY_UNVERIFIED,
            source_type=SOURCE_COMMUNITY,
            source_id=None,
            description=description or None,
            photo_path=photo_path or None,
        )
        return self.repository.add_merchant(merchant)

    def report_merchant(self, merchant_id: str, report_type: str, notes: str | None = None) -> int:
        return self.repository.record_merchant_report(
            MerchantReport(merchant_id=merchant_id, report_type=report_type, notes=notes, reported_at=datetime.now(UTC))
        )

    def _result_for(
        self,
        merchant: dict,
        observation: dict | None,
        category: str | None,
        history,
        summary: MerchantDealSummary | None,
    ) -> MapMerchantResult:
        if observation is None:
            availability = AVAILABILITY_UNKNOWN
            status_key = "not_enough_history"
            status_color = "neutral"
        else:
            observed_at = datetime.fromisoformat(observation["observed_at"])
            freshness = freshness_state(observed_at, category)
            availability = AVAILABILITY_CURRENT if freshness.state == "fresh" else AVAILABILITY_STALE
            if observation.get("price") is not None:
                status = classify_price_status(float(observation["price"]), history)
                status_key, status_color = status.key, status.color_key
            else:
                status_key, status_color = "not_enough_history", "neutral"
        if summary and summary.exceptional_deal_count:
            status_key, status_color = "price_integrity_exceptional", "exceptional"
        elif summary and summary.good_deal_count:
            status_key, status_color = "price_integrity_good", "cheap"
        elif summary and summary.price_integrity_warning_count:
            status_key, status_color = "price_integrity_weak_promotion", "expensive"
        marker_code = self._marker_label(merchant)
        return MapMerchantResult(
            merchant=merchant,
            availability=availability,
            observation=observation,
            price_status_key=status_key,
            price_status_color=status_color,
            marker_code=marker_code,
            deal_summary=summary,
        )

    def _marker_label(self, merchant: dict) -> str:
        """Make known chain markers identifiable without inventing branch facts."""

        chain_id = merchant.get("chain_id")
        if chain_id:
            chain = next((item for item in self.repository.chains() if item["id"] == chain_id), None)
            if chain:
                return chain["name"][:12]
        name = (merchant.get("name") or "").strip()
        if name:
            return name[:12]
        return MARKER_CODES.get(merchant["merchant_type"], "Food")
