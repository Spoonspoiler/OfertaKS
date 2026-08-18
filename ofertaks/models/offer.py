"""Unified offer model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class Offer:
    store_id: str
    store_name: str
    raw_name: str
    normalized_name: str
    brand: str | None
    quantity: float | None
    unit: str | None
    normal_price: float | None
    offer_price: float
    unit_price: float | None
    discount_percent: float | None
    valid_from: date | None
    valid_until: date | None
    category: str | None
    source_url: str
    image_url: str | None
    scraped_at: datetime

    def to_record(self) -> dict[str, Any]:
        return {
            "store_id": self.store_id,
            "raw_name": self.raw_name,
            "normalized_name": self.normalized_name,
            "brand": self.brand,
            "quantity": self.quantity,
            "unit": self.unit,
            "normal_price": self.normal_price,
            "offer_price": self.offer_price,
            "unit_price": self.unit_price,
            "discount_percent": self.discount_percent,
            "category": self.category,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "source_url": self.source_url,
            "image_url": self.image_url,
            "scraped_at": self.scraped_at.isoformat(timespec="seconds"),
        }

    @classmethod
    def from_row(cls, row: Any, store_name: str | None = None) -> "Offer":
        return cls(
            store_id=row["store_id"],
            store_name=store_name or row.get("store_name", row["store_id"]),
            raw_name=row["raw_name"],
            normalized_name=row["normalized_name"],
            brand=row["brand"],
            quantity=row["quantity"],
            unit=row["unit"],
            normal_price=row["normal_price"],
            offer_price=row["offer_price"],
            unit_price=row["unit_price"],
            discount_percent=row["discount_percent"],
            valid_from=date.fromisoformat(row["valid_from"]) if row["valid_from"] else None,
            valid_until=(
                date.fromisoformat(row["valid_until"]) if row["valid_until"] else None
            ),
            category=row["category"],
            source_url=row["source_url"],
            image_url=row["image_url"],
            scraped_at=datetime.fromisoformat(row["scraped_at"]),
        )
