"""Synchronization orchestration."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ofertaks.database.repository import Repository
from ofertaks.scrapers.base import BaseScraper, ScrapeResult
from ofertaks.scrapers.registry import create_scrapers
from ofertaks.utils.logger import log_event
from ofertaks.utils.network import HTTPClient

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SyncSummary:
    results: tuple[ScrapeResult, ...]

    @property
    def total_offers(self) -> int:
        return sum(result.items_found for result in self.results)

    @property
    def ok(self) -> bool:
        return any(result.status == "success" for result in self.results)


ProgressCallback = Callable[[str, str, str | None], None]


class SyncService:
    def __init__(self, repository: Repository, debug_dir: Path | None = None):
        self.repository = repository
        self.debug_dir = debug_dir
        self.client = HTTPClient()

    def sync_all(self, progress: ProgressCallback | None = None) -> SyncSummary:
        enabled_store_ids = {store["id"] for store in self.repository.stores(enabled_only=True)}
        scrapers = [
            scraper
            for scraper in create_scrapers(client=self.client, debug_dir=self.debug_dir)
            if scraper.store_id in enabled_store_ids
        ]
        results: list[ScrapeResult] = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(self._sync_store, scraper, progress): scraper for scraper in scrapers}
            for future in as_completed(futures):
                results.append(future.result())
        return SyncSummary(tuple(results))

    def _sync_store(
        self, scraper: BaseScraper, progress: ProgressCallback | None
    ) -> ScrapeResult:
        if progress:
            progress(scraper.store_id, "running", None)
        run_id = self.repository.start_scrape_run(scraper.store_id)
        result = scraper.scrape()
        try:
            if result.status == "success":
                self.repository.replace_current_offers(scraper.store_id, result.offers)
            self.repository.finish_scrape_run(
                run_id, result.status, result.items_found, result.error_message
            )
            log_event(
                LOGGER,
                "scraper_finished",
                store_id=scraper.store_id,
                status=result.status,
                items_found=result.items_found,
                error=result.error_message,
            )
        except Exception as exc:
            self.repository.finish_scrape_run(run_id, "failed", 0, str(exc))
            result = ScrapeResult(
                scraper.store_id,
                scraper.store_name,
                "failed",
                error_message=f"Persistence failed: {exc}",
            )
        if progress:
            progress(scraper.store_id, result.status, result.error_message)
        return result
