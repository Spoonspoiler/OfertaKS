from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from ofertaks.barcode.scanner import ManualBarcodeScanner
from ofertaks.database.database import Database
from ofertaks.database.repository import Repository
from ofertaks.models.knowledge import CanonicalProduct
from ofertaks.normalization.gtin import (
    FRESH_BULK_ARTISANAL,
    GTIN_CONFLICT,
    GTIN_NOT_APPLICABLE,
    GTIN_13,
    PROVISIONAL_NO_GTIN,
    VERIFIED_GTIN,
    gtin_type,
    is_valid_gtin,
)


class GTINIdentityTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repository = Repository(Database(Path(self.tmp.name) / "gtin.sqlite3"))
        self.repository.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_validated_gtin_is_normalized_and_resolves_exact_product(self):
        code = "4006381333931"
        product_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="Test tea", category="PANTRY", barcode_gtin="4006 3813-33931")
        )

        product = self.repository.find_verified_product_by_gtin(code)

        self.assertTrue(is_valid_gtin(code))
        self.assertEqual(gtin_type(code), GTIN_13)
        self.assertEqual(product["id"], product_id)
        self.assertEqual(product["gtin_status"], VERIFIED_GTIN)
        self.assertEqual(ManualBarcodeScanner.from_text(code).barcode_gtin, code)

    def test_invalid_gtin_cannot_create_a_packaged_product(self):
        with self.assertRaises(ValueError):
            self.repository.create_canonical_product(
                CanonicalProduct(id=None, canonical_name="Invalid tea", category="PANTRY", barcode_gtin="4006381333932")
            )

    def test_missing_code_states_keep_fresh_and_packaged_products_distinct(self):
        fresh_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="Tomatoes", category="FRUIT_VEGETABLE")
        )
        packaged_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="Rice", category="PANTRY")
        )

        fresh = self.repository.get_canonical_product(fresh_id)
        packaged = self.repository.get_canonical_product(packaged_id)

        self.assertEqual(fresh["identity_strategy"], FRESH_BULK_ARTISANAL)
        self.assertEqual(fresh["gtin_status"], GTIN_NOT_APPLICABLE)
        self.assertEqual(packaged["gtin_status"], PROVISIONAL_NO_GTIN)

    def test_conflicting_assignment_never_overwrites_verified_identity(self):
        code = "4006381333931"
        first_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="First tea", category="PANTRY", barcode_gtin=code)
        )
        second_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="Second tea", category="PANTRY")
        )

        status = self.repository.assign_gtin(second_id, code)

        self.assertEqual(status, GTIN_CONFLICT)
        self.assertEqual(self.repository.find_verified_product_by_gtin(code)["id"], first_id)
        self.assertEqual(self.repository.get_canonical_product(second_id)["gtin_status"], GTIN_CONFLICT)
        self.assertEqual(self.repository.list_validation_tasks()[0]["task_type"], "GTIN_REVIEW")
        self.repository.initialize()
        self.assertEqual(self.repository.get_canonical_product(second_id)["gtin_status"], GTIN_CONFLICT)

    def test_distinct_gtins_can_keep_same_display_identity_separate(self):
        first_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="Tea", category="PANTRY", barcode_gtin="4006381333931")
        )
        second_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="Tea", category="PANTRY", barcode_gtin="5901234123457")
        )

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(self.repository.find_verified_product_by_gtin("4006381333931")["id"], first_id)
        self.assertEqual(self.repository.find_verified_product_by_gtin("5901234123457")["id"], second_id)

    def test_migration_marks_invalid_legacy_code_for_review_without_deleting_product(self):
        product_id = self.repository.create_canonical_product(
            CanonicalProduct(id=None, canonical_name="Legacy product", category="PANTRY")
        )
        with self.repository.database.connect() as db:
            db.execute("UPDATE products SET barcode_gtin = ? WHERE id = ?", ("1234567890123", product_id))

        self.repository.initialize()

        product = self.repository.get_canonical_product(product_id)
        self.assertEqual(product["barcode_gtin"], "1234567890123")
        self.assertEqual(product["gtin_status"], GTIN_CONFLICT)
        self.assertEqual(self.repository.list_validation_tasks()[0]["task_type"], "GTIN_REVIEW")
