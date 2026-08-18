"""Freshness, quality, and origin reasoning for community observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import exp
from statistics import mean

from ofertaks.models.community import OriginObservation, QualityObservation
from ofertaks.utils.categories import DAIRY, FRUIT_VEGETABLE, MEAT

FRESHNESS_THRESHOLDS_HOURS = {
    FRUIT_VEGETABLE: (48, 96),
    MEAT: (48, 120),
    DAIRY: (72, 168),
}
DEFAULT_THRESHOLDS_HOURS = (168, 336)


@dataclass(slots=True)
class FreshnessState:
    state: str
    age_hours: float
    message: str
    stale: bool


@dataclass(slots=True)
class QualityAggregate:
    sample_size: int
    overall: float | None
    taste: float | None
    freshness: float | None
    appearance: float | None
    value: float | None
    enough_data: bool


@dataclass(slots=True)
class OriginSummary:
    country: str | None
    region: str | None
    producer: str | None
    source: str | None
    confidence: float
    explanation: str


def freshness_state(
    observed_at: datetime,
    category: str | None = None,
    now: datetime | None = None,
) -> FreshnessState:
    now = now or datetime.now(UTC)
    observed = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=UTC)
    age_hours = max(0.0, (now - observed).total_seconds() / 3600)
    fresh_limit, stale_limit = FRESHNESS_THRESHOLDS_HOURS.get(
        category or "", DEFAULT_THRESHOLDS_HOURS
    )
    if age_hours <= fresh_limit:
        state = "fresh"
        message = f"observed {age_hours:.0f} hours ago"
    elif age_hours <= stale_limit:
        state = "aging"
        message = f"observed {age_hours:.0f} hours ago; verify if possible"
    else:
        state = "stale"
        message = f"observed {age_hours:.0f} hours ago; price may be outdated"
    return FreshnessState(state, round(age_hours, 2), message, state == "stale")


def aggregate_quality(
    observations: list[QualityObservation],
    now: datetime | None = None,
    min_samples: int = 2,
) -> QualityAggregate:
    if not observations:
        return QualityAggregate(0, None, None, None, None, None, False)
    now = now or datetime.now(UTC)

    def weight(observation: QualityObservation) -> float:
        observed = (
            observation.observed_at
            if observation.observed_at.tzinfo
            else observation.observed_at.replace(tzinfo=UTC)
        )
        age_days = max(0.0, (now - observed).total_seconds() / 86400)
        recency = exp(-age_days / 14)
        confirmations = 1 + min(observation.confirmation_count, 5) * 0.12
        return max(0.05, recency * observation.confidence * confirmations)

    def weighted_average(field: str) -> float | None:
        values = []
        weights = []
        for observation in observations:
            value = getattr(observation, field)
            if value is None:
                continue
            values.append(float(value))
            weights.append(weight(observation))
        if not values:
            return None
        return round(sum(value * weight for value, weight in zip(values, weights)) / sum(weights), 2)

    taste = weighted_average("taste_score")
    freshness = weighted_average("freshness_score")
    appearance = weighted_average("appearance_score")
    value = weighted_average("value_score")
    score_parts = [score for score in (taste, freshness, appearance, value) if score is not None]
    overall = round(mean(score_parts), 2) if score_parts else None
    return QualityAggregate(
        sample_size=len(observations),
        overall=overall,
        taste=taste,
        freshness=freshness,
        appearance=appearance,
        value=value,
        enough_data=len(observations) >= min_samples and overall is not None,
    )


def summarize_origin(observations: list[OriginObservation]) -> OriginSummary:
    if not observations:
        return OriginSummary(None, None, None, None, 0.0, "Origin unknown")
    ranked = sorted(
        observations,
        key=lambda item: (item.confidence, item.observed_at),
        reverse=True,
    )
    best = ranked[0]
    if best.source in {"STORE_LABEL", "PRODUCT_PACKAGING", "OFFICIAL_DATA", "MERCHANT"}:
        explanation = f"Verified from {best.source.lower().replace('_', ' ')}"
    elif best.source == "USER_OBSERVATION":
        explanation = "Reported by community observation"
    else:
        explanation = "Origin evidence is weak"
    return OriginSummary(
        country=best.country,
        region=best.region,
        producer=best.producer,
        source=best.source,
        confidence=round(best.confidence, 2),
        explanation=explanation,
    )
