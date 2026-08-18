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


@dataclass(slots=True)
class MerchantMatch:
    """A conservative duplicate decision; callers merge only EXACT matches."""

    confidence: str
    merchant: dict | None
    distance_km: float | None
    name_similarity: float | None
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

    def match(self, candidate: Merchant) -> MerchantMatch:
        """Classify a possible duplicate without modifying either merchant.

        An identical provenance identifier is the only source-level automatic
        merge key. Name and distance are deliberately advisory for community
        and OSM imports so nearby independent shops are never overwritten.
        """

        candidates = self.repository.list_merchants()
        for merchant in candidates:
            if merchant["id"] == candidate.id:
                continue
            if (
                candidate.source_id
                and merchant.get("source_type") == candidate.source_type
                and merchant.get("source_id") == candidate.source_id
            ):
                return MerchantMatch("EXACT", merchant, 0.0, 1.0, "same source identifier")

        candidate_name = comparable_text(candidate.name)
        best: MerchantMatch | None = None
        for merchant in candidates:
            if merchant["id"] == candidate.id:
                continue
            distance = haversine_km(
                candidate.latitude, candidate.longitude, merchant["latitude"], merchant["longitude"]
            )
            if distance > 3.0:
                continue
            similarity = SequenceMatcher(
                None, candidate_name, comparable_text(merchant["name"])
            ).ratio()
            same_chain = bool(candidate.chain_id and candidate.chain_id == merchant.get("chain_id"))
            if distance <= 0.03 and (similarity >= 0.92 or same_chain):
                confidence = "EXACT"
            elif distance <= 0.15 and ((same_chain and similarity >= 0.60) or similarity >= 0.85):
                confidence = "LIKELY"
            elif distance <= 0.40 and similarity >= 0.65:
                confidence = "POSSIBLE"
            else:
                continue
            result = MerchantMatch(
                confidence,
                merchant,
                round(distance, 4),
                round(similarity, 3),
                f"{distance * 1000:.0f} m away; name similarity {similarity:.0%}",
            )
            rank = {"EXACT": 3, "LIKELY": 2, "POSSIBLE": 1}[confidence]
            if best is None or rank > {"EXACT": 3, "LIKELY": 2, "POSSIBLE": 1}[best.confidence]:
                best = result
        return best or MerchantMatch("NO_MATCH", None, None, None, "no safe duplicate candidate")
