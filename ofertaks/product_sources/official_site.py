"""Parse product schema metadata from an already retrieved official page."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from ofertaks.parsing.unit_parser import parse_quantity
from ofertaks.product_sources.base import OfficialProductMetadata


def _product_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        types = value.get("@type", ())
        types = (types,) if isinstance(types, str) else types
        if "Product" in types:
            return value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                found = _product_object(item)
                if found:
                    return found
    if isinstance(value, list):
        for item in value:
            found = _product_object(item)
            if found:
                return found
    return None


def _name(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        nested = value.get("name")
        return nested.strip() if isinstance(nested, str) and nested.strip() else None
    return None


def parse_official_product_page(
    url: str,
    html: str,
    publisher: str,
    retrieved_at: datetime,
    *,
    source_type: str = "OFFICIAL_MANUFACTURER",
) -> OfficialProductMetadata:
    """Extract declared schema fields only; absent data remains absent."""

    soup = BeautifulSoup(html, "html.parser")
    product: dict[str, Any] = {}
    for script in soup.select("script[type='application/ld+json']"):
        try:
            payload = json.loads(script.get_text(strip=True))
        except json.JSONDecodeError:
            continue
        product = _product_object(payload) or {}
        if product:
            break
    name = _name(product.get("name"))
    description = _name(product.get("description"))
    quantity = parse_quantity(" ".join(value for value in (name, description) if value))
    image = product.get("image")
    if isinstance(image, list):
        image = next((item for item in image if isinstance(item, str)), None)
    brand = _name(product.get("brand"))
    manufacturer = _name(product.get("manufacturer"))
    country = _name(product.get("countryOfOrigin"))
    return OfficialProductMetadata(
        source_type=source_type,
        publisher=publisher,
        url=url,
        retrieved_at=retrieved_at,
        canonical_name=name,
        brand=brand,
        manufacturer=manufacturer,
        quantity=quantity.quantity if quantity else None,
        unit=quantity.unit if quantity else None,
        origin_country=country,
        barcode_gtin=_name(product.get("gtin13")) or _name(product.get("gtin")),
        official_image_url=image if isinstance(image, str) else None,
        raw_metadata=product or None,
    )
