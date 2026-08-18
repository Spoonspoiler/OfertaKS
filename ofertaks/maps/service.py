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
)
from ofertaks.services.comparison_service import classify_price_status
from ofertaks.services.history_service import HistoryService

ALL_FOOD_FILTER = "all_food"
MAP_FILTER_TYPES = {
    ALL_FOOD_FILTER: None,
    "supermarkets": (SUPERMARKET, CONVENIENCE),
    "local_shops": (GROCERY, CONVENIENCE, DAIRY, FARM, SPECIALTY_FOOD, STREET_VENDOR),
    "markets": (MARKET, MARKET_STALL),
    "fruit_vegetables": (FRUIT_VEGETABLE,),
    "bakeries": (BAKERY,),
    "butchers_fish": (BUTCHER, FISH),
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


class MapService:
    def __init__(self, repository: Repository):
        self.repository = repository

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
        evidence = self.repository.latest_product_evidence(product_id) if product_id else {}
        category = self.repository.product_category(product_id) if product_id else None
        history = HistoryService(self.repository).stats_for_product(product_id) if product_id else None
        return [
            self._result_for(merchant, evidence.get(merchant["id"]), category, history)
            for merchant in merchants
        ]

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

    def _result_for(self, merchant: dict, observation: dict | None, category: str | None, history) -> MapMerchantResult:
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
        return MapMerchantResult(
            merchant=merchant,
            availability=availability,
            observation=observation,
            price_status_key=status_key,
            price_status_color=status_color,
            marker_code=MARKER_CODES.get(merchant["merchant_type"], "FD"),
        )
