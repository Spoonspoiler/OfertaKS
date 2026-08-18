"""Explicit registry for parsers of already retrieved public product pages."""

from __future__ import annotations

from datetime import datetime

from ofertaks.product_sources.base import OfficialProductMetadata, OfficialProductParser


class ProductSourceRegistry:
    """Keep source adapters modular without giving them implicit network access."""

    def __init__(self) -> None:
        self._parsers: dict[str, OfficialProductParser] = {}

    def register(self, source_type: str, parser: OfficialProductParser) -> None:
        key = source_type.upper().strip()
        if not key:
            raise ValueError("A product source type is required")
        self._parsers[key] = parser

    def parse(
        self,
        source_type: str,
        url: str,
        html: str,
        publisher: str,
        retrieved_at: datetime,
    ) -> OfficialProductMetadata:
        try:
            parser = self._parsers[source_type.upper().strip()]
        except KeyError as error:
            raise ValueError(f"No product parser is registered for {source_type!r}") from error
        return parser.parse(url, html, publisher, retrieved_at)
