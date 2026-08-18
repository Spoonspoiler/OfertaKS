"""Canonical product and immutable historical-evidence domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

CONFIDENCE_UNVERIFIED = "UNVERIFIED"
CONFIDENCE_LOW = "LOW"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_VERIFIED = "VERIFIED"
CONFIDENCE_CONFLICTED = "CONFLICTED"

MATCH_UNMATCHED = "UNMATCHED"
MATCH_CANDIDATE = "CANDIDATE"
MATCH_AUTO = "AUTO_MATCHED"
MATCH_CONFIRMED = "CONFIRMED"
MATCH_CONFLICTED = "CONFLICTED"

EXACT_PRODUCT = "EXACT_PRODUCT"
SAME_VARIANT_DIFFERENT_SIZE = "SAME_VARIANT_DIFFERENT_SIZE"
SAME_PRODUCT_FAMILY = "SAME_PRODUCT_FAMILY"
CATEGORY_EQUIVALENT = "CATEGORY_EQUIVALENT"
UNRELATED = "UNRELATED"

CONTRIBUTOR = "CONTRIBUTOR"
ADMIN = "ADMIN"

GTIN_8 = "GTIN_8"
GTIN_12 = "GTIN_12"
GTIN_13 = "GTIN_13"
GTIN_14 = "GTIN_14"
GTIN_UNKNOWN = "UNKNOWN"

VERIFIED_GTIN = "VERIFIED_GTIN"
PROVISIONAL_NO_GTIN = "PROVISIONAL_NO_GTIN"
GTIN_CONFLICT = "GTIN_CONFLICT"
GTIN_NOT_APPLICABLE = "GTIN_NOT_APPLICABLE"

PACKAGED = "PACKAGED"
FRESH_BULK_ARTISANAL = "FRESH_BULK_ARTISANAL"


@dataclass(slots=True)
class CanonicalProduct:
    id: int | None
    canonical_name: str
    category: str | None
    brand_id: int | None = None
    manufacturer_id: int | None = None
    producer_id: int | None = None
    distributor_id: int | None = None
    brand: str | None = None
    product_family: str | None = None
    variant: str | None = None
    quantity: float | None = None
    unit: str | None = None
    packaging: str | None = None
    flavor: str | None = None
    fat_percentage: float | None = None
    processing_type: str | None = None
    origin_country: str | None = None
    origin_region: str | None = None
    barcode_gtin: str | None = None
    gtin_type: str = GTIN_UNKNOWN
    gtin_status: str = PROVISIONAL_NO_GTIN
    gtin_verified_at: datetime | None = None
    gtin_source: str | None = None
    identity_strategy: str = PACKAGED
    official_product_url: str | None = None
    official_image_url: str | None = None
    active: bool = True
    merged_into_product_id: int | None = None


@dataclass(slots=True)
class Organization:
    id: int | None
    name: str
    kind: str
    website: str | None = None


@dataclass(slots=True)
class ProductSource:
    id: int | None
    product_id: int
    source_type: str
    publisher: str
    url: str
    retrieved_at: datetime
    last_checked_at: datetime | None = None
    status: str = "ACTIVE"
    confidence: float = 0.0
    raw_metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class ProductAttributeEvidence:
    id: int | None
    product_id: int
    field_name: str
    value: str
    confidence: float
    confidence_state: str
    created_at: datetime
    source_id: int | None = None
    source_type: str | None = None


@dataclass(slots=True)
class ProductAlias:
    id: int | None
    product_id: int
    raw_name: str
    normalized_name: str
    matching_status: str = MATCH_UNMATCHED
    matching_confidence: float = 0.0
    store_id: str | None = None
    merchant_id: str | None = None
    chain_id: str | None = None
    source_context: str | None = None
    source_raw_observation_id: int | None = None


@dataclass(slots=True)
class RawObservation:
    id: int | None
    raw_name: str
    source_type: str
    created_at: datetime
    merchant_id: str | None = None
    chain_id: str | None = None
    store_id: str | None = None
    raw_description: str | None = None
    raw_price_text: str | None = None
    parsed_price: float | None = None
    raw_quantity_text: str | None = None
    source_url: str | None = None
    source_document_id: int | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    observed_at: datetime | None = None
    image_reference: str | None = None
    canonical_product_id: int | None = None
    matching_status: str = MATCH_UNMATCHED
    matching_confidence: float = 0.0
    dedupe_key: str | None = None


@dataclass(slots=True)
class HistoricalSourceDocument:
    id: int | None
    source_type: str
    url: str
    retrieved_at: datetime
    chain_id: str | None = None
    merchant_id: str | None = None
    store_id: str | None = None
    canonical_url: str | None = None
    publication_date: date | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    content_hash: str | None = None
    archived_at: datetime | None = None
    extraction_status: str = "PENDING"
    raw_metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class ProductMerge:
    id: int | None
    source_product_id: int
    target_product_id: int
    merged_at: datetime
    reason: str | None = None
    created_by: str | None = None
    undone_at: datetime | None = None
    undone_by: str | None = None


@dataclass(slots=True)
class ValidationTask:
    id: int | None
    task_type: str
    created_at: datetime
    raw_observation_id: int | None = None
    candidate_product_id: int | None = None
    payload: dict[str, Any] | None = None
    status: str = "OPEN"
    usefulness_score: float = 0.0


@dataclass(slots=True)
class ValidationAnswer:
    id: int | None
    validation_task_id: int
    contributor_id: str
    answer: str
    created_at: datetime
    contributor_role: str = CONTRIBUTOR
