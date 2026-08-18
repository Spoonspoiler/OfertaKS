from datetime import UTC, datetime, timedelta
from unittest import TestCase

from ofertaks.community.observations import (
    aggregate_quality,
    freshness_state,
    summarize_origin,
)
from ofertaks.models.community import OriginObservation, QualityObservation
from ofertaks.utils.categories import FRUIT_VEGETABLE


class CommunityObservationTests(TestCase):
    def test_price_freshness_depends_on_age_and_category(self):
        now = datetime(2026, 8, 18, 12, tzinfo=UTC)
        fresh = freshness_state(now - timedelta(hours=2), FRUIT_VEGETABLE, now)
        stale = freshness_state(now - timedelta(days=12), FRUIT_VEGETABLE, now)
        self.assertEqual(fresh.state, "fresh")
        self.assertTrue(stale.stale)

    def test_recent_quality_observations_outweigh_old_ones(self):
        now = datetime(2026, 8, 18, 12, tzinfo=UTC)
        aggregate = aggregate_quality(
            [
                QualityObservation(
                    product_id=1,
                    merchant_id="m1",
                    observed_at=now - timedelta(days=60),
                    taste_score=1.0,
                    confidence=1.0,
                ),
                QualityObservation(
                    product_id=1,
                    merchant_id="m1",
                    observed_at=now - timedelta(hours=3),
                    taste_score=5.0,
                    confidence=1.0,
                    confirmation_count=3,
                ),
            ],
            now=now,
        )
        self.assertTrue(aggregate.enough_data)
        self.assertGreater(aggregate.taste, 4.5)

    def test_origin_requires_evidence(self):
        self.assertEqual(summarize_origin([]).explanation, "Origin unknown")
        now = datetime(2026, 8, 18, 12, tzinfo=UTC)
        summary = summarize_origin(
            [
                OriginObservation(
                    country="Kosovo",
                    region="Rahovec",
                    source="USER_OBSERVATION",
                    confidence=0.55,
                    observed_at=now,
                )
            ]
        )
        self.assertEqual(summary.country, "Kosovo")
        self.assertIn("community", summary.explanation)
