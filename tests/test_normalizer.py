from unittest import TestCase

from ofertaks.normalization.product_normalizer import normalize_product_name


class ProductNormalizerTests(TestCase):
    def test_coca_cola_variants_normalize(self):
        variants = [
            "Coca Cola 1.5L",
            "Coca-Cola Original PET 1500ml",
            "COCA COLA 1,5 L",
            "Coca Cola Original 1.5 litra",
        ]
        normalized = [normalize_product_name(value) for value in variants]
        self.assertTrue(all(item.brand == "Coca-Cola" for item in normalized))
        self.assertTrue(all(item.quantity == 1500 for item in normalized))
        self.assertTrue(all(item.unit == "ml" for item in normalized))
        self.assertEqual(len({item.normalized_name for item in normalized}), 1)
