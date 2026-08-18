import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.offer import Offer


def make_offer(name="Coca-Cola 1.5L", price=1.29):
    return Offer(
        store_id="etc",
        store_name="ETC",
        raw_name=name,
        normalized_name="coca cola",
        brand="Coca-Cola",
        quantity=1500,
        unit="ml",
        normal_price=1.69,
        offer_price=price,
        unit_price=0.86,
        discount_percent=24,
        valid_from=None,
        valid_until=None,
        category="DRINK",
        source_url="https://example.test",
        image_url=None,
        scraped_at=datetime.now(UTC),
    )


class DatabaseTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "db.sqlite3"))
        self.repo.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_insert_offer_and_history(self):
        offer = make_offer()
        self.repo.insert_offer(offer)
        offers = self.repo.search_offers("Coca")
        self.assertEqual(len(offers), 1)
        product_id = self.repo.find_product_id_for_offer(offers[0])
        self.assertIsNotNone(product_id)
        self.assertEqual(len(self.repo.price_history(product_id)), 1)

    def test_replace_current_offers_retains_history(self):
        self.repo.replace_current_offers("etc", [make_offer(price=1.29)])
        first = self.repo.search_offers("Coca")[0]
        product_id = self.repo.find_product_id_for_offer(first)
        self.repo.replace_current_offers("etc", [make_offer(price=1.19)])
        self.assertEqual(len(self.repo.search_offers("Coca")), 1)
        self.assertEqual(len(self.repo.price_history(product_id)), 2)

    def test_scraper_status(self):
        run_id = self.repo.start_scrape_run("etc")
        self.repo.finish_scrape_run(run_id, "success", 2, None)
        diagnostics = self.repo.diagnostics()
        self.assertEqual(diagnostics["last_runs"][0]["status"], "success")
