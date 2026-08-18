from unittest import TestCase

from ofertaks.parsing.price_parser import extract_prices, parse_price


class PriceParserTests(TestCase):
    def test_price_examples(self):
        examples = {
            "1.29 €": 1.29,
            "1,29€": 1.29,
            "0.99": 0.99,
            "12,90 EUR": 12.90,
            "€ 1.29": 1.29,
            "1 29": 1.29,
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                parsed = parse_price(text)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.value, expected)

    def test_extracts_multiple_prices(self):
        self.assertEqual(extract_prices("34 % 149 € 99.00 €"), [149.0, 99.0])
