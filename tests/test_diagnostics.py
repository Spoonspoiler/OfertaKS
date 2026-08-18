import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.offer import Offer


class DiagnosticsSummaryTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "db.sqlite3"))
        self.repo.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary_reports_food_counts_and_source_capabilities(self):
        self.repo.insert_offer(
            Offer(
                store_id="etc",
                store_name="ETC",
                raw_name="Milk",
                normalized_name="milk",
                brand=None,
                quantity=None,
                unit=None,
                normal_price=None,
                offer_price=1.0,
                unit_price=None,
                discount_percent=None,
                valid_from=None,
                valid_until=None,
                category="DAIRY",
                source_url="https://example.test",
                image_url=None,
                scraped_at=datetime.now(UTC),
            )
        )
        summary = self.repo.diagnostics_summary()
        statuses = {item["id"]: item for item in summary["last_scraper_runs"]}
        self.assertEqual(summary["store_count"], 4)
        self.assertEqual(summary["live_store_count"], 1)
        self.assertEqual(summary["food_offer_count"], 1)
        self.assertEqual(statuses["etc"]["availability"], "live")
        self.assertEqual(statuses["albi"]["availability"], "not_implemented")
        self.assertTrue(summary["database_writable"])
