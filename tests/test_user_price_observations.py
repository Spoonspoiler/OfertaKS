import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.community import UserPriceObservation
from ofertaks.models.offer import Offer


class UserPriceObservationTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "db.sqlite3"))
        self.repo.initialize()
        offer = Offer(
            store_id="etc",
            store_name="ETC",
            raw_name="Tomatoes",
            normalized_name="tomatoes",
            brand=None,
            quantity=1000,
            unit="g",
            normal_price=None,
            offer_price=1.5,
            unit_price=1.5,
            discount_percent=None,
            valid_from=None,
            valid_until=None,
            category="FRUIT_VEGETABLE",
            source_url="https://example.test",
            image_url=None,
            scraped_at=datetime.now(UTC),
        )
        self.repo.insert_offer(offer)
        self.product_id = self.repo.find_product_id_for_offer(offer)

    def tearDown(self):
        self.tmp.cleanup()

    def test_observation_retains_photo_quality_and_origin_provenance(self):
        observation_id = self.repo.record_user_price_observation(
            UserPriceObservation(
                merchant_name="Local market",
                raw_name="Tomatoes",
                normalized_name="tomatoes",
                price=1.2,
                observed_at=datetime.now(UTC),
                product_id=self.product_id,
                quantity=1000,
                unit="g",
                origin_country="Kosovo",
                origin_region="Rahovec",
                origin_source="STORE_LABEL",
                origin_confidence="verified",
                photo_path="C:/photos/tomatoes.jpg",
                quality="good",
                notes="Fresh stock",
            )
        )
        rows = self.repo.list_user_price_observations(self.product_id)
        self.assertEqual(rows[0]["id"], observation_id)
        self.assertEqual(rows[0]["photo_path"], "C:/photos/tomatoes.jpg")
        self.assertEqual(rows[0]["quality"], "good")
        origin = self.repo.list_origin_observations(self.product_id)[0]
        self.assertEqual(origin["country"], "Kosovo")
        self.assertEqual(origin["source"], "STORE_LABEL")

    def test_zero_price_is_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.record_user_price_observation(
                UserPriceObservation(
                    merchant_name="Local market",
                    raw_name="Tomatoes",
                    normalized_name="tomatoes",
                    price=0,
                    observed_at=datetime.now(UTC),
                )
            )
