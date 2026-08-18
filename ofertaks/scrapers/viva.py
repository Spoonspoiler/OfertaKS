"""Viva Fresh scraper."""

from __future__ import annotations

import json
from urllib.parse import urljoin

from ofertaks.parsing.html_utils import make_soup, text_of
from ofertaks.parsing.price_parser import extract_prices
from ofertaks.scrapers.base import BaseScraper, ScrapeResult
from ofertaks.utils.text import clean_text

OFFERS_URL = "https://vivafresh-rks.com/ofertat/"
PRODUCT_SELECTORS = (
    "[itemtype*='Product']",
    ".product",
    ".offer",
    ".oferta",
    ".elementor-post",
)


class VivaFreshScraper(BaseScraper):
    store_id = "viva_fresh"
    store_name = "Viva Fresh"
    website = "https://vivafresh-rks.com/"

    def fetch_and_parse(self) -> ScrapeResult:
        response = self.client.get(OFFERS_URL)
        self.save_debug_file("viva-ofertat.html", response.text)
        soup = make_soup(response.text)

        offers = self._parse_json_ld(soup, response.url)
        if not offers:
            offers = self._parse_structured_cards(soup, response.url)

        if offers:
            return ScrapeResult(self.store_id, self.store_name, "success", offers)

        images = [
            urljoin(response.url, image.get("src") or "")
            for image in soup.find_all("img")
            if image.get("src")
        ]
        return ScrapeResult(
            store_id=self.store_id,
            store_name=self.store_name,
            status="partial",
            offers=[],
            error_message=(
                "Viva Fresh current offers appear image-based; OCR is not implemented"
            ),
            metadata={"image_count": len(images), "images": images[:20]},
        )

    def _parse_json_ld(self, soup, source_url: str) -> list:
        offers = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                payload = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                offers.extend(self._offers_from_json_item(item, source_url))
        return offers

    def _offers_from_json_item(self, item, source_url: str) -> list:
        if not isinstance(item, dict):
            return []
        candidates = []
        if item.get("@type") == "Product":
            candidates.append(item)
        graph = item.get("@graph")
        if isinstance(graph, list):
            candidates.extend(node for node in graph if isinstance(node, dict))
        offers = []
        for product in candidates:
            name = product.get("name")
            offer_data = product.get("offers") or {}
            price = offer_data.get("price") if isinstance(offer_data, dict) else None
            if name and price:
                try:
                    price_value = float(str(price).replace(",", "."))
                except ValueError:
                    continue
                offers.append(
                    self.make_offer(
                        name,
                        price_value,
                        source_url,
                        image_url=product.get("image")
                        if isinstance(product.get("image"), str)
                        else None,
                    )
                )
        return offers

    def _parse_structured_cards(self, soup, source_url: str) -> list:
        offers = []
        seen: set[tuple[str, float]] = set()
        for selector in PRODUCT_SELECTORS:
            for card in soup.select(selector):
                text = text_of(card)
                prices = extract_prices(text)
                if not prices:
                    continue
                name = self._name_from_card(card)
                if not name:
                    continue
                price = prices[-1]
                key = (name.casefold(), price)
                if key in seen:
                    continue
                seen.add(key)
                image = card.find("img")
                image_url = urljoin(source_url, image.get("src")) if image and image.get("src") else None
                offers.append(
                    self.make_offer(name, price, source_url, image_url=image_url, extra_text=text)
                )
        return offers

    def _name_from_card(self, card) -> str | None:
        for selector in ("[itemprop='name']", "h2", "h3", "h4", ".title", ".name"):
            node = card.select_one(selector)
            if node:
                value = clean_text(node.get_text(" ", strip=True))
                if len(value) > 2:
                    return value
        image = card.find("img")
        if image:
            alt = clean_text(image.get("alt") or image.get("title") or "")
            if len(alt) > 2 and not alt.lower().startswith("image"):
                return alt
        return None
