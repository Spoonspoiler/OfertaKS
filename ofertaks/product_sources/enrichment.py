"""Apply official metadata as evidence before enriching a canonical product."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ofertaks.database.repository import Repository
from ofertaks.models.knowledge import (
    CONFIDENCE_CONFLICTED,
    CONFIDENCE_VERIFIED,
    ProductAttributeEvidence,
    ProductSource,
    ValidationTask,
)
from ofertaks.product_sources.base import OfficialProductMetadata
from ofertaks.utils.text import comparable_text


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    source_id: int
    filled_fields: tuple[str, ...]
    conflicted_fields: tuple[str, ...]


class ProductEnrichmentService:
    """Keep source conflicts visible instead of overwriting current product knowledge."""

    _ORGANIZATION_FIELDS = {
        "brand": "BRAND",
        "manufacturer": "MANUFACTURER",
        "producer": "PRODUCER",
        "distributor": "DISTRIBUTOR",
    }
    _PRODUCT_FIELDS = (
        "product_family",
        "variant",
        "quantity",
        "unit",
        "packaging",
        "flavor",
        "origin_country",
        "origin_region",
        "barcode_gtin",
        "official_image_url",
    )

    def __init__(self, repository: Repository):
        self.repository = repository

    def enrich(self, product_id: int, metadata: OfficialProductMetadata) -> EnrichmentResult:
        source_id = self.repository.upsert_product_source(
            ProductSource(
                id=None,
                product_id=product_id,
                source_type=metadata.source_type,
                publisher=metadata.publisher,
                url=metadata.url,
                retrieved_at=metadata.retrieved_at,
                last_checked_at=metadata.retrieved_at,
                confidence=1.0,
                raw_metadata=metadata.raw_metadata,
            )
        )
        product = self.repository.get_canonical_product(product_id)
        if not product:
            raise ValueError("Canonical product does not exist")
        values: dict[str, Any] = {
            "canonical_name": metadata.canonical_name,
            "brand": metadata.brand,
            "manufacturer": metadata.manufacturer,
            "producer": metadata.producer,
            "distributor": metadata.distributor,
            **{field: getattr(metadata, field) for field in self._PRODUCT_FIELDS},
        }
        filled: list[str] = []
        conflicts: list[str] = []
        for field_name, value in values.items():
            if value in {None, ""}:
                continue
            existing_key = f"{field_name}_name" if field_name in self._ORGANIZATION_FIELDS else field_name
            existing = product.get(existing_key)
            conflict = existing not in {None, ""} and comparable_text(str(existing)) != comparable_text(str(value))
            state = CONFIDENCE_CONFLICTED if conflict else CONFIDENCE_VERIFIED
            self.repository.add_product_attribute_evidence(
                ProductAttributeEvidence(
                    id=None,
                    product_id=product_id,
                    field_name=field_name,
                    value=str(value),
                    source_id=source_id,
                    source_type=metadata.source_type,
                    confidence=1.0,
                    confidence_state=state,
                    created_at=datetime.now(UTC),
                )
            )
            if conflict:
                conflicts.append(field_name)
                self.repository.create_validation_task(
                    ValidationTask(
                        id=None,
                        task_type="CONFIRM_PRODUCT_MATCH",
                        created_at=datetime.now(UTC),
                        candidate_product_id=product_id,
                        payload={"field": field_name, "current": existing, "proposed": value},
                    )
                )
            elif existing in {None, ""}:
                if field_name in self._ORGANIZATION_FIELDS:
                    if self.repository.set_product_organization_if_empty(product_id, self._ORGANIZATION_FIELDS[field_name], str(value)):
                        filled.append(field_name)
                elif field_name != "canonical_name":
                    if field_name == "official_image_url":
                        changed = self.repository.set_product_fields_if_empty(
                            product_id, {"official_image_url": value, "official_product_url": metadata.url}
                        )
                    else:
                        changed = self.repository.set_product_fields_if_empty(product_id, {field_name: value})
                    filled.extend(changed)
        return EnrichmentResult(source_id, tuple(dict.fromkeys(filled)), tuple(conflicts))
