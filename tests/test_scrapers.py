import json
from pathlib import Path
from unittest import TestCase

from ofertaks.parsing.html_utils import make_soup
from ofertaks.scrapers.etc import ETCScraper
from ofertaks.scrapers.interex import InterexScraper
from ofertaks.scrapers.viva import VivaFreshScraper
from ofertaks.utils.categories import DAIRY, FRUIT_VEGETABLE


FIXTURES = Path(__file__).parent / "fixtures"


class _CatalogResponse:
    def __init__(self, payload):
        self.text = json.dumps(payload)


class _VivaCatalogClient:
    def __init__(self):
        self.post_payloads = []

    def get(self, url):
        if "category%2Flevel1" in url:
            return _CatalogResponse(
                {
                    "success": True,
                    "data": [
                        {"id": 1, "name": "Pemë dhe Perime", "active": 1},
                        {"id": 4, "name": "Bulmet", "active": 1},
                    ],
                }
            )
        if "subcategory%2Flevel2" in url:
            return _CatalogResponse(
                {
                    "success": True,
                    "data": [
                        {"id": 10, "name": "Fruta të freskëta", "categories_lvl_1_id": 1, "active": 1},
                        {"id": 20, "name": "Qumësht", "categories_lvl_1_id": 4, "active": 1},
                    ],
                }
            )
        raise AssertionError(f"Unexpected GET: {url}")

    def post_json(self, url, payload, **kwargs):
        self.post_payloads.append(payload)
        level2_id = payload["level2_ids"][0]
        page = payload["page"]
        if level2_id == 10 and page == 1:
            products = [
                {
                    "id": 1,
                    "name": "Banane kg/ (PLU: 205)",
                    "final_price": "0.99",
                    "base_price": "1.59",
                    "unit_of_measure": "KG",
                    "stock": "229.58200",
                    "out_of_stock": False,
                    "images": [{"url": "https://cdn.example/banana.jpg"}],
                },
                {
                    "id": 2,
                    "name": "Pa stok",
                    "final_price": "3.00",
                    "out_of_stock": True,
                },
            ]
            return _CatalogResponse({"data": {"10": products}, "meta": {"last_page": 2}})
        if level2_id == 10 and page == 2:
            return _CatalogResponse(
                {
                    "data": {"10": [{"id": 1, "name": "Banane kg", "final_price": "0.99"}]},
                    "meta": {"last_page": 2},
                }
            )
        if level2_id == 20 and page == 1:
            return _CatalogResponse(
                {
                    "data": {
                        "20": [
                            {
                                "id": 3,
                                "name": "Qumësht Vita 1L",
                                "final_price": "1.19",
                                "base_price": "1.19",
                                "unit_of_measure": "COP",
                                "stock": "10",
                                "out_of_stock": False,
                            }
                        ]
                    },
                    "meta": {"last_page": 1},
                }
            )
        raise AssertionError(f"Unexpected POST: {url}, {payload}")


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

    def test_viva_public_catalog_paginates_and_deduplicates(self):
        client = _VivaCatalogClient()
        scraper = VivaFreshScraper(client=client)
        scraper.catalog_level2_batch_size = 1
        result = scraper.fetch_and_parse()

        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.offers), 2)
        self.assertEqual(result.metadata["pages_fetched"], 3)
        self.assertEqual(result.metadata["out_of_stock_skipped"], 1)
        self.assertEqual([payload["page"] for payload in client.post_payloads], [1, 2, 1])

        banana, milk = result.offers
        self.assertEqual(banana.category, FRUIT_VEGETABLE)
        self.assertEqual(banana.offer_price, 0.99)
        self.assertEqual(banana.normal_price, 1.59)
        self.assertEqual(banana.unit_price, 0.99)
        self.assertEqual(banana.image_url, "https://cdn.example/banana.jpg")
        self.assertEqual(milk.category, DAIRY)
