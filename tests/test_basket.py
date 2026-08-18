import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.offer import Offer
from ofertaks.services.basket_service import BasketService


def offer(store_id, store_name, name, price):
    return Offer(
        store_id=store_id,
        store_name=store_name,
        raw_name=name,
        normalized_name=name.casefold(),
        brand=None,
        quantity=None,
        unit=None,
        normal_price=None,
        offer_price=price,
        unit_price=None,
        discount_percent=None,
        valid_from=None,
        valid_until=None,
        category="OTHER",
        source_url="https://example.test",
        image_url=None,
        scraped_at=datetime.now(UTC),
    )


class BasketTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "db.sqlite3"))
        self.repo.initialize()
        self.repo.replace_current_offers(
            "etc",
            [
                offer("etc", "ETC", "Milk 1L", 1.20),
                offer("etc", "ETC", "Coffee 1kg", 12.50),
            ],
        )
        self.repo.replace_current_offers(
            "interex",
            [
                offer("interex", "Interex", "Milk 1L", 1.10),
                offer("interex", "Interex", "Coffee 1kg", 11.99),
            ],
        )
        self.repo.replace_current_offers(
            "viva_fresh",
            [
                offer("viva_fresh", "Viva Fresh", "Milk 1L", 1.05),
                offer("viva_fresh", "Viva Fresh", "Coffee 1kg", 13.20),
            ],
        )
        self.repo.add_basket_item("Milk")
        self.repo.add_basket_item("Coffee")

    def tearDown(self):
        self.tmp.cleanup()

    def test_unlimited_stores(self):
        plan = BasketService(self.repo).cheapest_overall()
        self.assertEqual(plan.total, 13.04)
        self.assertEqual(len(plan.missing), 0)

    def test_maximum_two_stores(self):
        plan = BasketService(self.repo).maximum_stores(2)
        self.assertEqual(plan.total, 13.04)

    def test_one_store(self):
        plans = BasketService(self.repo).one_store_totals()
        self.assertEqual(plans[0].stores, ("Interex",))
        self.assertEqual(plans[0].total, 13.09)
