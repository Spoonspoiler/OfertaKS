from __future__ import annotations

import sqlite3
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest import TestCase

from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.knowledge import (
    CATEGORY_EQUIVALENT,
    CONFIDENCE_CONFLICTED,
    EXACT_PRODUCT,
    SAME_PRODUCT_FAMILY,
    SAME_VARIANT_DIFFERENT_SIZE,
    CanonicalProduct,
    HistoricalSourceDocument,
    RawObservation,
    ValidationAnswer,
    ValidationTask,
)
from ofertaks.product_sources.base import OfficialProductMetadata
from ofertaks.product_sources.enrichment import ProductEnrichmentService
from ofertaks.product_sources.official_site import parse_official_product_page
from ofertaks.product_sources.registry import ProductSourceRegistry
from ofertaks.services.historical_archive import HISTORICAL_ARCHIVE_START, HistoricalArchiveService
from ofertaks.services.history_service import HistoryService
from ofertaks.services.product_knowledge import classify_product_relationship
from ofertaks.services.promotion_service import PromotionAnalysisService
from ofertaks.services.validation_service import ValidationService


def product(
    name: str,
    *,
    brand: str | None = "Barilla",
    family: str = "spaghetti",
    variant: str | None = "n5",
    quantity: float | None = 500,
    category: str = "PANTRY",
) -> CanonicalProduct:
    return CanonicalProduct(
        id=None,
        canonical_name=name,
        brand=brand,
        product_family=family,
        variant=variant,
        quantity=quantity,
        unit="g" if quantity is not None else None,
        category=category,
    )


class CanonicalKnowledgeTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Database(Path(self.tmp.name) / "knowledge.sqlite3"))
        self.repo.initialize()
        self.now = datetime(2026, 8, 18, tzinfo=UTC)

    def tearDown(self):
        self.tmp.cleanup()

    def test_relationship_levels_distinguish_exact_and_comparable_products(self):
        exact = product("Barilla Spaghetti N5 500 g")
        different_size = product("Barilla Spaghetti N5 1 kg", quantity=1000)
        same_family = product("Barilla Spaghettini N3 500 g", family="spaghettini", variant="n3")
        equivalent = product("De Cecco Spaghetti 500 g", brand="De Cecco")

        self.assertEqual(classify_product_relationship(exact, product("Barilla Spaghetti N5 500 g")).relationship, EXACT_PRODUCT)
        self.assertEqual(classify_product_relationship(exact, different_size).relationship, SAME_VARIANT_DIFFERENT_SIZE)
        self.assertEqual(classify_product_relationship(exact, same_family).relationship, SAME_PRODUCT_FAMILY)
        self.assertEqual(classify_product_relationship(exact, equivalent).relationship, CATEGORY_EQUIVALENT)

    def test_fresh_produce_without_a_brand_can_be_exact(self):
        tomatoes = product("Tomatoes 1 kg", brand=None, family="tomatoes", variant=None, quantity=1000, category="FRUIT_VEGETABLE")
        same_tomatoes = product("Tomatoes 1 kg", brand=None, family="tomatoes", variant=None, quantity=1000, category="FRUIT_VEGETABLE")

        self.assertEqual(classify_product_relationship(tomatoes, same_tomatoes).relationship, EXACT_PRODUCT)

    def test_raw_evidence_is_immutable_but_its_match_can_be_confirmed(self):
        product_id = self.repo.create_canonical_product(product("Rio Mare Tuna 160 g", brand="Rio Mare", family="tuna", variant="oil", quantity=160, category="MEAT"))
        raw_id = self.repo.record_raw_observation(
            RawObservation(
                id=None,
                raw_name="TON RIO OIL 160",
                source_type="RECEIPT",
                created_at=self.now,
                raw_price_text="1.39",
                parsed_price=1.39,
                canonical_product_id=None,
            )
        )
        self.repo.link_raw_observation(raw_id, product_id, "CONFIRMED", 0.95)
        linked = self.repo.raw_observations(product_id)[0]
        self.assertEqual(linked["raw_name"], "TON RIO OIL 160")
        self.assertEqual(linked["canonical_product_id"], product_id)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.repo.database.connect() as db:
                db.execute("UPDATE raw_observations SET raw_name = 'rewritten' WHERE id = ?", (raw_id,))

    def test_raw_evidence_deduplication_returns_the_original_id(self):
        observation = RawObservation(
            id=None,
            raw_name="BARILLA SPAG 500",
            source_type="FLYER_PDF",
            created_at=self.now,
            dedupe_key="flyer:barilla:2025-02-01",
        )
        first = self.repo.record_raw_observation(observation)
        second = self.repo.record_raw_observation(observation)
        self.assertEqual(first, second)
        self.assertEqual(len(self.repo.raw_observations()), 1)

    def test_official_metadata_fills_blanks_and_records_conflicts(self):
        product_id = self.repo.create_canonical_product(product("Barilla Spaghetti N5", quantity=None))
        service = ProductEnrichmentService(self.repo)
        result = service.enrich(
            product_id,
            OfficialProductMetadata(
                source_type="OFFICIAL_MANUFACTURER",
                publisher="Barilla",
                url="https://example.test/barilla/n5",
                retrieved_at=self.now,
                canonical_name="Barilla Spaghetti N5",
                brand="Barilla",
                manufacturer="Barilla S.p.A.",
                quantity=500,
                unit="g",
                origin_country="Italy",
            ),
        )
        enriched = self.repo.get_canonical_product(product_id)
        self.assertIn("quantity", result.filled_fields)
        self.assertEqual(enriched["quantity"], 500)
        self.assertEqual(enriched["manufacturer_name"], "Barilla S.p.A.")

        conflict = service.enrich(
            product_id,
            OfficialProductMetadata(
                source_type="OFFICIAL_MANUFACTURER",
                publisher="Barilla",
                url="https://example.test/barilla/n5-v2",
                retrieved_at=self.now,
                quantity=450,
                unit="g",
            ),
        )
        self.assertIn("quantity", conflict.conflicted_fields)
        self.assertEqual(self.repo.get_canonical_product(product_id)["quantity"], 500)
        evidence = self.repo.list_product_attribute_evidence(product_id, "quantity")
        self.assertEqual(evidence[0]["confidence_state"], CONFIDENCE_CONFLICTED)

    def test_official_schema_parser_only_uses_declared_metadata(self):
        metadata = parse_official_product_page(
            "https://example.test/product",
            """
            <script type="application/ld+json">
              {"@context":"https://schema.org","@type":"Product","name":"Alpsko Milk 1 L",
               "brand":{"name":"Alpsko"},"gtin13":"1234567890123","image":"https://example.test/milk.png"}
            </script>
            """,
            "Alpsko",
            self.now,
        )
        self.assertEqual(metadata.brand, "Alpsko")
        self.assertEqual(metadata.quantity, 1000)
        self.assertEqual(metadata.unit, "ml")
        self.assertEqual(metadata.barcode_gtin, "1234567890123")

    def test_registered_official_parser_has_no_implicit_network_access(self):
        class StaticParser:
            def parse(self, url, html, publisher, retrieved_at):
                return parse_official_product_page(url, html, publisher, retrieved_at)

        registry = ProductSourceRegistry()
        registry.register("official_manufacturer", StaticParser())
        metadata = registry.parse(
            "OFFICIAL_MANUFACTURER",
            "https://example.test/product",
            '<script type="application/ld+json">{"@type":"Product","name":"Olive Oil"}</script>',
            "Example",
            self.now,
        )
        self.assertEqual(metadata.canonical_name, "Olive Oil")

    def test_historical_document_deduplication_and_unmatched_ingestion(self):
        archive = HistoricalArchiveService(self.repo)
        document = HistoricalSourceDocument(
            id=None,
            source_type="FLYER_PDF",
            url="https://example.test/interex-2025.pdf",
            canonical_url="https://example.test/interex-2025.pdf",
            retrieved_at=self.now,
            chain_id="interex",
            publication_date=date(2025, 2, 1),
            extraction_status="OCR_REQUIRED",
        )
        first = self.repo.upsert_historical_source_document(document)
        second = self.repo.upsert_historical_source_document(document)
        self.assertEqual(first, second)
        observation_id = archive.ingest_raw_observation(
            RawObservation(
                id=None,
                raw_name="BARILLA SPAG 500",
                source_type="FLYER_PDF",
                created_at=self.now,
                source_document_id=first,
                parsed_price=0.99,
                observed_at=datetime(2025, 2, 1, tzinfo=UTC),
            )
        )
        self.assertEqual(self.repo.raw_observations(document_id=first)[0]["id"], observation_id)
        self.assertEqual(HISTORICAL_ARCHIVE_START, date(2025, 1, 1))
        self.assertEqual(len(self.repo.list_validation_tasks()), 1)

    def test_merge_is_reversible_without_rewriting_observation_evidence(self):
        old_product = self.repo.create_canonical_product(product("Barilla Spaghetti Legacy", variant="legacy"))
        current_product = self.repo.create_canonical_product(product("Barilla Spaghetti N5"))
        raw_id = self.repo.record_raw_observation(
            RawObservation(
                id=None,
                raw_name="BARILLA SPAG 500",
                source_type="FLYER_PDF",
                created_at=self.now,
                parsed_price=0.99,
                observed_at=self.now,
                canonical_product_id=old_product,
            )
        )
        merge_id = self.repo.merge_products(old_product, current_product, reason="confirmed duplicate")
        self.assertEqual(self.repo.resolved_product_id(old_product), current_product)
        self.assertEqual(self.repo.raw_observations(old_product)[0]["id"], raw_id)
        self.assertEqual(len(self.repo.historical_prices(current_product)), 1)
        self.assertEqual(HistoryService(self.repo).stats_for_product(current_product).count, 1)
        with self.assertRaises(ValueError):
            self.repo.merge_products(current_product, old_product)
        self.repo.undo_product_merge(merge_id)
        self.assertEqual(self.repo.resolved_product_id(old_product), old_product)
        self.assertEqual(self.repo.raw_observations(old_product)[0]["raw_name"], "BARILLA SPAG 500")

    def test_validation_requires_independent_consensus_and_surfaces_conflicts(self):
        product_id = self.repo.create_canonical_product(product("Rio Mare Tuna 160 g", brand="Rio Mare", family="tuna", variant="oil", quantity=160, category="MEAT"))
        raw_id = self.repo.record_raw_observation(
            RawObservation(id=None, raw_name="TON RIO OIL 160", source_type="RECEIPT", created_at=self.now)
        )
        task_id = self.repo.create_validation_task(
            ValidationTask(
                id=None,
                task_type="SAME_PRODUCT",
                created_at=self.now,
                raw_observation_id=raw_id,
                candidate_product_id=product_id,
            )
        )
        validator = ValidationService(self.repo)
        for contributor in ("a", "b"):
            result = validator.submit(
                ValidationAnswer(None, task_id, contributor, "YES", self.now)
            )
            self.assertEqual(result.status, "TENTATIVE")
        result = validator.submit(ValidationAnswer(None, task_id, "c", "YES", self.now))
        self.assertEqual(result.status, "CONFIRMED")
        self.assertEqual(self.repo.raw_observations(product_id)[0]["matching_status"], "CONFIRMED")

        conflict_task = self.repo.create_validation_task(
            ValidationTask(id=None, task_type="SAME_PRODUCT", created_at=self.now)
        )
        validator.submit(ValidationAnswer(None, conflict_task, "a", "YES", self.now))
        conflict = validator.submit(ValidationAnswer(None, conflict_task, "b", "NO", self.now))
        self.assertEqual(conflict.status, "NEEDS_REVIEW")

    def test_promotion_uses_history_not_advertised_discount(self):
        product_id = self.repo.create_canonical_product(product("Barilla Spaghetti N5"))
        for price in (1.19, 1.19, 1.29, 1.19):
            self.repo.record_raw_observation(
                RawObservation(
                    id=None,
                    raw_name="BARILLA SPAG 500",
                    source_type="FLYER_PDF",
                    created_at=self.now,
                    parsed_price=price,
                    observed_at=self.now - timedelta(days=5),
                    canonical_product_id=product_id,
                )
            )
        promotions = PromotionAnalysisService(self.repo)
        weak = promotions.assess(product_id, 1.29, advertised_normal_price=1.79, now=self.now)
        exceptional = promotions.assess(product_id, 0.79, now=self.now)
        self.assertEqual(weak.classification, "PROMOTION_WEAK")
        self.assertEqual(exceptional.classification, "EXCEPTIONAL_PRICE")


class SchemaMigrationTests(TestCase):
    def test_v5_migrates_legacy_products_and_store_aliases_without_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript(
                """
                CREATE TABLE stores (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, website TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1, last_successful_sync TEXT
                );
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_name TEXT NOT NULL, brand TEXT, quantity REAL, unit TEXT, category TEXT
                );
                CREATE TABLE product_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL, store_id TEXT NOT NULL,
                    raw_name TEXT NOT NULL, normalized_name TEXT NOT NULL,
                    UNIQUE(store_id, raw_name, normalized_name)
                );
                INSERT INTO stores (id, name, website) VALUES ('etc', 'ETC', 'https://example.test');
                INSERT INTO products (id, canonical_name, brand, quantity, unit, category)
                VALUES (1, 'rio mare tuna', 'Rio Mare', 160, 'g', 'MEAT');
                INSERT INTO product_aliases (product_id, store_id, raw_name, normalized_name)
                VALUES (1, 'etc', 'TON RIO OIL 160', 'rio mare tuna');
                """
            )
            connection.commit()
            connection.close()

            database = Database(path)
            database.initialize()
            with database.connect() as db:
                product_row = db.execute("SELECT brand_id, created_at, active FROM products WHERE id = 1").fetchone()
                alias_row = db.execute(
                    "SELECT raw_name, matching_status, matching_confidence FROM product_aliases WHERE id = 1"
                ).fetchone()
                self.assertIsNotNone(product_row["created_at"])
                self.assertEqual(product_row["active"], 1)
                self.assertIsNotNone(product_row["brand_id"])
                self.assertEqual(alias_row["raw_name"], "TON RIO OIL 160")
                self.assertEqual(alias_row["matching_status"], "AUTO_MATCHED")
                self.assertEqual(alias_row["matching_confidence"], 0.75)
