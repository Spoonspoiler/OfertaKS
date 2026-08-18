from unittest import TestCase

from ofertaks.services.comparison_service import classify_price_status
from ofertaks.services.history_service import HistoryStats


class PriceStatusTests(TestCase):
    def setUp(self):
        self.history = HistoryStats(4, 10.0, 10.0, 8.0, 12.0, 10.0, 10.0)

    def test_thresholds_are_deterministic(self):
        cases = {
            8.0: "price_exceptional",
            9.5: "price_cheap",
            10.2: "price_normal",
            11.0: "price_expensive",
            11.6: "price_high",
        }
        for price, expected in cases.items():
            with self.subTest(price=price):
                self.assertEqual(classify_price_status(price, self.history).key, expected)

    def test_history_is_required_before_price_claims(self):
        insufficient = HistoryStats(2, 8.0, 10.0, 8.0, 12.0, None, None)
        status = classify_price_status(8.0, insufficient)
        self.assertEqual(status.key, "not_enough_history")
        self.assertEqual(status.color_key, "neutral")
