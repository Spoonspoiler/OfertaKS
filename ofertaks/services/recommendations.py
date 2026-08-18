"""Consumer-first merchant recommendations with explicit local preference."""

from __future__ import annotations

from dataclasses import dataclass

from ofertaks.database.repository import Repository
from ofertaks.models.merchant import INDEPENDENT_LOCAL, LOCAL_CHAIN
from ofertaks.parsing.unit_parser import calculate_unit_price


@dataclass(frozen=True, slots=True)
class MerchantRecommendation:
    merchant_id: str
    product_id: int
    price: float
    absolute_cheapest: bool
    recommended: bool
    reason: str


class ConsumerRecommendationService:
    """Recommend local exact-product evidence within a small price tolerance.

    Partner, commission, payment, and chain-size fields are deliberately absent
    from both the inputs and the ranking.
    """

    def __init__(self, repository: Repository, local_price_tolerance_percent: float = 6.0):
        self.repository = repository
        self.local_price_tolerance_percent = local_price_tolerance_percent

    def recommend(self, product_id: int) -> tuple[MerchantRecommendation, ...]:
        candidates = [
            row
            for row in self.repository.current_merchant_prices()
            if int(row["product_id"]) == product_id and row.get("price") is not None
        ]
        if not candidates:
            return ()
        merchants = {merchant["id"]: merchant for merchant in self.repository.list_merchants()}
        values = [(row, self._comparison_value(row)) for row in candidates]
        lowest = min(value for _row, value in values)
        local_limit = lowest * (1 + self.local_price_tolerance_percent / 100)
        local = [
            (row, value)
            for row, value in values
            if merchants.get(row["merchant_id"], {}).get("ownership_type") in {INDEPENDENT_LOCAL, LOCAL_CHAIN}
            and value <= local_limit
        ]
        chosen = min(local or values, key=lambda item: (item[1], item[0]["merchant_id"]))[0]["merchant_id"]
        return tuple(
            MerchantRecommendation(
                merchant_id=row["merchant_id"],
                product_id=product_id,
                price=float(row["price"]),
                absolute_cheapest=value == lowest,
                recommended=row["merchant_id"] == chosen,
                reason=(
                    "local_within_tolerance"
                    if row["merchant_id"] == chosen and local
                    else "absolute_lowest_exact_product"
                ),
            )
            for row, value in sorted(values, key=lambda item: (item[1], item[0]["merchant_id"]))
        )

    @staticmethod
    def _comparison_value(row: dict) -> float:
        return calculate_unit_price(float(row["price"]), row.get("quantity"), row.get("unit")) or float(row["price"])
