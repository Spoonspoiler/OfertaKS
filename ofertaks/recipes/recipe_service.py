"""Recipe matching and additional-cost estimation."""

from __future__ import annotations

from dataclasses import dataclass

from ofertaks.database.repository import Repository
from ofertaks.models.offer import Offer
from ofertaks.models.recipe import Recipe
from ofertaks.normalization.matcher import match_score
from ofertaks.normalization.product_normalizer import normalize_product_name


@dataclass(slots=True)
class IngredientPurchase:
    ingredient: str
    offer: Offer
    confidence: float


@dataclass(slots=True)
class RecipeMatch:
    recipe_id: int
    slug: str
    title: str
    available: tuple[str, ...]
    missing_required: tuple[str, ...]
    purchases: tuple[IngredientPurchase, ...]
    additional_cost: float


class RecipeService:
    def __init__(
        self,
        repository: Repository,
        min_offer_match_score: float = 0.42,
        min_pantry_match_score: float = 0.62,
    ):
        self.repository = repository
        self.min_offer_match_score = min_offer_match_score
        self.min_pantry_match_score = min_pantry_match_score

    def save_recipe(self, recipe: Recipe) -> int:
        return self.repository.upsert_recipe(recipe)

    def match_all(self) -> list[RecipeMatch]:
        matches = [self.match_recipe(row["id"]) for row in self.repository.list_recipes()]
        return sorted(matches, key=lambda match: (len(match.missing_required), match.additional_cost))

    def match_recipe(self, recipe_id: int) -> RecipeMatch:
        recipe = self._recipe_record(recipe_id)
        ingredients = self.repository.recipe_ingredients(recipe_id)
        pantry = self.repository.list_pantry_items()
        available: list[str] = []
        missing: list[str] = []
        purchases: list[IngredientPurchase] = []

        for ingredient in ingredients:
            if self._has_in_pantry(ingredient.raw_name, pantry):
                available.append(ingredient.raw_name)
                continue
            if ingredient.required:
                missing.append(ingredient.raw_name)
            purchase = self._cheapest_purchase(ingredient.raw_name)
            if purchase:
                purchases.append(purchase)

        return RecipeMatch(
            recipe_id=recipe_id,
            slug=recipe["slug"],
            title=recipe["title"],
            available=tuple(available),
            missing_required=tuple(missing),
            purchases=tuple(purchases),
            additional_cost=round(sum(purchase.offer.offer_price for purchase in purchases), 2),
        )

    def _recipe_record(self, recipe_id: int) -> dict:
        for recipe in self.repository.list_recipes():
            if recipe["id"] == recipe_id:
                return recipe
        raise KeyError(f"Recipe not found: {recipe_id}")

    def _has_in_pantry(self, ingredient_name: str, pantry: list[dict]) -> bool:
        normalized_ingredient = normalize_product_name(ingredient_name)
        for item in pantry:
            if match_score(normalized_ingredient, item["raw_name"]) >= self.min_pantry_match_score:
                return True
        return False

    def _cheapest_purchase(self, ingredient_name: str) -> IngredientPurchase | None:
        offers = self.repository.search_offers(ingredient_name, limit=50)
        if not offers:
            offers = self.repository.list_offers(limit=500)
        candidates = [
            (offer, match_score(ingredient_name, offer.raw_name))
            for offer in offers
        ]
        candidates = [
            (offer, score)
            for offer, score in candidates
            if score >= self.min_offer_match_score
        ]
        if not candidates:
            return None
        offer, score = sorted(candidates, key=lambda pair: pair[0].offer_price)[0]
        return IngredientPurchase(ingredient=ingredient_name, offer=offer, confidence=score)
