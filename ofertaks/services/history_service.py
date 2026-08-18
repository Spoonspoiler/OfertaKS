"""Price history calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean

from ofertaks.database.repository import Repository


@dataclass(slots=True)
class HistoryStats:
    count: int
    current: float | None
    average: float | None
    minimum: float | None
    maximum: float | None
    average_30d: float | None
    average_90d: float | None

    @property
    def enough_history(self) -> bool:
        return self.count >= 3


class HistoryService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def stats_for_product(self, product_id: int) -> HistoryStats:
        rows = self.repository.price_history(product_id)
        prices = [float(row["price"]) for row in rows]
        now = datetime.utcnow()

        def recent_average(days: int) -> float | None:
            cutoff = now - timedelta(days=days)
            recent = [
                float(row["price"])
                for row in rows
                if datetime.fromisoformat(row["observed_at"]) >= cutoff
            ]
            return round(mean(recent), 2) if recent else None

        return HistoryStats(
            count=len(prices),
            current=prices[-1] if prices else None,
            average=round(mean(prices), 2) if prices else None,
            minimum=min(prices) if prices else None,
            maximum=max(prices) if prices else None,
            average_30d=recent_average(30),
            average_90d=recent_average(90),
        )
