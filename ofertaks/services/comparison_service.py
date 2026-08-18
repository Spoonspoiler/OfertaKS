"""Deal scoring and offer comparison."""

from __future__ import annotations

from dataclasses import dataclass

from ofertaks.models.offer import Offer
from ofertaks.services.history_service import HistoryStats


@dataclass(slots=True)
class DealScore:
    score: float
    label_key: str
    reasons: tuple[str, ...]


def score_offer(offer: Offer, history: HistoryStats | None = None) -> DealScore:
    score = 0.0
    reasons: list[str] = []

    if offer.normal_price and offer.normal_price > offer.offer_price:
        advertised = (offer.normal_price - offer.offer_price) / offer.normal_price * 100
        score += min(0.35, advertised / 100)
        reasons.append(f"Advertised -{advertised:.0f}%")
    elif offer.discount_percent:
        score += min(0.25, offer.discount_percent / 120)
        reasons.append(f"Advertised -{offer.discount_percent:.0f}%")

    if history and history.enough_history and history.average:
        delta = (history.average - offer.offer_price) / history.average * 100
        if delta > 0:
            score += min(0.35, delta / 80)
            reasons.append(f"{delta:.0f}% below recent average")
        else:
            reasons.append(f"{abs(delta):.0f}% above recent average")
        if history.minimum is not None:
            if offer.offer_price <= history.minimum:
                score += 0.20
                reasons.append("Lowest observed price")
            elif history.minimum > 0:
                near_min = (offer.offer_price - history.minimum) / history.minimum * 100
                if near_min <= 5:
                    score += 0.12
                    reasons.append("Near historical minimum")
    else:
        reasons.append("Not enough history")

    score = round(min(score, 1.0), 3)
    if score >= 0.72:
        label = "excellent_deal"
    elif score >= 0.45:
        label = "good_deal"
    elif score >= 0.22:
        label = "average_deal"
    else:
        label = "weak_deal"
    return DealScore(score=score, label_key=label, reasons=tuple(reasons))


def cheapest_by_store(offers: list[Offer]) -> dict[str, Offer]:
    best: dict[str, Offer] = {}
    for offer in offers:
        current = best.get(offer.store_id)
        if current is None or offer.offer_price < current.offer_price:
            best[offer.store_id] = offer
    return best
