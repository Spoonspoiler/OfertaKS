from unittest import TestCase

from ofertaks.normalization.matcher import match_score


class MatchingTests(TestCase):
    def test_strong_match_for_equivalent_product(self):
        score = match_score("Coca-Cola 1.5L", "COCA COLA 1500 ml")
        self.assertGreaterEqual(score, 0.82)

    def test_quantity_mismatch_reduces_score(self):
        score = match_score("Coca-Cola 500ml", "Coca-Cola 2L")
        self.assertLess(score, 0.70)
