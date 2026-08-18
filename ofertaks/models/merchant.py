"""Merchant and chain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

SUPERMARKET = "SUPERMARKET"
GROCERY = "GROCERY"
CONVENIENCE = "CONVENIENCE"
MARKET = "MARKET"
MARKET_STALL = "MARKET_STALL"
FRUIT_VEGETABLE = "FRUIT_VEGETABLE"
BUTCHER = "BUTCHER"
BAKERY = "BAKERY"
DAIRY = "DAIRY"
FISH = "FISH"
FARM = "FARM"
FARMER = "FARMER"  # Legacy persisted value retained for existing local databases.
SPECIALTY_FOOD = "SPECIALTY_FOOD"
STREET_VENDOR = "STREET_VENDOR"
OTHER_FOOD = "OTHER_FOOD"
OTHER = "OTHER"  # Legacy persisted value retained for existing local databases.

MERCHANT_TYPES = {
    SUPERMARKET,
    GROCERY,
    CONVENIENCE,
    MARKET,
    MARKET_STALL,
    FRUIT_VEGETABLE,
    BUTCHER,
    BAKERY,
    DAIRY,
    FISH,
    FARM,
    FARMER,
    SPECIALTY_FOOD,
    STREET_VENDOR,
    OTHER_FOOD,
    OTHER,
}

SOURCE_OSM = "OSM"
SOURCE_CHAIN_OFFICIAL = "CHAIN_OFFICIAL"
SOURCE_COMMUNITY = "COMMUNITY"
SOURCE_MERCHANT = "MERCHANT"
SOURCE_ADMIN = "ADMIN"

COMMUNITY_UNVERIFIED = "COMMUNITY_UNVERIFIED"
COMMUNITY_CONFIRMED = "COMMUNITY_CONFIRMED"
MERCHANT_VERIFIED = "MERCHANT_VERIFIED"
ADMIN_VERIFIED = "ADMIN_VERIFIED"
CLOSED_REPORTED = "CLOSED_REPORTED"


@dataclass(slots=True)
class Chain:
    id: str
    name: str
    website: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Merchant:
    id: str
    name: str
    merchant_type: str
    chain_id: str | None
    latitude: float
    longitude: float
    address: str | None = None
    city: str | None = None
    neighborhood: str | None = None
    phone: str | None = None
    website: str | None = None
    opening_hours: dict[str, Any] | None = None
    payment_cash: bool | None = None
    payment_card: bool | None = None
    community_added: bool = False
    claimed_by_merchant: bool = False
    verification_status: str = "unverified"
    source_type: str = "UNKNOWN"
    source_id: str | None = None
    osm_type: str | None = None
    osm_id: str | None = None
    osm_tags: dict[str, Any] | None = None
    source_last_seen_at: datetime | None = None
    merchant_last_verified_at: datetime | None = None
    description: str | None = None
    photo_path: str | None = None
    community_status: str = "NOT_COMMUNITY"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.merchant_type not in MERCHANT_TYPES:
            raise ValueError(f"Unknown merchant type: {self.merchant_type}")
