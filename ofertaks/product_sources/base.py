"""Interfaces for parsing public official product information."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(slots=True)
class OfficialProductMetadata:
    source_type: str
    publisher: str
    url: str
    retrieved_at: datetime
    canonical_name: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    producer: str | None = None
    distributor: str | None = None
    product_family: str | None = None
    variant: str | None = None
    quantity: float | None = None
    unit: str | None = None
    packaging: str | None = None
    flavor: str | None = None
    origin_country: str | None = None
    origin_region: str | None = None
    barcode_gtin: str | None = None
    official_image_url: str | None = None
    raw_metadata: dict | None = field(default=None)


class OfficialProductParser(Protocol):
    def parse(self, url: str, html: str, publisher: str, retrieved_at: datetime) -> OfficialProductMetadata: ...
