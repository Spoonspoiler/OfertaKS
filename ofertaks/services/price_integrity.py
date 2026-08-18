"""Consumer-first price history, promotion integrity, and unit-price analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean, median
from typing import Iterable

from ofertaks.database.repository import Repository
from ofertaks.models.pricing import (
    ADVERTISED_DISCOUNT_MISMATCH,
    BEST_NEARBY_PRICE,
    CLEARANCE,
    EXCEPTIONAL_DEAL,
    EXPENSIVE,
    GOOD_DEAL,
    INSUFFICIENT_HISTORY,
    NORMAL_PRICE,
    PACKAGE_PRICE_UNCHANGED_UNIT_INCREASE,
    PRICE_INCREASE_BEFORE_PROMOTION,
    PROMOTION,
    RECENT_PRICE_INCREASE,
    VERY_EXPENSIVE,
    WEAK_PROMOTION,
    PriceAssessment,
    PriceChangeEvent,
    PromotionEvent,
)
from ofertaks.parsing.unit_parser import calculate_unit_price


@dataclass(frozen=True, slots=True)
class PriceIntegrityConfig:
    min_history_observations: int = 3
    stable_window_days: int = 90
    recent_increase_window_days: int = 30
    promotion_followup_days: int = 30
    minimum_meaningful_increase_percent: float = 8.0
    exceptional_threshold_percent: float = -20.0
    good_threshold_percent: float = -5.0
    expensive_threshold_percent: float = 5.0
    very_expensive_threshold_percent: float = 15.0
    advertised_rounding_tolerance_percent: float = 1.5


@dataclass(frozen=True, slots=True)
class HistoricalPriceStatistics:
    observation_count: int
    first_observation_at: datetime | None
    last_observation_at: datetime | None
    history_span_days: int
    latest_price: float | None
    previous_price: float | None
    median_30d: float | None
    median_90d: float | None
    median_365d: float | None
    median_all_time: float | None
    average_30d: float | None
    average_90d: float | None
    minimum_30d: float | None
    minimum_90d: float | None
    minimum_365d: float | None
    maximum_30d: float | None
    maximum_90d: float | None
    maximum_365d: float | None
    all_time_minimum: float | None
    all_time_maximum: float | None
    stable_reference_price: float | None
    unit_observation_count: int
    median_unit_price_90d: float | None
    stable_unit_reference_price: float | None

    @property
    def reference_confidence(self) -> str:
        if self.observation_count < 3:
            return "INSUFFICIENT"
        if self.observation_count >= 6 and self.history_span_days >= 60:
            return "STRONG"
        if self.history_span_days >= 20:
            return "MODERATE"
        return "WEAK"


class HistoricalPriceStatsService:
    """Deterministic exact-product statistics. Medians are the primary reference."""

    def __init__(self, repository: Repository, config: PriceIntegrityConfig | None = None):
        self.repository = repository
        self.config = config or PriceIntegrityConfig()

    def statistics(
        self,
        product_id: int,
        *,
        merchant_id: str | None = None,
        chain_id: str | None = None,
        now: datetime | None = None,
    ) -> HistoricalPriceStatistics:
        now = now or datetime.now(UTC)
        rows = self.repository.price_timeline(product_id, merchant_id=merchant_id, chain_id=chain_id)
        entries = [
            (float(row["price"]), self._as_datetime(row["observed_at"]), row)
            for row in rows
            if row.get("price") is not None
        ]
        entries.sort(key=lambda item: item[1])
        values = [price for price, _observed, _row in entries]
        first = entries[0][1] if entries else None
        last = entries[-1][1] if entries else None
        span = max(0, (last.date() - first.date()).days) if first and last else 0

        def window(days: int) -> list[float]:
            cutoff = now - timedelta(days=days)
            return [price for price, observed, _row in entries if cutoff <= observed <= now]

        def median_for(items: list[float]) -> float | None:
            return round(float(median(items)), 4) if items else None

        def average_for(items: list[float]) -> float | None:
            return round(float(mean(items)), 4) if items else None

        def minimum_for(items: list[float]) -> float | None:
            return min(items) if items else None

        def maximum_for(items: list[float]) -> float | None:
            return max(items) if items else None

        values_30, values_90, values_365 = window(30), window(90), window(365)
        stable_cutoff = now - timedelta(days=self.config.stable_window_days)
        stable_values = [
            price
            for price, observed, row in entries
            if stable_cutoff <= observed <= now
            and row.get("observation_context") not in {PROMOTION, CLEARANCE}
        ]
        unit_entries = [
            (self._unit_price(row), observed, row)
            for _price, observed, row in entries
            if self._unit_price(row) is not None
        ]
        unit_values_90 = [
            float(value)
            for value, observed, _row in unit_entries
            if value is not None and now - timedelta(days=90) <= observed <= now
        ]
        stable_unit_values = [
            float(value)
            for value, observed, row in unit_entries
            if value is not None
            and stable_cutoff <= observed <= now
            and row.get("observation_context") not in {PROMOTION, CLEARANCE}
        ]
        return HistoricalPriceStatistics(
            observation_count=len(entries),
            first_observation_at=first,
            last_observation_at=last,
            history_span_days=span,
            latest_price=values[-1] if values else None,
            previous_price=values[-2] if len(values) >= 2 else None,
            median_30d=median_for(values_30),
            median_90d=median_for(values_90),
            median_365d=median_for(values_365),
            median_all_time=median_for(values),
            average_30d=average_for(values_30),
            average_90d=average_for(values_90),
            minimum_30d=minimum_for(values_30),
            minimum_90d=minimum_for(values_90),
            minimum_365d=minimum_for(values_365),
            maximum_30d=maximum_for(values_30),
            maximum_90d=maximum_for(values_90),
            maximum_365d=maximum_for(values_365),
            all_time_minimum=minimum_for(values),
            all_time_maximum=maximum_for(values),
            stable_reference_price=median_for(stable_values) if len(stable_values) >= self.config.min_history_observations else None,
            unit_observation_count=len(unit_entries),
            median_unit_price_90d=median_for(unit_values_90),
            stable_unit_reference_price=(
                median_for(stable_unit_values)
                if len(stable_unit_values) >= self.config.min_history_observations
                else None
            ),
        )

    def change_events(self, product_id: int, *, now: datetime | None = None) -> list[PriceChangeEvent]:
        rows = self.repository.price_timeline(product_id)
        entries = sorted(
            [(float(row["price"]), self._as_datetime(row["observed_at"]), row) for row in rows if row.get("price") is not None],
            key=lambda item: item[1],
        )
        events: list[PriceChangeEvent] = []
        for (previous, _previous_at, previous_row), (current, observed_at, row) in zip(entries, entries[1:]):
            if previous <= 0:
                continue
            change = round((current - previous) / previous * 100, 2)
            previous_unit, current_unit = self._unit_price(previous_row), self._unit_price(row)
            if abs(current - previous) <= 0.001 and previous_unit and current_unit and current_unit > previous_unit * 1.01:
                kind = PACKAGE_PRICE_UNCHANGED_UNIT_INCREASE
            elif abs(change) < 1:
                kind = "STABLE"
            else:
                kind = "INCREASE" if change > 0 else "DECREASE"
            events.append(
                PriceChangeEvent(
                    observed_at=observed_at,
                    previous_price=previous,
                    current_price=current,
                    change_percent=change,
                    kind=kind,
                    previous_unit_price=previous_unit,
                    current_unit_price=current_unit,
                )
            )
        return events

    @staticmethod
    def _as_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    @staticmethod
    def _unit_price(row: dict) -> float | None:
        if row.get("unit_price") is not None:
            return float(row["unit_price"])
        return calculate_unit_price(float(row["price"]), row.get("quantity"), row.get("unit"))


class PriceIntegrityService:
    """Evaluate evidence independently from merchant advertising or commercial status."""

    def __init__(self, repository: Repository, config: PriceIntegrityConfig | None = None):
        self.repository = repository
        self.config = config or PriceIntegrityConfig()
        self.statistics_service = HistoricalPriceStatsService(repository, self.config)

    def assess(
        self,
        product_id: int,
        current_price: float,
        *,
        current_unit_price: float | None = None,
        quantity: float | None = None,
        unit: str | None = None,
        promotion: PromotionEvent | dict | None = None,
        observed_at: datetime | None = None,
        merchant_id: str | None = None,
        chain_id: str | None = None,
    ) -> PriceAssessment:
        now = observed_at or datetime.now(UTC)
        stats = self.statistics_service.statistics(product_id, now=now)
        current_unit_price = current_unit_price or calculate_unit_price(current_price, quantity, unit)
        use_unit = current_unit_price is not None and stats.unit_observation_count >= self.config.min_history_observations
        reference = (
            stats.stable_unit_reference_price or stats.median_unit_price_90d
            if use_unit
            else stats.stable_reference_price or stats.median_90d or stats.median_365d or stats.median_all_time
        )
        current_value = current_unit_price if use_unit else current_price
        if use_unit:
            reference_type = (
                "stable_unit_price"
                if stats.stable_unit_reference_price
                else "unit_price_90d_median"
            )
        elif stats.stable_reference_price:
            reference_type = "stable_price"
        elif stats.median_90d is not None:
            reference_type = "price_90d_median"
        elif stats.median_365d is not None:
            reference_type = "price_365d_median"
        else:
            reference_type = "price_all_time_median"
        promotion_values = self._promotion_values(promotion)
        advertised_discount = promotion_values["advertised_discount_percent"]
        flags: list[str] = []
        if stats.observation_count < self.config.min_history_observations or reference is None or reference <= 0:
            return PriceAssessment(
                primary_status=INSUFFICIENT_HISTORY,
                flags=tuple(self._promotion_claim_flags(current_price, promotion_values)),
                current_price=current_price,
                current_unit_price=current_unit_price,
                reference_price=None,
                reference_type=None,
                difference_amount=None,
                difference_percent=None,
                advertised_discount_percent=advertised_discount,
                observed_discount_vs_reference_percent=None,
                history_observation_count=stats.observation_count,
                history_span_days=stats.history_span_days,
                reference_confidence=stats.reference_confidence,
                explanation_key="price_integrity_insufficient_history",
                ranking_score=0.0,
                stable_reference_price=stats.stable_reference_price,
                previous_price=stats.previous_price,
            )
        difference_amount = round(current_value - reference, 4)
        difference_percent = round(difference_amount / reference * 100, 1)
        observed_discount = round((reference - current_value) / reference * 100, 1)
        if difference_percent <= self.config.exceptional_threshold_percent:
            primary = EXCEPTIONAL_DEAL
            explanation = "price_integrity_exceptional"
        elif difference_percent <= self.config.good_threshold_percent:
            primary = GOOD_DEAL
            explanation = "price_integrity_good"
        elif difference_percent > self.config.very_expensive_threshold_percent:
            primary = VERY_EXPENSIVE
            explanation = "price_integrity_very_expensive"
        elif difference_percent > self.config.expensive_threshold_percent:
            primary = EXPENSIVE
            explanation = "price_integrity_expensive"
        else:
            primary = NORMAL_PRICE
            explanation = "price_integrity_normal"
        flags.extend(self._promotion_claim_flags(current_price, promotion_values))
        is_promotion = promotion is not None
        if is_promotion and primary in {NORMAL_PRICE, EXPENSIVE, VERY_EXPENSIVE}:
            primary, explanation = WEAK_PROMOTION, "price_integrity_weak_promotion"
        recent_flags = self._recent_increase_flags(product_id, current_price, now, is_promotion, stats)
        flags.extend(recent_flags)
        changes = self.statistics_service.change_events(product_id)
        if changes and changes[-1].kind == PACKAGE_PRICE_UNCHANGED_UNIT_INCREASE:
            flags.append(PACKAGE_PRICE_UNCHANGED_UNIT_INCREASE)
        ranking = round(max(-100.0, min(100.0, -difference_percent * 3.0)), 1)
        return PriceAssessment(
            primary_status=primary,
            flags=tuple(dict.fromkeys(flags)),
            current_price=current_price,
            current_unit_price=current_unit_price,
            reference_price=round(reference, 4),
            reference_type=reference_type,
            difference_amount=difference_amount,
            difference_percent=difference_percent,
            advertised_discount_percent=advertised_discount,
            observed_discount_vs_reference_percent=observed_discount,
            history_observation_count=stats.observation_count,
            history_span_days=stats.history_span_days,
            reference_confidence=stats.reference_confidence,
            explanation_key=explanation,
            ranking_score=ranking,
            stable_reference_price=stats.stable_reference_price,
            previous_price=stats.previous_price,
        )

    def best_nearby(
        self,
        merchant_id: str,
        product_id: int,
        observations: Iterable[dict],
    ) -> bool:
        """Compare only current exact-product merchant evidence; no partner fields participate."""

        candidates = [row for row in observations if int(row["product_id"]) == product_id and row.get("price") is not None]
        if len(candidates) < 2:
            return False
        uses_unit_price = all(self._current_unit_value(row) is not None for row in candidates)
        values = [self._current_unit_value(row) if uses_unit_price else float(row["price"]) for row in candidates]
        mine = next((value for row, value in zip(candidates, values) if row["merchant_id"] == merchant_id), None)
        return mine is not None and mine <= min(values)

    def _recent_increase_flags(
        self,
        product_id: int,
        current_price: float,
        now: datetime,
        is_promotion: bool,
        stats: HistoricalPriceStatistics,
    ) -> list[str]:
        if not stats.stable_reference_price or stats.stable_reference_price <= 0:
            return []
        rows = self.repository.price_timeline(product_id)
        cutoff = now - timedelta(days=self.config.recent_increase_window_days)
        recent_regular = [
            float(row["price"])
            for row in rows
            if row.get("price") is not None
            and HistoricalPriceStatsService._as_datetime(row["observed_at"]) >= cutoff
            and HistoricalPriceStatsService._as_datetime(row["observed_at"]) <= now
            and row.get("observation_context") not in {PROMOTION, CLEARANCE}
        ]
        if not recent_regular:
            return []
        recent_max = max(recent_regular)
        increase = (recent_max - stats.stable_reference_price) / stats.stable_reference_price * 100
        if increase < self.config.minimum_meaningful_increase_percent:
            return []
        flags = [RECENT_PRICE_INCREASE]
        if is_promotion and current_price > stats.stable_reference_price:
            flags.append(PRICE_INCREASE_BEFORE_PROMOTION)
        return flags

    def _promotion_claim_flags(self, current_price: float, promotion: dict[str, float | None]) -> list[str]:
        reference, claimed = promotion["advertised_reference_price"], promotion["advertised_discount_percent"]
        if not reference or claimed is None or reference <= 0:
            return []
        arithmetic = (reference - current_price) / reference * 100
        if abs(arithmetic - claimed) > self.config.advertised_rounding_tolerance_percent:
            return [ADVERTISED_DISCOUNT_MISMATCH]
        return []

    @staticmethod
    def _promotion_values(event: PromotionEvent | dict | None) -> dict[str, float | None]:
        if event is None:
            return {"advertised_reference_price": None, "advertised_discount_percent": None}
        if isinstance(event, PromotionEvent):
            return {
                "advertised_reference_price": event.advertised_reference_price,
                "advertised_discount_percent": event.advertised_discount_percent,
            }
        return {
            "advertised_reference_price": event.get("advertised_reference_price"),
            "advertised_discount_percent": event.get("advertised_discount_percent"),
        }

    @staticmethod
    def _current_unit_value(row: dict) -> float | None:
        if row.get("unit_price") is not None:
            return float(row["unit_price"])
        return calculate_unit_price(float(row["price"]), row.get("quantity"), row.get("unit"))
