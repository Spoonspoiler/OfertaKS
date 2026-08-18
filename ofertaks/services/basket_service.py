"""Shopping basket optimization."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from ofertaks.database.repository import Repository
from ofertaks.models.offer import Offer
from ofertaks.normalization.matcher import match_score


@dataclass(slots=True)
class BasketChoice:
    query: str
    quantity: int
    offer: Offer | None
    score: float

    @property
    def subtotal(self) -> float:
        if not self.offer:
            return 0.0
        return round(self.offer.offer_price * self.quantity, 2)


@dataclass(slots=True)
class BasketPlan:
    mode: str
    choices: tuple[BasketChoice, ...]
    total: float
    stores: tuple[str, ...]
    missing: tuple[str, ...]


class BasketService:
    def __init__(self, repository: Repository, min_score: float = 0.42):
        self.repository = repository
        self.min_score = min_score

    def _candidates(self, query: str) -> list[tuple[Offer, float]]:
        # Basket planning is a domain service rather than the food browsing UI.
        # It keeps access to the retained full catalogue for existing lists.
        candidates = self.repository.search_offers(query, limit=50, food_only=False)
        scored = [(offer, match_score(query, offer.raw_name)) for offer in candidates]
        scored = [(offer, score) for offer, score in scored if score >= self.min_score]
        return sorted(scored, key=lambda pair: (-pair[1], pair[0].offer_price))

    def cheapest_overall(self) -> BasketPlan:
        choices: list[BasketChoice] = []
        stores: set[str] = set()
        for item in self.repository.list_basket_items():
            candidates = self._candidates(item["query"])
            offer, score = candidates[0] if candidates else (None, 0.0)
            if offer:
                stores.add(offer.store_name)
            choices.append(BasketChoice(item["query"], item["quantity"], offer, score))
        return self._plan("any_store", choices, stores)

    def one_store_totals(self) -> list[BasketPlan]:
        stores = self.repository.stores(enabled_only=True)
        plans = []
        for store in stores:
            choices = []
            for item in self.repository.list_basket_items():
                candidates = [
                    pair
                    for pair in self._candidates(item["query"])
                    if pair[0].store_id == store["id"]
                ]
                offer, score = candidates[0] if candidates else (None, 0.0)
                choices.append(BasketChoice(item["query"], item["quantity"], offer, score))
            plans.append(self._plan("one_store", choices, {store["name"]}))
        return sorted(plans, key=lambda plan: (len(plan.missing), plan.total))

    def maximum_stores(self, max_count: int = 2) -> BasketPlan:
        stores = self.repository.stores(enabled_only=True)
        best: BasketPlan | None = None
        for count in range(1, min(max_count, len(stores)) + 1):
            for combo in combinations(stores, count):
                allowed = {store["id"] for store in combo}
                names = {store["name"] for store in combo}
                choices = []
                for item in self.repository.list_basket_items():
                    candidates = [
                        pair
                        for pair in self._candidates(item["query"])
                        if pair[0].store_id in allowed
                    ]
                    offer, score = candidates[0] if candidates else (None, 0.0)
                    choices.append(BasketChoice(item["query"], item["quantity"], offer, score))
                plan = self._plan("two_stores", choices, names)
                if best is None or (len(plan.missing), plan.total) < (
                    len(best.missing),
                    best.total,
                ):
                    best = plan
        return best or BasketPlan("two_stores", tuple(), 0.0, tuple(), tuple())

    def _plan(
        self, mode: str, choices: list[BasketChoice], stores: set[str]
    ) -> BasketPlan:
        total = round(sum(choice.subtotal for choice in choices), 2)
        missing = tuple(choice.query for choice in choices if choice.offer is None)
        used_stores = tuple(
            sorted({choice.offer.store_name for choice in choices if choice.offer} or stores)
        )
        return BasketPlan(mode, tuple(choices), total, used_stores, missing)
