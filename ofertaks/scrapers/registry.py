"""Scraper registry."""

from __future__ import annotations

from ofertaks.scrapers.base import BaseScraper
from ofertaks.scrapers.etc import ETCScraper
from ofertaks.scrapers.interex import InterexScraper
from ofertaks.scrapers.viva import VivaFreshScraper

SCRAPER_CLASSES: tuple[type[BaseScraper], ...] = (
    VivaFreshScraper,
    InterexScraper,
    ETCScraper,
)


def create_scrapers(**kwargs) -> list[BaseScraper]:
    return [scraper_class(**kwargs) for scraper_class in SCRAPER_CLASSES]


def scraper_by_store_id(store_id: str) -> type[BaseScraper] | None:
    for scraper_class in SCRAPER_CLASSES:
        if scraper_class.store_id == store_id:
            return scraper_class
    return None
