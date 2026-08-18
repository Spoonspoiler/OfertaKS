from pathlib import Path
from unittest import TestCase

from ofertaks.parsing.html_utils import make_soup
from ofertaks.scrapers.etc import ETCScraper
from ofertaks.scrapers.interex import InterexScraper


FIXTURES = Path(__file__).parent / "fixtures"


class ScraperTests(TestCase):
    def test_etc_fixture(self):
        soup = make_soup((FIXTURES / "etc_offer.html").read_text(encoding="utf-8"))
        offers = ETCScraper(client=None).parse_offer_page(soup, "https://etc-ks.com/test")
        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[0].raw_name, "Coca-Cola Original PET 1500ml")
        self.assertEqual(offers[0].offer_price, 1.29)
        self.assertEqual(offers[0].normal_price, 1.69)

    def test_interex_index_fixture(self):
        soup = make_soup((FIXTURES / "interex_index.html").read_text(encoding="utf-8"))
        flyers = InterexScraper(client=None).parse_flyer_index(
            soup, "https://fletushka.interex-rks.com/"
        )
        self.assertEqual(len(flyers), 1)
        self.assertEqual(flyers[0].pdf_url, "https://fletushka.interex-rks.com/uploads/fletushka.pdf")
