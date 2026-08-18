"""Local-first ingestion for historical documents and raw price evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Iterable, Protocol

from ofertaks.database.repository import Repository
from ofertaks.models.knowledge import HistoricalSourceDocument, RawObservation, ValidationTask
from ofertaks.normalization.product_normalizer import normalize_product_name

HISTORICAL_ARCHIVE_START = date(2025, 1, 1)


class HistoricalWebProvider(Protocol):
    """A bounded archive-discovery adapter, such as a future Wayback provider."""

    def discover(self, domain: str, start_date: date, end_date: date) -> Iterable[HistoricalSourceDocument]: ...


class HistoricalArchiveService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def discover(
        self,
        provider: HistoricalWebProvider,
        domain: str,
        end_date: date,
        start_date: date = HISTORICAL_ARCHIVE_START,
    ) -> list[int]:
        """Persist only provider-discovered metadata; parsing can happen later."""

        if end_date < start_date:
            raise ValueError("Historical discovery end date precedes the start date")
        return [
            self.repository.upsert_historical_source_document(document)
            for document in provider.discover(domain, start_date, end_date)
        ]

    def ingest_raw_observation(self, observation: RawObservation) -> int:
        """Append evidence and use only an existing confident alias for automatic linkage."""

        normalized = normalize_product_name(observation.raw_name)
        alias = self.repository.find_product_alias(
            observation.raw_name,
            normalized.normalized_name,
            merchant_id=observation.merchant_id,
            chain_id=observation.chain_id,
            store_id=observation.store_id,
        )
        if alias and alias["matching_status"] in {"CONFIRMED", "AUTO_MATCHED"}:
            observation = replace(
                observation,
                canonical_product_id=alias["product_id"],
                matching_status=alias["matching_status"],
                matching_confidence=float(alias["matching_confidence"]),
            )
        observation_id = self.repository.record_raw_observation(observation)
        if observation.canonical_product_id is None:
            self.repository.create_validation_task(
                ValidationTask(
                    id=None,
                    task_type="CONFIRM_PRODUCT_MATCH",
                    created_at=observation.created_at,
                    raw_observation_id=observation_id,
                    payload={"raw_name": observation.raw_name, "normalized_name": normalized.normalized_name},
                )
            )
        return observation_id
