import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.offer import Offer
from ofertaks.utils.categories import FROZEN, HOUSEHOLD, PANTRY, detect_category


def make_offer(name: str, category: str, price: float = 1.0) -> Offer:
    return Offer(
        store_id="etc",
        store_name="ETC",
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
        category=category,
        source_url="https://example.test",
        image_url=None,
        scraped_at=datetime.now(UTC),
    )


class FoodCatalogTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "db.sqlite3"))
        self.repo.initialize()
        self.repo.insert_offer(make_offer("Pasta", "FOOD"))
        self.repo.insert_offer(make_offer("Frozen peas", FROZEN, 1.2))
        self.repo.insert_offer(make_offer("Dish detergent", HOUSEHOLD, 2.0))

    def tearDown(self):
        self.tmp.cleanup()

    def test_main_catalog_defaults_to_food_only(self):
        names = {offer.raw_name for offer in self.repo.list_offers()}
        self.assertEqual(names, {"Pasta", "Frozen peas"})
        all_names = {offer.raw_name for offer in self.repo.list_offers(food_only=False)}
        self.assertIn("Dish detergent", all_names)
        self.assertEqual(self.repo.search_offers("Dish"), [])
        self.assertEqual(
            [offer.raw_name for offer in self.repo.search_offers("Dish", food_only=False)],
            ["Dish detergent"],
        )

    def test_pantry_filter_includes_legacy_food_data(self):
        self.assertEqual(
            [offer.raw_name for offer in self.repo.list_offers(category=PANTRY)],
            ["Pasta"],
        )

    def test_detection_keeps_non_food_out_of_food_categories(self):
        self.assertEqual(detect_category("Frozen chicken"), FROZEN)
        self.assertEqual(detect_category("Dish detergent"), HOUSEHOLD)
