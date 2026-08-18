"""Careful, bounded OpenStreetMap food-place discovery for the active market."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ofertaks.app.config import CHAIN_CONFIG
from ofertaks.app.paths import get_map_cache_dir
from ofertaks.database.repository import Repository
from ofertaks.maps.region import MarketRegion
from ofertaks.models.merchant import (
    BAKERY,
    BUTCHER,
    CONVENIENCE,
    DAIRY,
    FARM,
    FISH,
    FRUIT_VEGETABLE,
    GROCERY,
    MARKET,
    SPECIALTY_FOOD,
    SUPERMARKET,
    Merchant,
    SOURCE_OSM,
)
from ofertaks.utils.network import HTTPClient
from ofertaks.utils.text import comparable_text

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"

OSM_SHOP_TYPES = {
    "supermarket": SUPERMARKET,
    "convenience": CONVENIENCE,
    "greengrocer": FRUIT_VEGETABLE,
    "bakery": BAKERY,
    "butcher": BUTCHER,
    "seafood": FISH,
    "farm": FARM,
    "deli": SPECIALTY_FOOD,
    "cheese": DAIRY,
    "health_food": SPECIALTY_FOOD,
}


@dataclass(frozen=True, slots=True)
class OSMImportResult:
    region_id: str
    imported: int
    updated: int
    skipped: int
    fetched_at: datetime
    cache_path: Path


def merchant_type_from_osm_tags(tags: dict[str, str]) -> str | None:
    """Map only food-related OSM tags to OfertaKS merchant types."""

    shop = tags.get("shop", "").casefold()
    if shop in OSM_SHOP_TYPES:
        return OSM_SHOP_TYPES[shop]
    if tags.get("amenity", "").casefold() == "marketplace":
        return MARKET
    if tags.get("shop", "").casefold() == "grocery":
        return GROCERY
    return None


def detect_known_chain(tags: dict[str, str]) -> str | None:
    """Detect registered chains from raw OSM name, brand, or operator values."""

    candidate = " ".join(
        value for value in (tags.get("name"), tags.get("brand"), tags.get("operator")) if value
    )
    normalized = comparable_text(candidate)
    if not normalized:
        return None
    for chain_id, data in CHAIN_CONFIG.items():
        aliases = (data["name"], *data.get("aliases", ()))
        if any(comparable_text(alias) in normalized for alias in aliases):
            return chain_id
    return None


def build_food_place_query(region: MarketRegion) -> str:
    """Build one Overpass request limited to food-relevant tags in one region."""

    min_lat, min_lon, max_lat, max_lon = region.bbox
    bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    return f"""[out:json][timeout:25];
(
  nwr[\"shop\"~\"^(supermarket|convenience|grocery|greengrocer|bakery|butcher|seafood|farm|deli|cheese|health_food)$\"]({bbox});
  nwr[\"amenity\"=\"marketplace\"]({bbox});
);
out center tags;"""


class OverpassMerchantImporter:
    """One-request importer that persists real OSM places into local SQLite."""

    def __init__(
        self,
        repository: Repository,
        region: MarketRegion,
        http_client: HTTPClient | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.repository = repository
        self.region = region
        self.http_client = http_client or HTTPClient()
        self.cache_dir = cache_dir or get_map_cache_dir() / "osm"

    @property
    def cache_path(self) -> Path:
        return self.cache_dir / f"{self.region.id}_food_merchants.json"

    def fetch_payload(self) -> dict[str, Any]:
        """Fetch one bounded regional response and cache it outside the repository."""

        encoded = urlencode({"data": build_food_place_query(self.region)})
        response = self.http_client.get(f"{OVERPASS_ENDPOINT}?{encoded}", timeout=35)
        if response.status_code != 200:
            raise RuntimeError(f"Overpass returned HTTP {response.status_code}")
        payload = json.loads(response.text)
        if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
            raise RuntimeError("Overpass response did not contain elements")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload

    def load_cached_payload(self) -> dict[str, Any] | None:
        if not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload.get("elements"), list) else None

    def import_region(self, *, use_cached: bool = False) -> OSMImportResult:
        payload = self.load_cached_payload() if use_cached else None
        payload = payload or self.fetch_payload()
        return self.import_payload(payload)

    def import_payload(self, payload: dict[str, Any]) -> OSMImportResult:
        imported = updated = skipped = 0
        seen_at = datetime.now(UTC)
        for element in payload.get("elements", []):
            merchant = self._merchant_from_element(element, seen_at)
            if merchant is None:
                skipped += 1
                continue
            existing = self.repository.get_merchant_by_source(SOURCE_OSM, merchant.source_id or "")
            if existing:
                merchant.id = existing["id"]
                updated += 1
            else:
                imported += 1
            # Similar names from OSM, chains, or community data remain separate
            # until a future review can explicitly resolve a LIKELY/POSSIBLE match.
            self.repository.add_merchant(merchant)
        return OSMImportResult(
            region_id=self.region.id,
            imported=imported,
            updated=updated,
            skipped=skipped,
            fetched_at=seen_at,
            cache_path=self.cache_path,
        )

    def _merchant_from_element(self, element: dict[str, Any], seen_at: datetime) -> Merchant | None:
        tags = {str(key): str(value) for key, value in (element.get("tags") or {}).items()}
        merchant_type = merchant_type_from_osm_tags(tags)
        latitude = element.get("lat") or (element.get("center") or {}).get("lat")
        longitude = element.get("lon") or (element.get("center") or {}).get("lon")
        name = tags.get("name") or tags.get("brand") or tags.get("operator")
        element_type = str(element.get("type") or "")
        element_id = element.get("id")
        if not (merchant_type and name and latitude is not None and longitude is not None and element_type and element_id):
            return None
        address = " ".join(
            value
            for value in (tags.get("addr:housenumber"), tags.get("addr:street"))
            if value
        ) or None
        source_id = f"{element_type}/{element_id}"
        return Merchant(
            id=f"osm-{element_type}-{element_id}",
            name=name,
            merchant_type=merchant_type,
            chain_id=detect_known_chain(tags),
            latitude=float(latitude),
            longitude=float(longitude),
            address=address,
            city=tags.get("addr:city") or self.region.city,
            phone=tags.get("phone") or tags.get("contact:phone"),
            website=tags.get("website") or tags.get("contact:website"),
            opening_hours={"raw": tags["opening_hours"]} if tags.get("opening_hours") else None,
            payment_cash=_tag_bool(tags.get("payment:cash")),
            payment_card=_tag_bool(tags.get("payment:cards")),
            source_type=SOURCE_OSM,
            source_id=source_id,
            osm_type=element_type,
            osm_id=str(element_id),
            osm_tags=tags,
            source_last_seen_at=seen_at,
            verification_status="OSM_LISTED",
        )


def _tag_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.casefold() in {"yes", "true", "1"}
