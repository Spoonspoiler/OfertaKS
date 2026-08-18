from unittest import TestCase

from ofertaks.parsing.unit_parser import calculate_unit_price, parse_quantity


class UnitParserTests(TestCase):
    def test_unit_examples(self):
        examples = {
            "1.5L": (1500, "ml"),
            "1500ml": (1500, "ml"),
            "500 g": (500, "g"),
            "1kg": (1000, "g"),
            "6x330ml": (1980, "ml"),
            "10 pcs": (10, "piece"),
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                parsed = parse_quantity(text)
                self.assertIsNotNone(parsed)
                self.assertEqual((parsed.quantity, parsed.unit), expected)

    def test_unit_price(self):
        self.assertEqual(calculate_unit_price(1.29, 1500, "ml"), 0.86)
