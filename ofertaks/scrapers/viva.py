"""Viva Fresh public catalogue scraper."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urljoin

from ofertaks.parsing.html_utils import make_soup, text_of
from ofertaks.parsing.price_parser import extract_prices
from ofertaks.parsing.unit_parser import parse_quantity
from ofertaks.scrapers.base import BaseScraper, ScrapeResult
from ofertaks.utils.categories import (
    BAKERY,
    DAIRY,
    DRINK,
    FROZEN,
    FRUIT_VEGETABLE,
    MEAT,
    PANTRY,
    SNACKS,
)
from ofertaks.utils.text import clean_text

OFFERS_URL = "https://vivafresh-rks.com/ofertat/"
ONLINE_STORE_URL = "https://online.vivafresh.shop/"
CATALOG_PROXY_URL = f"{ONLINE_STORE_URL}lib/config/proxy.php"
CATALOG_ORGANIZATION_ID = 9
CATALOG_PAGE_SIZE = 100
CATALOG_LEVEL2_BATCH_SIZE = 25
MAX_CATALOG_PAGES = 500
PRODUCT_SELECTORS = (
    "[itemtype*='Product']",
    ".product",
    ".offer",
    ".oferta",
    ".elementor-post",
)

# These identifiers are exposed by Viva Fresh's public category endpoint. The
# remaining groups are retained with their source category and normalized by
# the usual classifier, which keeps the scraper useful beyond food browsing.
VIVA_CATEGORY_MAP = {
    1: FRUIT_VEGETABLE,
    2: MEAT,
    3: MEAT,
    4: DAIRY,
    5: BAKERY,
    6: FROZEN,
    7: PANTRY,
    8: PANTRY,
    9: PANTRY,
    10: PANTRY,
    11: PANTRY,
    12: PANTRY,
    13: SNACKS,
    14: SNACKS,
    15: DRINK,
    16: DRINK,
    17: PANTRY,
}


class VivaFreshScraper(BaseScraper):
    store_id = "viva_fresh"
    store_name = "Viva Fresh"
    website = ONLINE_STORE_URL
    catalog_level2_batch_size = CATALOG_LEVEL2_BATCH_SIZE

    def fetch_and_parse(self) -> ScrapeResult:
        try:
            return self._fetch_public_catalog()
        except Exception as exc:
            return self._fetch_promotional_fallback(str(exc))

    def _fetch_public_catalog(self) -> ScrapeResult:
        categories = self._active_records(self._catalog_get("category/level1"))
        category_names = {
            self._integer_id(category): clean_text(str(category.get("name") or ""))
            for category in categories
            if self._integer_id(category) is not None
        }
        if not category_names:
            raise RuntimeError("the public catalogue exposed no active top-level categories")

        category_ids = ",".join(str(category_id) for category_id in category_names)
        subcategories = self._active_records(
            self._catalog_get(f"subcategory/level2?category_ids={category_ids}")
        )
        if not subcategories:
            raise RuntimeError("the public catalogue exposed no active subcategories")

        offers = []
        seen_product_ids: set[int] = set()
        pages_fetched = 0
        products_seen = 0
        out_of_stock = 0

        subcategories_by_id = {
            level2_id: subcategory
            for subcategory in subcategories
            if (level2_id := self._integer_id(subcategory)) is not None
        }
        for level2_ids in self._batches(list(subcategories_by_id), self.catalog_level2_batch_size):
            page = 1
            while True:
                if pages_fetched >= MAX_CATALOG_PAGES:
                    raise RuntimeError("public catalogue pagination exceeded the safety limit")
                payload = self._catalog_post(
                    "shop/get-products-byLvl2",
                    {
                        "organization_id": CATALOG_ORGANIZATION_ID,
                        "level2_ids": level2_ids,
                        "page": page,
                        "per_page": CATALOG_PAGE_SIZE,
                    },
                )
                pages_fetched += 1
                for level2_id in level2_ids:
                    subcategory = subcategories_by_id[level2_id]
                    level1_id = self._level1_id(subcategory)
                    products = self._products_from_payload(payload.get("data"), level2_id)
                    products_seen += len(products)
                    for product in products:
                        product_id = self._integer_id(product)
                        if product_id is None or product_id in seen_product_ids:
                            continue
                        seen_product_ids.add(product_id)
                        if product.get("out_of_stock") or self._is_nonpositive_stock(product.get("stock")):
                            out_of_stock += 1
                            continue
                        offer = self._offer_from_product(
                            product,
                            level1_id=level1_id,
                            level1_name=category_names.get(level1_id, ""),
                            level2_name=clean_text(str(subcategory.get("name") or "")),
                        )
                        if offer is not None:
                            offers.append(offer)

                meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
                last_page = self._positive_integer(meta.get("last_page"), default=page)
                if page >= last_page:
                    break
                page += 1

        if not offers:
            raise RuntimeError("the public catalogue returned no in-stock products with valid prices")
        return ScrapeResult(
            self.store_id,
            self.store_name,
            "success",
            offers,
            metadata={
                "catalog_url": ONLINE_STORE_URL,
                "organization_id": CATALOG_ORGANIZATION_ID,
                "categories": len(category_names),
                "subcategories": len(subcategories),
                "pages_fetched": pages_fetched,
                "products_seen": products_seen,
                "out_of_stock_skipped": out_of_stock,
            },
        )

    def _fetch_promotional_fallback(self, catalog_error: str) -> ScrapeResult:
        try:
            response = self.client.get(OFFERS_URL)
        except Exception as exc:
            return ScrapeResult(
                self.store_id,
                self.store_name,
                "partial",
                error_message=(
                    f"Public Viva Fresh catalogue unavailable ({catalog_error}); "
                    f"promotional page also unavailable ({exc})"
                ),
            )

        self.save_debug_file("viva-ofertat.html", response.text)
        soup = make_soup(response.text)
        offers = self._parse_json_ld(soup, response.url)
        if not offers:
            offers = self._parse_structured_cards(soup, response.url)
        if offers:
            return ScrapeResult(
                self.store_id,
                self.store_name,
                "success",
                offers,
                metadata={"catalog_fallback": True, "catalog_error": catalog_error},
            )

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
                f"Public Viva Fresh catalogue unavailable ({catalog_error}); "
                "promotional page is image-based and OCR is not implemented"
            ),
            metadata={"image_count": len(images), "images": images[:20]},
        )

    def _catalog_get(self, endpoint: str) -> dict[str, Any]:
        url = f"{CATALOG_PROXY_URL}?endpoint={quote(endpoint, safe='')}"
        return self._json_payload(self.client.get(url))

    def _catalog_post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{CATALOG_PROXY_URL}?endpoint={quote(endpoint, safe='')}"
        return self._json_payload(
            self.client.post_json(url, payload, headers={"X-Requested-With": "XMLHttpRequest"})
        )

    @staticmethod
    def _json_payload(response: Any) -> dict[str, Any]:
        try:
            payload = json.loads(response.text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("public catalogue returned invalid JSON") from exc
        if not isinstance(payload, dict) or payload.get("success") is False:
            raise RuntimeError("public catalogue request was rejected")
        return payload

    @staticmethod
    def _active_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        records = payload.get("data")
        if not isinstance(records, list):
            return []
        return [record for record in records if isinstance(record, dict) and record.get("active", True)]

    @staticmethod
    def _products_from_payload(data: Any, level2_id: int) -> list[dict[str, Any]]:
        if isinstance(data, dict):
            products = data.get(str(level2_id), data.get(level2_id, []))
        else:
            products = data
        return [product for product in products if isinstance(product, dict)] if isinstance(products, list) else []

    @staticmethod
    def _batches(values: list[int], size: int) -> list[list[int]]:
        return [values[index : index + size] for index in range(0, len(values), max(size, 1))]

    def _offer_from_product(
        self,
        product: dict[str, Any],
        *,
        level1_id: int | None,
        level1_name: str,
        level2_name: str,
    ):
        name = clean_text(str(product.get("name") or ""))
        price = self._price(product.get("final_price"))
        if not name or price is None:
            return None
        normal_price = self._price(product.get("base_price"))
        if normal_price is not None and normal_price <= price:
            normal_price = None
        images = product.get("images")
        image_url = self._first_image_url(images)
        quantity_override, unit_override = self._unit_override(product.get("unit_of_measure"), name)
        source_category = clean_text(" / ".join(part for part in (level1_name, level2_name) if part))
        product_id = self._integer_id(product)
        return self.make_offer(
            name,
            price,
            f"{ONLINE_STORE_URL}product?id={product_id}",
            normal_price=normal_price,
            category=VIVA_CATEGORY_MAP.get(level1_id),
            raw_category=source_category,
            image_url=image_url,
            quantity_override=quantity_override,
            unit_override=unit_override,
        )

    @staticmethod
    def _unit_override(unit_of_measure: Any, product_name: str) -> tuple[float | None, str | None]:
        unit = clean_text(str(unit_of_measure or "")).upper()
        if unit == "KG":
            return 1000.0, "g"
        if unit in {"L", "LT"}:
            return 1000.0, "ml"
        if unit in {"COP", "COPE", "PCS", "PIECE"} and parse_quantity(product_name) is None:
            return 1.0, "piece"
        return None, None

    @staticmethod
    def _first_image_url(images: Any) -> str | None:
        if not isinstance(images, list):
            return None
        for image in images:
            if not isinstance(image, dict):
                continue
            url = clean_text(str(image.get("url") or image.get("src") or ""))
            if url:
                return url
        return None

    @staticmethod
    def _integer_id(record: dict[str, Any]) -> int | None:
        try:
            return int(record.get("id"))
        except (TypeError, ValueError):
            return None

    def _level1_id(self, subcategory: dict[str, Any]) -> int | None:
        parent = subcategory.get("categories_lvl_1")
        if isinstance(parent, dict):
            parent_id = self._integer_id(parent)
            if parent_id is not None:
                return parent_id
        try:
            return int(subcategory.get("categories_lvl_1_id"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _positive_integer(value: Any, *, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _price(value: Any) -> float | None:
        try:
            price = float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return None
        return price if price > 0 else None

    @staticmethod
    def _is_nonpositive_stock(value: Any) -> bool:
        if value in (None, ""):
            return False
        try:
            return float(str(value).replace(",", ".")) <= 0
        except (TypeError, ValueError):
            return False

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
                price_value = self._price(price)
                if price_value is not None:
                    offers.append(
                        self.make_offer(
                            name,
                            price_value,
                            source_url,
                            image_url=product.get("image") if isinstance(product.get("image"), str) else None,
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
                offers.append(self.make_offer(name, price, source_url, image_url=image_url, extra_text=text))
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
