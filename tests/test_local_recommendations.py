from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.community import UserPriceObservation
from ofertaks.models.knowledge import CanonicalProduct
from ofertaks.models.merchant import GROCERY, INDEPENDENT_LOCAL, Merchant, OWNERSHIP_UNKNOWN
from ofertaks.services.recommendations import ConsumerRecommendationService


class LocalRecommendationTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repository = Repository(Database(Path(self.tmp.name) / "local.sqlite3"))
        self.repository.initialize()
        self.product_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="Apples", category="FRUIT_VEGETABLE")
        )
        self._merchant("local", "Local market", INDEPENDENT_LOCAL)
        self._merchant("chain", "Chain market", OWNERSHIP_UNKNOWN)

    def tearDown(self):
        self.tmp.cleanup()

    def _merchant(self, merchant_id: str, name: str, ownership_type: str) -> None:
        self.repository.add_merchant(
            Merchant(
                id=merchant_id,
                name=name,
                merchant_type=GROCERY,
                chain_id=None,
                latitude=42.65,
                longitude=21.15,
                ownership_type=ownership_type,
            )
        )

    def test_local_merchant_is_recommended_within_explicit_tolerance(self):
        now = datetime.now(UTC)
        for merchant_id, price in (("local", 1.05), ("chain", 1.00)):
            self.repository.record_user_price_observation(
                UserPriceObservation(
                    merchant_name=merchant_id,
                    merchant_id=merchant_id,
                    product_id=self.product_id,
                    raw_name="Apples",
                    normalized_name="apples",
                    price=price,
                    observed_at=now,
                )
            )

        recommendations = ConsumerRecommendationService(self.repository).recommend(self.product_id)
        by_merchant = {item.merchant_id: item for item in recommendations}

        self.assertTrue(by_merchant["chain"].absolute_cheapest)
        self.assertTrue(by_merchant["local"].recommended)
        self.assertEqual(by_merchant["local"].reason, "local_within_tolerance")
