"""Merchant location and duplicate-detection services."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from ofertaks.database.repository import Repository
from ofertaks.models.merchant import Merchant
from ofertaks.routing.distance import haversine_km
from ofertaks.utils.text import comparable_text


@dataclass(slots=True)
class NearbyMerchant:
    merchant: dict
    distance_km: float


@dataclass(slots=True)
class DuplicateMerchantCandidate:
    merchant: dict
    distance_km: float
    name_similarity: float
    score: float
    reason: str


class MerchantService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def add_merchant(self, merchant: Merchant) -> str:
        return self.repository.add_merchant(merchant)

    def nearby(
        self,
        latitude: float,
        longitude: float,
        max_distance_km: float | None = None,
        limit: int = 20,
    ) -> list[NearbyMerchant]:
        matches = []
        for merchant in self.repository.list_merchants():
            distance = haversine_km(
                latitude, longitude, merchant["latitude"], merchant["longitude"]
            )
            if max_distance_km is None or distance <= max_distance_km:
                matches.append(NearbyMerchant(merchant=merchant, distance_km=distance))
        return sorted(matches, key=lambda item: item.distance_km)[:limit]

    def duplicate_candidates(
        self,
        candidate: Merchant,
        max_distance_km: float = 0.12,
        min_score: float = 0.70,
    ) -> list[DuplicateMerchantCandidate]:
        candidates: list[DuplicateMerchantCandidate] = []
        candidate_name = comparable_text(candidate.name)
        for merchant in self.repository.list_merchants():
            if merchant["id"] == candidate.id:
                continue
            distance = haversine_km(
                candidate.latitude,
                candidate.longitude,
                merchant["latitude"],
                merchant["longitude"],
            )
            if distance > max_distance_km * 3:
                continue
            existing_name = comparable_text(merchant["name"])
            name_similarity = SequenceMatcher(None, candidate_name, existing_name).ratio()
            type_score = 1.0 if merchant["merchant_type"] == candidate.merchant_type else 0.55
            distance_score = max(0.0, 1.0 - (distance / max_distance_km))
            score = round((0.45 * name_similarity) + (0.35 * distance_score) + (0.20 * type_score), 3)
            if score >= min_score:
                reason = (
                    f"{distance * 1000:.0f} m away, "
                    f"name similarity {name_similarity:.0%}, same type {type_score == 1.0}"
                )
                candidates.append(
                    DuplicateMerchantCandidate(
                        merchant=merchant,
                        distance_km=distance,
                        name_similarity=round(name_similarity, 3),
                        score=score,
                        reason=reason,
                    )
                )
        return sorted(candidates, key=lambda item: item.score, reverse=True)
