"""Interex flyer/PDF scraper."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from urllib.parse import urljoin

from ofertaks.parsing.date_parser import parse_date_range
from ofertaks.parsing.html_utils import make_soup, text_of
from ofertaks.parsing.pdf_utils import extract_text_from_pdf_bytes
from ofertaks.parsing.price_parser import extract_prices
from ofertaks.scrapers.base import BaseScraper, ScrapeResult
from ofertaks.utils.text import clean_text

FLYER_URL = "https://fletushka.interex-rks.com/"
MAX_PDFS = 2


@dataclass(slots=True)
class Flyer:
    title: str
    valid_from: date | None
    valid_until: date | None
    pdf_url: str


class InterexScraper(BaseScraper):
    store_id = "interex"
    store_name = "Interex"
    website = "https://interex-rks.com/"

    def fetch_and_parse(self) -> ScrapeResult:
        response = self.client.get(FLYER_URL)
        self.save_debug_file("interex-flyers.html", response.text)
        soup = make_soup(response.text)
        flyers = self.parse_flyer_index(soup, response.url)
        if not flyers:
            return ScrapeResult(
                self.store_id,
                self.store_name,
                "failed",
                error_message="No flyer PDF links found",
            )

        offers = []
        extraction_statuses = []
        for index, flyer in enumerate(flyers[:MAX_PDFS]):
            pdf_response = self.client.get(flyer.pdf_url)
            self.save_debug_file(f"interex-flyer-{index}.pdf", pdf_response.content)
            extraction = extract_text_from_pdf_bytes(pdf_response.content)
            extraction_statuses.append(
                {
                    "title": flyer.title,
                    "pdf_url": flyer.pdf_url,
                    "extraction_status": extraction.status,
                    "pages": extraction.pages,
                    "error": extraction.error,
                }
            )
            if extraction.status == "success":
                offers.extend(self.parse_pdf_text(extraction.text, flyer))

        if offers:
            status = "success"
            error = None
        else:
            status = "partial"
            error = "Flyer metadata found but no text offers extracted; OCR may be required"
        return ScrapeResult(
            self.store_id,
            self.store_name,
            status,
            offers,
            error_message=error,
            metadata={"flyers": [asdict(f) for f in flyers], "extraction": extraction_statuses},
        )

    def parse_flyer_index(self, soup, base_url: str) -> list[Flyer]:
        flyers = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if ".pdf" not in href.casefold():
                continue
            pdf_url = urljoin(base_url, href)
            container = anchor.find_parent(["article", "li", "div", "section"]) or anchor.parent
            text = text_of(container)
            title = self._flyer_title(container) or clean_text(anchor.get_text(" ", strip=True))
            valid_from, valid_until = parse_date_range(text)
            flyers.append(Flyer(title=title or pdf_url.rsplit("/", 1)[-1], valid_from=valid_from, valid_until=valid_until, pdf_url=pdf_url))
        return self._sort_flyers(flyers)

    def _flyer_title(self, container) -> str | None:
        if not container:
            return None
        for tag_name in ("h1", "h2", "h3", "h4", "h5"):
            tag = container.find(tag_name)
            if tag:
                value = clean_text(tag.get_text(" ", strip=True))
                if value:
                    return value
        return None

    def _sort_flyers(self, flyers: list[Flyer]) -> list[Flyer]:
        return sorted(
            flyers,
            key=lambda flyer: flyer.valid_until or flyer.valid_from or date.min,
            reverse=True,
        )

    def parse_pdf_text(self, text: str, flyer: Flyer) -> list:
        offers = []
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        seen: set[tuple[str, float]] = set()
        for idx, line in enumerate(lines):
            prices = extract_prices(line)
            if not prices:
                continue
            previous = lines[idx - 1] if idx else ""
            name = self._product_name_from_pdf_lines(previous, line)
            if not name:
                continue
            offer_price = prices[-1]
            normal_price = max(prices) if len(prices) >= 2 else None
            key = (name.casefold(), offer_price)
            if key in seen:
                continue
            seen.add(key)
            offers.append(
                self.make_offer(
                    name,
                    offer_price,
                    flyer.pdf_url,
                    normal_price=normal_price if normal_price != offer_price else None,
                    valid_from=flyer.valid_from,
                    valid_until=flyer.valid_until,
                    extra_text=line,
                )
            )
        return offers

    def _product_name_from_pdf_lines(self, previous: str, line: str) -> str | None:
        candidate = previous
        if not candidate or extract_prices(candidate):
            candidate = re.sub(r"\d+(?:[,.]\d+)?\s*(?:€|eur)", "", line, flags=re.I)
        candidate = clean_text(candidate)
        if len(candidate) < 3 or len(candidate) > 90:
            return None
        if candidate.isdigit():
            return None
        return candidate
