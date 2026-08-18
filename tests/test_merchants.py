import tempfile
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.merchant import FRUIT_VEGETABLE, GROCERY, Merchant
from ofertaks.routing.distance import haversine_km
from ofertaks.services.merchant_service import MerchantService


class MerchantTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "db.sqlite3"))
        self.repo.initialize()
        self.service = MerchantService(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_haversine_distance(self):
        distance = haversine_km(42.6629, 21.1655, 42.6639, 21.1665)
        self.assertGreater(distance, 0.1)
        self.assertLess(distance, 0.2)

    def test_nearby_merchants(self):
        self.service.add_merchant(
            Merchant(
                id="ulpiana-veg",
                name="Ulpiana vegetable seller",
                merchant_type=FRUIT_VEGETABLE,
                chain_id=None,
                latitude=42.6559,
                longitude=21.1628,
                city="Prishtina",
            )
        )
        matches = self.service.nearby(42.6558, 21.1627, max_distance_km=0.2)
        self.assertEqual(matches[0].merchant["id"], "ulpiana-veg")

    def test_duplicate_detection_warns_but_does_not_merge(self):
        self.service.add_merchant(
            Merchant(
                id="corner-grocery",
                name="Corner Grocery Ulpiana",
                merchant_type=GROCERY,
                chain_id=None,
                latitude=42.6558,
                longitude=21.1627,
            )
        )
        duplicate = Merchant(
            id="new-corner-grocery",
            name="Corner grocery",
            merchant_type=GROCERY,
            chain_id=None,
            latitude=42.65581,
            longitude=21.16272,
        )
        candidates = self.service.duplicate_candidates(duplicate)
        self.assertEqual(candidates[0].merchant["id"], "corner-grocery")
        self.assertEqual(self.repo.list_merchants()[0]["id"], "corner-grocery")
