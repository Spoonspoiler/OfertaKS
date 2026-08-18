"""ETC scraper."""

from __future__ import annotations

from datetime import date
from urllib.parse import urljoin

from ofertaks.parsing.date_parser import parse_date_range
from ofertaks.parsing.html_utils import image_url_near, make_soup, text_of
from ofertaks.parsing.price_parser import extract_prices, parse_price
from ofertaks.scrapers.base import BaseScraper, ScrapeResult
from ofertaks.utils.text import clean_text, comparable_text

MAGAZINA_URL = "https://etc-ks.com/magazina.php"
LINK_HINTS = ("aktualitet", "oferte", "oferta")
MAX_DETAIL_PAGES = 4


class ETCScraper(BaseScraper):
    store_id = "etc"
    store_name = "ETC"
    website = "https://etc-ks.com/"

    def fetch_and_parse(self) -> ScrapeResult:
        response = self.client.get(MAGAZINA_URL)
        self.save_debug_file("etc-magazina.html", response.text)
        soup = make_soup(response.text)
        detail_links = self._discover_detail_links(soup, response.url)
        if not detail_links:
            detail_links = [MAGAZINA_URL]

        offers = []
        pages_parsed = 0
        for url in detail_links[:MAX_DETAIL_PAGES]:
            detail = self.client.get(url)
            self.save_debug_file(f"etc-detail-{pages_parsed}.html", detail.text)
            detail_soup = make_soup(detail.text)
            offers.extend(self.parse_offer_page(detail_soup, detail.url))
            pages_parsed += 1

        status = "success" if offers else "failed"
        message = None if offers else "No text offers with parseable EUR prices found"
        return ScrapeResult(
            store_id=self.store_id,
            store_name=self.store_name,
            status=status,
            offers=offers,
            error_message=message,
            metadata={"pages_parsed": pages_parsed, "detail_links": detail_links},
        )

    def _discover_detail_links(self, soup, base_url: str) -> list[str]:
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            label = comparable_text(anchor.get_text(" ", strip=True) + " " + href)
            if "aktualiteti.php" in href and any(hint in label for hint in LINK_HINTS):
                absolute = urljoin(base_url, href)
                if absolute not in links:
                    links.append(absolute)
        return links

    def parse_offer_page(self, soup, source_url: str) -> list:
        page_text = text_of(soup)
        valid_from, valid_until = parse_date_range(page_text, today=date.today())
        offers = []
        seen: set[tuple[str, float]] = set()

        for heading in soup.find_all(["h3", "h4", "h5"]):
            name = clean_text(heading.get_text(" ", strip=True))
            if not self._looks_like_product_name(name):
                continue
            context = self._nearby_text(heading)
            if "€" not in context and "eur" not in context.casefold():
                continue
            prices = extract_prices(context)
            if not prices:
                continue
            offer_price = prices[-1]
            normal_price = None
            if len(prices) >= 2:
                normal_price = max(prices[0], prices[-1])
                offer_price = min(prices[0], prices[-1]) if prices[0] != prices[-1] else prices[-1]
            key = (name.casefold(), offer_price)
            if key in seen:
                continue
            seen.add(key)
            offers.append(
                self.make_offer(
                    name,
                    offer_price,
                    source_url,
                    normal_price=normal_price if normal_price != offer_price else None,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    image_url=image_url_near(heading, source_url),
                    extra_text=context,
                )
            )
        return offers

    def _looks_like_product_name(self, name: str) -> bool:
        if len(name) < 3 or len(name) > 90:
            return False
        if parse_price(name):
            return False
        lowered = comparable_text(name)
        blocked = {"aktualitet", "produkte", "zhanre", "fletushka", "oferta"}
        return lowered not in blocked

    def _nearby_text(self, heading) -> str:
        node = heading
        for _ in range(4):
            node = node.parent if node is not None else None
            if node is None:
                break
            text = text_of(node)
            if extract_prices(text):
                return text
        chunks = [text_of(heading)]
        sibling = heading.find_next_sibling()
        count = 0
        while sibling is not None and count < 8:
            chunks.append(text_of(sibling))
            if sibling.name in {"h3", "h4", "h5"}:
                break
            sibling = sibling.find_next_sibling()
            count += 1
        return clean_text(" ".join(chunks))
