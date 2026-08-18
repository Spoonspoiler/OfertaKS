from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import TestCase

from ofertaks.community.observations import origin_display_for_offer
from ofertaks.models.community import OriginObservation


class OriginDisplayTests(TestCase):
    def test_flyer_origin_is_probable_not_verified(self):
        display = origin_display_for_offer(
            SimpleNamespace(origin_country="Kosovo", origin_region="Rahovec"), []
        )
        self.assertEqual(display.country, "Kosovo")
        self.assertEqual(display.source_key, "origin_source_flyer")
        self.assertEqual(display.confidence_key, "origin_confidence_probable")

    def test_store_label_origin_is_verified_when_confident(self):
        display = origin_display_for_offer(
            SimpleNamespace(origin_country=None, origin_region=None),
            [
                OriginObservation(
                    country="Albania",
                    region=None,
                    source="STORE_LABEL",
                    confidence=0.9,
                    observed_at=datetime.now(UTC),
                )
            ],
        )
        self.assertEqual(display.source_key, "origin_source_store_label")
        self.assertEqual(display.confidence_key, "origin_confidence_verified")

    def test_missing_origin_is_explicitly_unknown(self):
        display = origin_display_for_offer(
            SimpleNamespace(origin_country=None, origin_region=None), []
        )
        self.assertEqual(display.confidence_key, "origin_confidence_unknown")
