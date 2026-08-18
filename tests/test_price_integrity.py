from __future__ import annotations

import tempfile
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.maps.service import MapService
from ofertaks.models.community import UserPriceObservation
from ofertaks.models.knowledge import CanonicalProduct, RawObservation
from ofertaks.models.merchant import GROCERY, Merchant
from ofertaks.models.pricing import (
    ADVERTISED_DISCOUNT_MISMATCH,
    EXCEPTIONAL_DEAL,
    EXPENSIVE,
    GOOD_DEAL,
    INSUFFICIENT_HISTORY,
    NORMAL_PRICE,
    PACKAGE_PRICE_UNCHANGED_UNIT_INCREASE,
    PRICE_INCREASE_BEFORE_PROMOTION,
    PROMOTION,
    RECENT_PRICE_INCREASE,
    VERY_EXPENSIVE,
    WEAK_PROMOTION,
    PriceObservation,
    PromotionEvent,
)
from ofertaks.models.offer import Offer
from ofertaks.services.merchant_deals import MerchantDealSummaryService
from ofertaks.services.price_integrity import HistoricalPriceStatsService, PriceIntegrityService
from ofertaks.ui.widgets.offer_card import OfferCardMixin


class PriceIntegrityTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repository = Repository(Database(Path(self.tmp.name) / "integrity.sqlite3"))
        self.repository.initialize()
        self.now = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        self._product_number = 0

    def tearDown(self):
        self.tmp.cleanup()

    def _product(self, name: str = "Olive oil") -> int:
        self._product_number += 1
        return self.repository.create_canonical_product(
            CanonicalProduct(
                id=None,
                canonical_name=f"{name} {self._product_number}",
                category="PANTRY",
            )
        )

    def _price(
        self,
        product_id: int,
        value: float,
        days_ago: int,
        *,
        quantity: float | None = None,
        unit: str | None = None,
        context: str = "REGULAR",
        raw_observation_id: int | None = None,
    ) -> int:
        return self.repository.record_price_observation(
            PriceObservation(
                product_id=product_id,
                price=value,
                observed_at=self.now - timedelta(days=days_ago),
                store_id="etc",
                quantity=quantity,
                unit=unit,
                observation_context=context,
                raw_observation_id=raw_observation_id,
                source_type="TEST",
            )
        )

    def _regular_history(self, product_id: int, value: float = 1.20) -> None:
        for days_ago in (80, 50, 20):
            self._price(product_id, value, days_ago)

    def _merchant(self, merchant_id: str, name: str, latitude: float) -> None:
        self.repository.add_merchant(
            Merchant(
                id=merchant_id,
                name=name,
                merchant_type=GROCERY,
                chain_id=None,
                latitude=latitude,
                longitude=21.15,
            )
        )

    def test_statistics_use_exact_append_only_history_and_medians(self):
        product_id = self._product()
        for value, days_ago in ((1.0, 80), (1.2, 50), (1.4, 20), (1.3, 5)):
            self._price(product_id, value, days_ago)

        stats = HistoricalPriceStatsService(self.repository).statistics(product_id, now=self.now)

        self.assertEqual(stats.observation_count, 4)
        self.assertEqual(stats.median_90d, 1.25)
        self.assertEqual(stats.minimum_30d, 1.3)
        self.assertEqual(stats.maximum_365d, 1.4)
        self.assertEqual(stats.stable_reference_price, 1.25)
        self.assertEqual(stats.reference_confidence, "MODERATE")

    def test_v6_migrates_existing_price_history_without_losing_rows(self):
        product_id = self._product()
        path = self.repository.database.path
        legacy_db = sqlite3.connect(path)
        try:
            db = legacy_db
            db.execute("ALTER TABLE price_history RENAME TO price_history_v5")
            for index in (
                "idx_price_history_product",
                "idx_price_history_store",
                "idx_price_history_merchant",
                "idx_price_history_chain",
                "idx_price_history_context",
            ):
                db.execute(f"DROP INDEX IF EXISTS {index}")
            db.execute("DROP TABLE price_history_v5")
            db.execute(
                """
                CREATE TABLE price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    store_id TEXT NOT NULL REFERENCES stores(id),
                    price REAL NOT NULL,
                    normal_price REAL,
                    observed_at TEXT NOT NULL,
                    raw_observation_id INTEGER,
                    source_type TEXT,
                    confidence_state TEXT
                )
                """
            )
            db.execute(
                """
                INSERT INTO price_history (
                    product_id, store_id, price, normal_price, observed_at, source_type, confidence_state
                ) VALUES (?, 'etc', 3.5, 4.0, ?, 'LEGACY', 'MEDIUM')
                """,
                (product_id, self.now.isoformat(timespec="seconds")),
            )
            legacy_db.commit()
        finally:
            legacy_db.close()
        self.repository.initialize()

        rows = self.repository.price_timeline(product_id)
        with self.repository.database.connect() as db:
            fields = {row["name"] for row in db.execute("PRAGMA table_info(price_history)")}

        self.assertIn("observation_context", fields)
        self.assertIn("promotion_event_id", fields)
        self.assertIn("unit_price", fields)
        self.assertEqual(rows[0]["price"], 3.5)
        self.assertEqual(rows[0]["observation_context"], "REGULAR")

    def test_raw_evidence_linked_to_price_history_is_not_double_counted(self):
        product_id = self._product()
        raw_id = self.repository.record_raw_observation(
            RawObservation(
                id=None,
                raw_name="Olive oil",
                source_type="FLYER",
                created_at=self.now,
                store_id="etc",
                parsed_price=4.5,
                observed_at=self.now,
                canonical_product_id=product_id,
                matching_status="CONFIRMED",
            )
        )
        self._price(product_id, 4.5, 0, raw_observation_id=raw_id)

        timeline = self.repository.price_timeline(product_id)

        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["evidence_kind"], "PRICE_HISTORY")

    def test_exact_product_identity_does_not_borrow_other_product_history(self):
        target = self._product("Brand A olive oil")
        other = self._product("Brand B olive oil")
        self._regular_history(other, 4.0)
        self._price(target, 2.0, 30)
        self._price(target, 2.1, 10)

        assessment = PriceIntegrityService(self.repository).assess(target, 1.0, observed_at=self.now)

        self.assertEqual(assessment.primary_status, INSUFFICIENT_HISTORY)
        self.assertEqual(assessment.history_observation_count, 2)

    def test_exceptional_and_weak_promotion_are_distinct(self):
        product_id = self._product()
        self._regular_history(product_id, 1.20)
        integrity = PriceIntegrityService(self.repository)

        exceptional = integrity.assess(product_id, 0.90, observed_at=self.now)
        self.assertEqual(exceptional.primary_status, EXCEPTIONAL_DEAL)

        event = PromotionEvent(
            canonical_product_id=product_id,
            promo_price=1.20,
            observed_at=self.now,
            advertised_reference_price=1.80,
            advertised_discount_percent=33.3,
            valid_from=self.now.date(),
            valid_until=(self.now + timedelta(days=3)).date(),
            source_type="FLYER",
            geographic_scope="CHAIN",
        )
        event_id = self.repository.record_promotion_event(event)
        self.assertEqual(self.repository.record_promotion_event(event), event_id)
        self.assertEqual(len(self.repository.active_promotion_events(product_id, now=self.now)), 1)
        weak = integrity.assess(product_id, 1.20, promotion=event, observed_at=self.now)

        self.assertEqual(weak.primary_status, WEAK_PROMOTION)

    def test_price_status_thresholds_are_deterministic(self):
        product_id = self._product()
        self._regular_history(product_id, 1.0)
        integrity = PriceIntegrityService(self.repository)

        self.assertEqual(integrity.assess(product_id, 0.80, observed_at=self.now).primary_status, EXCEPTIONAL_DEAL)
        self.assertEqual(integrity.assess(product_id, 0.95, observed_at=self.now).primary_status, GOOD_DEAL)
        self.assertEqual(integrity.assess(product_id, 1.05, observed_at=self.now).primary_status, NORMAL_PRICE)
        self.assertEqual(integrity.assess(product_id, 1.06, observed_at=self.now).primary_status, EXPENSIVE)
        self.assertEqual(integrity.assess(product_id, 1.16, observed_at=self.now).primary_status, VERY_EXPENSIVE)

    def test_offer_card_cache_keeps_different_prices_separate(self):
        product_id = self._product("Chicken")
        self._regular_history(product_id, 5.0)
        first = Offer(
            store_id="etc", store_name="ETC", raw_name="Chicken", normalized_name="chicken",
            brand=None, quantity=1000, unit="g", normal_price=None, offer_price=6.99,
            unit_price=6.99, discount_percent=None, valid_from=None, valid_until=None,
            category="MEAT", source_url="https://example.test/a", image_url=None, scraped_at=self.now,
        )
        second = Offer(
            store_id="etc", store_name="ETC", raw_name="Chicken", normalized_name="chicken",
            brand=None, quantity=1000, unit="g", normal_price=None, offer_price=3.99,
            unit_price=3.99, discount_percent=None, valid_from=None, valid_until=None,
            category="MEAT", source_url="https://example.test/b", image_url=None, scraped_at=self.now,
        )
        self.repository.insert_offer(first)
        self.repository.insert_offer(second)
        card = OfferCardMixin()
        card.app = type("App", (), {"repository": self.repository})()

        first_assessment = card._offer_context(first)[2]
        second_assessment = card._offer_context(second)[2]

        self.assertEqual(first_assessment.current_price, 6.99)
        self.assertEqual(second_assessment.current_price, 3.99)
        self.assertEqual(len(card._offer_context_cache), 2)

    def test_claim_mismatch_and_pre_promotion_increase_are_flags(self):
        product_id = self._product()
        self._regular_history(product_id, 1.0)
        self._price(product_id, 1.30, 10)
        event = PromotionEvent(
            canonical_product_id=product_id,
            promo_price=1.15,
            observed_at=self.now,
            advertised_reference_price=2.00,
            advertised_discount_percent=20.0,
            valid_from=self.now.date(),
            valid_until=(self.now + timedelta(days=4)).date(),
            source_type="FLYER",
        )

        assessment = PriceIntegrityService(self.repository).assess(
            product_id, 1.15, promotion=event, observed_at=self.now
        )

        self.assertIn(ADVERTISED_DISCOUNT_MISMATCH, assessment.flags)
        self.assertIn(RECENT_PRICE_INCREASE, assessment.flags)
        self.assertIn(PRICE_INCREASE_BEFORE_PROMOTION, assessment.flags)

    def test_same_package_price_with_smaller_quantity_is_detected(self):
        product_id = self._product()
        for days_ago in (70, 50, 30):
            self._price(product_id, 2.0, days_ago, quantity=500, unit="g")
        self._price(product_id, 2.0, 0, quantity=450, unit="g")

        changes = HistoricalPriceStatsService(self.repository).change_events(product_id, now=self.now)

        self.assertEqual(changes[-1].kind, PACKAGE_PRICE_UNCHANGED_UNIT_INCREASE)
        self.assertGreater(changes[-1].current_unit_price, changes[-1].previous_unit_price)

    def test_expired_promotion_does_not_appear_as_current(self):
        product_id = self._product()
        self.repository.record_promotion_event(
            PromotionEvent(
                canonical_product_id=product_id,
                promo_price=0.9,
                observed_at=self.now - timedelta(days=10),
                valid_until=(self.now - timedelta(days=1)).date(),
            )
        )

        self.assertEqual(self.repository.active_promotion_events(product_id, now=self.now), [])

    def test_local_merchant_can_win_without_promotion_or_chain_attribution(self):
        product_id = self._product("Tomatoes")
        self._regular_history(product_id, 2.0)
        self._merchant("local", "Local grower", 42.65)
        self._merchant("other", "Other grocery", 42.651)
        for merchant_id, price in (("local", 1.20), ("other", 2.00)):
            self.repository.record_user_price_observation(
                UserPriceObservation(
                    merchant_name=merchant_id,
                    merchant_id=merchant_id,
                    product_id=product_id,
                    raw_name="Tomatoes",
                    normalized_name="tomatoes",
                    price=price,
                    observed_at=self.now,
                )
            )
        self.repository.record_promotion_event(
            PromotionEvent(
                canonical_product_id=product_id,
                promo_price=1.20,
                observed_at=self.now,
                chain_id="etc",
                geographic_scope="CHAIN",
                valid_until=(self.now + timedelta(days=2)).date(),
            )
        )

        summaries = MerchantDealSummaryService(self.repository).summaries_for_merchants(
            ["local", "other"], now=self.now
        )
        map_rows = MapService(self.repository).viewport_merchants(
            (42.64, 21.14, 42.66, 21.16), filter_id="best_deals"
        )

        local_deal = summaries["local"].best_deals[0]
        self.assertTrue(local_deal.best_nearby)
        self.assertEqual(local_deal.assessment.primary_status, EXCEPTIONAL_DEAL)
        self.assertNotEqual(local_deal.assessment.primary_status, WEAK_PROMOTION)
        self.assertEqual([row.merchant["id"] for row in map_rows], ["local"])
