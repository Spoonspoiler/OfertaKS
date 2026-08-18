"""Base scraper contracts and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ofertaks.app import config
from ofertaks.models.offer import Offer
from ofertaks.normalization.product_normalizer import normalize_product_name
from ofertaks.parsing.price_parser import parse_discount_percent
from ofertaks.parsing.unit_parser import calculate_unit_price
from ofertaks.utils.network import HTTPClient
from ofertaks.utils.text import clean_text


@dataclass(slots=True)
class ScrapeResult:
    store_id: str
    store_name: str
    status: str
    offers: list[Offer] = field(default_factory=list)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def items_found(self) -> int:
        return len(self.offers)


class BaseScraper:
    store_id = ""
    store_name = ""
    website = ""

    def __init__(self, client: HTTPClient | None = None, debug_dir: Path | None = None):
        self.client = client or HTTPClient()
        self.debug_dir = debug_dir

    def scrape(self) -> ScrapeResult:
        try:
            result = self.fetch_and_parse()
        except Exception as exc:
            return ScrapeResult(
                store_id=self.store_id,
                store_name=self.store_name,
                status="failed",
                error_message=str(exc),
            )
        return result

    def fetch_and_parse(self) -> ScrapeResult:
        raise NotImplementedError

    def make_offer(
        self,
        raw_name: str,
        offer_price: float,
        source_url: str,
        *,
        normal_price: float | None = None,
        valid_from: date | None = None,
        valid_until: date | None = None,
        category: str | None = None,
        image_url: str | None = None,
        scraped_at: datetime | None = None,
        raw_category: str | None = None,
        extra_text: str = "",
    ) -> Offer:
        raw_name = clean_text(raw_name)
        normalized = normalize_product_name(raw_name, raw_category=raw_category or category)
        quantity = normalized.quantity
        unit = normalized.unit
        unit_price = calculate_unit_price(offer_price, quantity, unit)
        discount = parse_discount_percent(extra_text)
        if discount is None and normal_price and normal_price > offer_price:
            discount = round((normal_price - offer_price) / normal_price * 100, 2)
        return Offer(
            store_id=self.store_id,
            store_name=self.store_name,
            raw_name=raw_name,
            normalized_name=normalized.normalized_name,
            brand=normalized.brand,
            quantity=quantity,
            unit=unit,
            normal_price=normal_price,
            offer_price=offer_price,
            unit_price=unit_price,
            discount_percent=discount,
            valid_from=valid_from,
            valid_until=valid_until,
            category=category or normalized.category,
            source_url=source_url,
            image_url=image_url,
            scraped_at=scraped_at or datetime.now(UTC),
        )

    def save_debug_file(self, name: str, content: bytes | str) -> None:
        if not config.DEBUG_SCRAPERS or self.debug_dir is None:
            return
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        path = self.debug_dir / name
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)
