import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.offer import Offer
from ofertaks.models.recipe import Recipe, RecipeIngredient
from ofertaks.recipes.recipe_service import RecipeService


def offer(store_id, store_name, name, price):
    return Offer(
        store_id=store_id,
        store_name=store_name,
        raw_name=name,
        normalized_name=name.casefold(),
        brand=None,
        quantity=None,
        unit=None,
        normal_price=None,
        offer_price=price,
        unit_price=None,
        discount_percent=None,
        valid_from=None,
        valid_until=None,
        category="FOOD",
        source_url="https://example.test",
        image_url=None,
        scraped_at=datetime.now(UTC),
        chain_id=store_id,
    )


class RecipeTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "db.sqlite3"))
        self.repo.initialize()
        self.service = RecipeService(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pantry_recipe_match_has_no_missing_cost(self):
        for item in ["pasta", "tuna", "tomatoes"]:
            self.repo.add_pantry_item(item)
        recipe_id = self.service.save_recipe(
            Recipe(
                slug="tuna-pasta",
                title="Tuna pasta",
                cuisine="Balkans",
                servings=2,
                ingredients=(
                    RecipeIngredient("pasta", ""),
                    RecipeIngredient("tuna", ""),
                    RecipeIngredient("tomatoes", ""),
                ),
            )
        )
        match = self.service.match_recipe(recipe_id)
        self.assertEqual(match.missing_required, ())
        self.assertEqual(match.additional_cost, 0)

    def test_recipe_additional_cost_uses_current_cheapest_offers(self):
        for item in ["pasta", "tuna", "tomatoes"]:
            self.repo.add_pantry_item(item)
        self.repo.replace_current_offers(
            "viva_fresh",
            [offer("viva_fresh", "Viva Fresh", "Olives 250g", 0.99)],
        )
        self.repo.replace_current_offers(
            "etc",
            [offer("etc", "ETC", "Lemon 1 pcs", 0.39)],
        )
        recipe_id = self.service.save_recipe(
            Recipe(
                slug="tuna-pasta-plus",
                title="Tuna pasta with olives",
                cuisine="Mediterranean",
                servings=2,
                ingredients=(
                    RecipeIngredient("pasta", ""),
                    RecipeIngredient("tuna", ""),
                    RecipeIngredient("tomatoes", ""),
                    RecipeIngredient("olives", ""),
                    RecipeIngredient("lemon", ""),
                ),
            )
        )
        match = self.service.match_recipe(recipe_id)
        self.assertEqual(match.missing_required, ("olives", "lemon"))
        self.assertEqual(match.additional_cost, 1.38)
