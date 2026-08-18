"""Repository layer for SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from datetime import UTC, datetime
from typing import Any, Iterable

from ofertaks.app.config import CHAIN_CONFIG, SOURCE_STATUS_CONFIG, STORE_CONFIG
from ofertaks.app.smoke import app_smoke_check
from ofertaks.database.database import Database
from ofertaks.models.community import (
    MerchantProductObservation,
    MerchantReport,
    OriginObservation,
    QualityObservation,
    UserPriceObservation,
)
from ofertaks.models.merchant import Chain, Merchant
from ofertaks.models.knowledge import (
    CanonicalProduct,
    HistoricalSourceDocument,
    ProductAlias,
    ProductAttributeEvidence,
    ProductSource,
    RawObservation,
    ValidationAnswer,
    ValidationTask,
)
from ofertaks.models.offer import Offer
from ofertaks.models.recipe import Recipe, RecipeIngredient
from ofertaks.normalization.product_normalizer import normalize_product_name
from ofertaks.utils.categories import category_filter_values
from ofertaks.utils.text import comparable_text


class Repository:
    def __init__(self, database: Database):
        self.database = database

    def initialize(self) -> None:
        self.database.initialize()
        self.seed_stores()
        self.seed_chains()

    def seed_stores(self) -> None:
        with self.database.connect() as db:
            for store_id, data in STORE_CONFIG.items():
                db.execute(
                    """
                    INSERT INTO stores (id, name, website, enabled)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        website=excluded.website
                    """,
                    (store_id, data["name"], data["website"], int(data["enabled"])),
                )

    def seed_chains(self) -> None:
        now = self._now()
        with self.database.connect() as db:
            for chain_id, data in CHAIN_CONFIG.items():
                db.execute(
                    """
                    INSERT INTO chains (id, name, website, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        website=excluded.website,
                        enabled=excluded.enabled,
                        updated_at=excluded.updated_at
                    """,
                    (
                        chain_id,
                        data["name"],
                        data["website"],
                        int(data["enabled"]),
                        now,
                        now,
                    ),
                )

    def chains(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM chains"
        params: tuple[Any, ...] = ()
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY name"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def stores(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM stores"
        params: tuple[Any, ...] = ()
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY name"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def set_store_enabled(self, store_id: str, enabled: bool) -> None:
        with self.database.connect() as db:
            db.execute("UPDATE stores SET enabled = ? WHERE id = ?", (int(enabled), store_id))

    def start_scrape_run(self, store_id: str) -> int:
        now = self._now()
        with self.database.connect() as db:
            cursor = db.execute(
                "INSERT INTO scrape_runs (store_id, started_at, status) VALUES (?, ?, ?)",
                (store_id, now, "running"),
            )
            return int(cursor.lastrowid)

    def finish_scrape_run(
        self,
        run_id: int,
        status: str,
        items_found: int,
        error_message: str | None = None,
    ) -> None:
        now = self._now()
        with self.database.connect() as db:
            db.execute(
                """
                UPDATE scrape_runs
                SET finished_at = ?, status = ?, items_found = ?, error_message = ?
                WHERE id = ?
                """,
                (now, status, items_found, error_message, run_id),
            )
            if status == "success":
                store_id = db.execute(
                    "SELECT store_id FROM scrape_runs WHERE id = ?", (run_id,)
                ).fetchone()["store_id"]
                db.execute(
                    "UPDATE stores SET last_successful_sync = ? WHERE id = ?",
                    (now, store_id),
                )

    def replace_current_offers(self, store_id: str, offers: Iterable[Offer]) -> None:
        offers = list(offers)
        with self.database.connect() as db:
            db.execute("DELETE FROM offers WHERE store_id = ?", (store_id,))
            for offer in offers:
                product_id = self._upsert_product(db, offer)
                db.execute(
                    """
                    INSERT INTO offers (
                        store_id, merchant_id, chain_id,
                        raw_name, normalized_name, brand, quantity, unit,
                        normal_price, offer_price, unit_price, discount_percent,
                        category, valid_from, valid_until, origin_country, origin_region,
                        source_url, image_url, scraped_at
                    )
                    VALUES (
                        :store_id, :merchant_id, :chain_id,
                        :raw_name, :normalized_name, :brand, :quantity, :unit,
                        :normal_price, :offer_price, :unit_price, :discount_percent,
                        :category, :valid_from, :valid_until, :origin_country, :origin_region,
                        :source_url, :image_url, :scraped_at
                    )
                    """,
                    offer.to_record(),
                )
                self._ensure_product_alias(db, product_id, offer.store_id, offer.raw_name, offer.normalized_name)
                raw_observation_id = self._record_offer_evidence(db, offer, product_id)
                db.execute(
                    """
                    INSERT INTO price_history (
                        product_id, store_id, price, normal_price, observed_at,
                        raw_observation_id, source_type, confidence_state
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        offer.store_id,
                        offer.offer_price,
                        offer.normal_price,
                        offer.scraped_at.isoformat(timespec="seconds"),
                        raw_observation_id,
                        "SCRAPER_HTML",
                        "MEDIUM",
                    ),
                )

    def insert_offer(self, offer: Offer) -> int:
        with self.database.connect() as db:
            product_id = self._upsert_product(db, offer)
            cursor = db.execute(
                """
                INSERT INTO offers (
                    store_id, merchant_id, chain_id,
                    raw_name, normalized_name, brand, quantity, unit,
                    normal_price, offer_price, unit_price, discount_percent,
                    category, valid_from, valid_until, origin_country, origin_region,
                    source_url, image_url, scraped_at
                )
                VALUES (
                    :store_id, :merchant_id, :chain_id,
                    :raw_name, :normalized_name, :brand, :quantity, :unit,
                    :normal_price, :offer_price, :unit_price, :discount_percent,
                    :category, :valid_from, :valid_until, :origin_country, :origin_region,
                    :source_url, :image_url, :scraped_at
                )
                """,
                offer.to_record(),
            )
            self._ensure_product_alias(db, product_id, offer.store_id, offer.raw_name, offer.normalized_name)
            raw_observation_id = self._record_offer_evidence(db, offer, product_id)
            db.execute(
                """
                INSERT INTO price_history (
                    product_id, store_id, price, normal_price, observed_at,
                    raw_observation_id, source_type, confidence_state
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    offer.store_id,
                    offer.offer_price,
                    offer.normal_price,
                    offer.scraped_at.isoformat(timespec="seconds"),
                    raw_observation_id,
                    "SCRAPER_HTML",
                    "MEDIUM",
                ),
            )
            return int(cursor.lastrowid)

    def _upsert_product(self, db, offer: Offer) -> int:
        canonical = normalize_product_name(offer.raw_name, offer.category)
        canonical_name = canonical.normalized_name or offer.normalized_name
        brand = offer.brand or canonical.brand
        quantity = offer.quantity if offer.quantity is not None else canonical.quantity
        unit = offer.unit or canonical.unit
        category = offer.category or canonical.category
        brand_id = self._ensure_organization(db, "brands", brand) if brand else None
        now = self._now()
        db.execute(
            """
            INSERT OR IGNORE INTO products (
                canonical_name, brand, brand_id, quantity, unit, category, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_name,
                brand,
                brand_id,
                quantity,
                unit,
                category,
                now,
                now,
            ),
        )
        row = db.execute(
            """
            SELECT id FROM products
            WHERE canonical_name = ?
              AND COALESCE(brand, '') = COALESCE(?, '')
              AND COALESCE(quantity, -1) = COALESCE(?, -1)
              AND COALESCE(unit, '') = COALESCE(?, '')
            """,
            (
                canonical_name,
                brand,
                quantity,
                unit,
            ),
        ).fetchone()
        product_id = int(row["id"])
        if brand_id is not None:
            db.execute(
                "UPDATE products SET brand_id = COALESCE(brand_id, ?), updated_at = ? WHERE id = ?",
                (brand_id, now, product_id),
            )
        return product_id

    def _ensure_organization(self, db, table: str, name: str) -> int:
        if table not in {"brands", "manufacturers", "producers", "distributors"}:
            raise ValueError(f"Unsupported organization table: {table}")
        normalized_name = comparable_text(name)
        if not normalized_name:
            raise ValueError("Organization name is required")
        now = self._now()
        db.execute(
            f"""
            INSERT INTO {table} (name, normalized_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(normalized_name) DO UPDATE SET updated_at=excluded.updated_at
            """,
            (name.strip(), normalized_name, now, now),
        )
        row = db.execute(f"SELECT id FROM {table} WHERE normalized_name = ?", (normalized_name,)).fetchone()
        return int(row["id"])

    def _ensure_product_alias(
        self,
        db,
        product_id: int,
        store_id: str | None,
        raw_name: str,
        normalized_name: str,
        *,
        merchant_id: str | None = None,
        chain_id: str | None = None,
        source_context: str = "SCRAPER",
        matching_status: str = "AUTO_MATCHED",
        matching_confidence: float = 0.75,
        source_raw_observation_id: int | None = None,
    ) -> int:
        row = db.execute(
            """
            SELECT id FROM product_aliases
            WHERE product_id = ? AND store_id IS ? AND merchant_id IS ? AND chain_id IS ?
              AND raw_name = ? AND normalized_name = ?
            """,
            (product_id, store_id, merchant_id, chain_id, raw_name, normalized_name),
        ).fetchone()
        if row:
            return int(row["id"])
        cursor = db.execute(
            """
            INSERT INTO product_aliases (
                product_id, store_id, merchant_id, chain_id, raw_name, normalized_name,
                source_context, matching_status, matching_confidence, source_raw_observation_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                store_id,
                merchant_id,
                chain_id,
                raw_name,
                normalized_name,
                source_context,
                matching_status,
                matching_confidence,
                source_raw_observation_id,
                self._now(),
            ),
        )
        return int(cursor.lastrowid)

    def _record_offer_evidence(self, db, offer: Offer, product_id: int) -> int:
        observed_at = offer.scraped_at.isoformat(timespec="seconds")
        dedupe_payload = "|".join(
            (
                "offer",
                offer.store_id,
                offer.source_url,
                offer.raw_name,
                str(offer.offer_price),
                observed_at,
            )
        )
        observation = RawObservation(
            id=None,
            raw_name=offer.raw_name,
            source_type="SCRAPER_HTML",
            created_at=offer.scraped_at,
            merchant_id=offer.merchant_id,
            chain_id=offer.chain_id,
            store_id=offer.store_id,
            parsed_price=offer.offer_price,
            source_url=offer.source_url,
            valid_from=offer.valid_from,
            valid_until=offer.valid_until,
            observed_at=offer.scraped_at,
            image_reference=offer.image_url,
            canonical_product_id=product_id,
            matching_status="AUTO_MATCHED",
            matching_confidence=0.75,
            dedupe_key=sha256(dedupe_payload.encode("utf-8")).hexdigest(),
        )
        return self._insert_raw_observation(db, observation)

    def record_raw_observation(self, observation: RawObservation) -> int:
        """Append source evidence without allowing later rewrites of raw fields."""

        if not observation.raw_name.strip():
            raise ValueError("Raw observation name is required")
        if observation.parsed_price is not None and observation.parsed_price < 0:
            raise ValueError("Parsed price cannot be negative")
        with self.database.connect() as db:
            return self._insert_raw_observation(db, observation)

    def _insert_raw_observation(self, db, observation: RawObservation) -> int:
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO raw_observations (
                merchant_id, chain_id, store_id, raw_name, raw_description, raw_price_text,
                parsed_price, raw_quantity_text, source_type, source_url, source_document_id,
                valid_from, valid_until, observed_at, image_reference, canonical_product_id,
                matching_status, matching_confidence, dedupe_key, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.merchant_id,
                observation.chain_id,
                observation.store_id,
                observation.raw_name,
                observation.raw_description,
                observation.raw_price_text,
                observation.parsed_price,
                observation.raw_quantity_text,
                observation.source_type.upper(),
                observation.source_url,
                observation.source_document_id,
                observation.valid_from.isoformat() if observation.valid_from else None,
                observation.valid_until.isoformat() if observation.valid_until else None,
                self._timestamp(observation.observed_at),
                observation.image_reference,
                observation.canonical_product_id,
                observation.matching_status.upper(),
                max(0.0, min(1.0, observation.matching_confidence)),
                observation.dedupe_key,
                self._timestamp(observation.created_at) or self._now(),
            ),
        )
        if cursor.rowcount:
            return int(cursor.lastrowid)
        if observation.dedupe_key:
            row = db.execute(
                "SELECT id FROM raw_observations WHERE dedupe_key = ?", (observation.dedupe_key,)
            ).fetchone()
            if row:
                return int(row["id"])
        raise RuntimeError("Raw observation could not be stored")

    def list_offers(
        self,
        store_id: str | None = None,
        category: str | None = None,
        sort: str = "best",
        limit: int | None = 200,
        food_only: bool = True,
    ) -> list[Offer]:
        where = []
        params: list[Any] = []
        if store_id:
            where.append("o.store_id = ?")
            params.append(store_id)
        if category:
            values = category_filter_values(category)
            where.append(f"o.category IN ({','.join('?' for _ in values)})")
            params.extend(values)
        elif food_only:
            values = category_filter_values(None)
            where.append(f"o.category IN ({','.join('?' for _ in values)})")
            params.extend(values)
        sql = """
            SELECT o.*, s.name AS store_name
            FROM offers o
            JOIN stores s ON s.id = o.store_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        order_map = {
            "lowest": "o.offer_price ASC",
            "discount": "COALESCE(o.discount_percent, 0) DESC",
            "newest": "o.scraped_at DESC",
            "unit": "COALESCE(o.unit_price, o.offer_price) ASC",
            "best": "COALESCE(o.discount_percent, 0) DESC, COALESCE(o.unit_price, o.offer_price) ASC",
        }
        sql += f" ORDER BY {order_map.get(sort, order_map['best'])}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.database.connect() as db:
            return [Offer.from_row(row, row["store_name"]) for row in db.execute(sql, params)]

    def search_offers(
        self,
        query: str,
        limit: int = 100,
        food_only: bool = True,
    ) -> list[Offer]:
        like = f"%{query.casefold()}%"
        where = [
            """(
                lower(o.raw_name) LIKE ?
                OR lower(o.normalized_name) LIKE ?
                OR lower(COALESCE(o.brand, '')) LIKE ?
            )"""
        ]
        params: list[Any] = [like, like, like]
        if food_only:
            values = category_filter_values(None)
            where.append(f"o.category IN ({','.join('?' for _ in values)})")
            params.extend(values)
        params.append(limit)
        with self.database.connect() as db:
            rows = db.execute(
                f"""
                SELECT o.*, s.name AS store_name
                FROM offers o
                JOIN stores s ON s.id = o.store_id
                WHERE {' AND '.join(where)}
                ORDER BY COALESCE(o.unit_price, o.offer_price) ASC
                LIMIT ?
                """,
                params,
            )
            return [Offer.from_row(row, row["store_name"]) for row in rows]

    def find_product_id_for_offer(self, offer: Offer) -> int | None:
        with self.database.connect() as db:
            row = db.execute(
                """
                SELECT p.id
                FROM products p
                JOIN product_aliases a ON a.product_id = p.id
                WHERE a.store_id = ? AND a.raw_name = ? AND a.normalized_name = ?
                LIMIT 1
                """,
                (offer.store_id, offer.raw_name, offer.normalized_name),
            ).fetchone()
            return int(row["id"]) if row else None

    def product_category(self, product_id: int) -> str | None:
        with self.database.connect() as db:
            row = db.execute("SELECT category FROM products WHERE id = ?", (product_id,)).fetchone()
            return row["category"] if row else None

    def ensure_product(self, raw_name: str) -> int:
        """Create or reuse a canonical product for a local merchant observation."""

        canonical = normalize_product_name(raw_name)
        canonical_name = canonical.normalized_name or raw_name.casefold().strip()
        with self.database.connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO products (
                    canonical_name, brand, brand_id, quantity, unit, category, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    canonical_name,
                    canonical.brand,
                    self._ensure_organization(db, "brands", canonical.brand) if canonical.brand else None,
                    canonical.quantity,
                    canonical.unit,
                    canonical.category,
                    self._now(),
                    self._now(),
                ),
            )
            row = db.execute(
                """
                SELECT id FROM products
                WHERE canonical_name = ?
                  AND COALESCE(brand, '') = COALESCE(?, '')
                  AND COALESCE(quantity, -1) = COALESCE(?, -1)
                  AND COALESCE(unit, '') = COALESCE(?, '')
                """,
                (canonical_name, canonical.brand, canonical.quantity, canonical.unit),
            ).fetchone()
            return int(row["id"])

    def offers_for_product(
        self,
        product_id: int,
        *,
        food_only: bool = True,
        limit: int = 30,
    ) -> list[Offer]:
        """Return current store offers linked to the same canonical product."""

        where = ["a.product_id = ?"]
        params: list[Any] = [product_id]
        if food_only:
            values = category_filter_values(None)
            where.append(f"o.category IN ({','.join('?' for _ in values)})")
            params.extend(values)
        params.append(limit)
        sql = f"""
            SELECT DISTINCT o.*, s.name AS store_name
            FROM offers o
            JOIN stores s ON s.id = o.store_id
            JOIN product_aliases a
              ON a.store_id = o.store_id
             AND a.raw_name = o.raw_name
             AND a.normalized_name = o.normalized_name
            WHERE {' AND '.join(where)}
            ORDER BY COALESCE(o.unit_price, o.offer_price) ASC, s.name
            LIMIT ?
        """
        with self.database.connect() as db:
            return [Offer.from_row(row, row["store_name"]) for row in db.execute(sql, params)]

    def price_history(self, product_id: int, days: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM price_history WHERE product_id = ?"
        params: list[Any] = [product_id]
        if days is not None:
            sql += " AND observed_at >= datetime('now', ?)"
            params.append(f"-{days} days")
        sql += " ORDER BY observed_at ASC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def create_canonical_product(self, product: CanonicalProduct) -> int:
        """Create or reuse a specific purchasable identity without guessing missing fields."""

        if not product.canonical_name.strip():
            raise ValueError("Canonical product name is required")
        with self.database.connect() as db:
            brand_id = product.brand_id
            if brand_id is None and product.brand:
                brand_id = self._ensure_organization(db, "brands", product.brand)
            if product.barcode_gtin:
                existing = db.execute(
                    "SELECT id FROM products WHERE barcode_gtin = ?", (product.barcode_gtin,)
                ).fetchone()
                if existing:
                    return int(existing["id"])
            now = self._now()
            db.execute(
                """
                INSERT OR IGNORE INTO products (
                    canonical_name, brand, brand_id, manufacturer_id, producer_id, distributor_id,
                    product_family, variant, quantity, unit, packaging, flavor, fat_percentage,
                    processing_type, category, origin_country, origin_region, barcode_gtin,
                    official_product_url, official_image_url, active, merged_into_product_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.canonical_name.strip(),
                    product.brand,
                    brand_id,
                    product.manufacturer_id,
                    product.producer_id,
                    product.distributor_id,
                    product.product_family,
                    product.variant,
                    product.quantity,
                    product.unit,
                    product.packaging,
                    product.flavor,
                    product.fat_percentage,
                    product.processing_type,
                    product.category,
                    product.origin_country,
                    product.origin_region,
                    product.barcode_gtin,
                    product.official_product_url,
                    product.official_image_url,
                    int(product.active),
                    product.merged_into_product_id,
                    now,
                    now,
                ),
            )
            row = db.execute(
                """
                SELECT id FROM products
                WHERE canonical_name = ?
                  AND COALESCE(brand, '') = COALESCE(?, '')
                  AND COALESCE(quantity, -1) = COALESCE(?, -1)
                  AND COALESCE(unit, '') = COALESCE(?, '')
                """,
                (product.canonical_name.strip(), product.brand, product.quantity, product.unit),
            ).fetchone()
            return int(row["id"])

    def ensure_organization(self, kind: str, name: str) -> int:
        table_by_kind = {
            "BRAND": "brands",
            "MANUFACTURER": "manufacturers",
            "PRODUCER": "producers",
            "DISTRIBUTOR": "distributors",
        }
        table = table_by_kind.get(kind.upper())
        if not table:
            raise ValueError("Unsupported organization kind")
        with self.database.connect() as db:
            return self._ensure_organization(db, table, name)

    def set_product_organization_if_empty(self, product_id: int, kind: str, name: str) -> bool:
        column_by_kind = {
            "BRAND": "brand_id",
            "MANUFACTURER": "manufacturer_id",
            "PRODUCER": "producer_id",
            "DISTRIBUTOR": "distributor_id",
        }
        table_by_kind = {
            "BRAND": "brands",
            "MANUFACTURER": "manufacturers",
            "PRODUCER": "producers",
            "DISTRIBUTOR": "distributors",
        }
        normalized_kind = kind.upper()
        column = column_by_kind.get(normalized_kind)
        table = table_by_kind.get(normalized_kind)
        if not column or not table:
            raise ValueError("Unsupported organization kind")
        with self.database.connect() as db:
            existing = db.execute(f"SELECT {column} FROM products WHERE id = ?", (product_id,)).fetchone()
            if not existing:
                raise ValueError("Canonical product does not exist")
            if existing[column] is not None:
                return False
            organization_id = self._ensure_organization(db, table, name)
            assignments = f"{column} = ?, updated_at = ?"
            params: list[Any] = [organization_id, self._now()]
            if normalized_kind == "BRAND":
                assignments = "brand = COALESCE(brand, ?), " + assignments
                params.insert(0, name.strip())
            params.append(product_id)
            db.execute(f"UPDATE products SET {assignments} WHERE id = ?", params)
            return True

    def get_canonical_product(self, product_id: int) -> dict[str, Any] | None:
        with self.database.connect() as db:
            row = db.execute(
                """
                SELECT p.*, b.name AS brand_name, m.name AS manufacturer_name,
                       pr.name AS producer_name, d.name AS distributor_name
                FROM products p
                LEFT JOIN brands b ON b.id = p.brand_id
                LEFT JOIN manufacturers m ON m.id = p.manufacturer_id
                LEFT JOIN producers pr ON pr.id = p.producer_id
                LEFT JOIN distributors d ON d.id = p.distributor_id
                WHERE p.id = ?
                """,
                (product_id,),
            ).fetchone()
            return dict(row) if row else None

    def set_product_fields_if_empty(self, product_id: int, fields: dict[str, Any]) -> list[str]:
        """Fill only absent canonical fields; conflicts stay in attribute evidence for review."""

        allowed = {
            "brand",
            "brand_id",
            "manufacturer_id",
            "producer_id",
            "distributor_id",
            "product_family",
            "variant",
            "quantity",
            "unit",
            "packaging",
            "flavor",
            "fat_percentage",
            "processing_type",
            "category",
            "origin_country",
            "origin_region",
            "barcode_gtin",
            "official_product_url",
            "official_image_url",
        }
        updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
        if not updates:
            return []
        with self.database.connect() as db:
            existing = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if not existing:
                raise ValueError("Canonical product does not exist")
            changed = [key for key, value in updates.items() if existing[key] in {None, ""} and value not in {None, ""}]
            if changed:
                assignments = ", ".join(f"{key} = ?" for key in changed)
                db.execute(
                    f"UPDATE products SET {assignments}, updated_at = ? WHERE id = ?",
                    [updates[key] for key in changed] + [self._now(), product_id],
                )
            return changed

    def add_product_alias(self, alias: ProductAlias) -> int:
        with self.database.connect() as db:
            return self._ensure_product_alias(
                db,
                alias.product_id,
                alias.store_id,
                alias.raw_name,
                alias.normalized_name,
                merchant_id=alias.merchant_id,
                chain_id=alias.chain_id,
                source_context=alias.source_context or "MANUAL",
                matching_status=alias.matching_status,
                matching_confidence=alias.matching_confidence,
                source_raw_observation_id=alias.source_raw_observation_id,
            )

    def find_product_alias(
        self,
        raw_name: str,
        normalized_name: str,
        *,
        merchant_id: str | None = None,
        chain_id: str | None = None,
        store_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve the most-specific known alias without treating a guess as confirmation."""

        with self.database.connect() as db:
            row = db.execute(
                """
                SELECT a.*, p.canonical_name
                FROM product_aliases a
                JOIN products p ON p.id = a.product_id
                WHERE a.raw_name = ? AND a.normalized_name = ?
                  AND (a.merchant_id IS NULL OR a.merchant_id = ?)
                  AND (a.chain_id IS NULL OR a.chain_id = ?)
                  AND (a.store_id IS NULL OR a.store_id = ?)
                ORDER BY (a.merchant_id IS NOT NULL) DESC,
                         (a.chain_id IS NOT NULL) DESC,
                         (a.store_id IS NOT NULL) DESC,
                         a.matching_confidence DESC, a.id DESC
                LIMIT 1
                """,
                (raw_name, normalized_name, merchant_id, chain_id, store_id),
            ).fetchone()
            return dict(row) if row else None

    def link_raw_observation(
        self,
        raw_observation_id: int,
        product_id: int | None,
        matching_status: str,
        matching_confidence: float,
    ) -> None:
        with self.database.connect() as db:
            db.execute(
                """
                UPDATE raw_observations
                SET canonical_product_id = ?, matching_status = ?, matching_confidence = ?
                WHERE id = ?
                """,
                (
                    product_id,
                    matching_status.upper(),
                    max(0.0, min(1.0, matching_confidence)),
                    raw_observation_id,
                ),
            )

    def raw_observations(
        self,
        product_id: int | None = None,
        document_id: int | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if product_id is not None:
            where.append("canonical_product_id = ?")
            params.append(product_id)
        if document_id is not None:
            where.append("source_document_id = ?")
            params.append(document_id)
        sql = "SELECT * FROM raw_observations"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY COALESCE(observed_at, created_at), id"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def upsert_product_source(self, source: ProductSource) -> int:
        if not source.publisher.strip() or not source.url.strip():
            raise ValueError("Product source publisher and URL are required")
        with self.database.connect() as db:
            db.execute(
                """
                INSERT INTO product_sources (
                    product_id, source_type, publisher, url, retrieved_at, last_checked_at,
                    status, confidence, raw_metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, url) DO UPDATE SET
                    last_checked_at=excluded.last_checked_at,
                    status=excluded.status,
                    confidence=excluded.confidence,
                    raw_metadata_json=excluded.raw_metadata_json
                """,
                (
                    source.product_id,
                    source.source_type.upper(),
                    source.publisher.strip(),
                    source.url.strip(),
                    self._timestamp(source.retrieved_at),
                    self._timestamp(source.last_checked_at),
                    source.status.upper(),
                    max(0.0, min(1.0, source.confidence)),
                    json.dumps(source.raw_metadata, ensure_ascii=False) if source.raw_metadata is not None else None,
                ),
            )
            row = db.execute(
                "SELECT id FROM product_sources WHERE product_id = ? AND url = ?",
                (source.product_id, source.url.strip()),
            ).fetchone()
            return int(row["id"])

    def list_product_sources(self, product_id: int) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM product_sources WHERE product_id = ? ORDER BY confidence DESC, id DESC",
                    (product_id,),
                )
            ]

    def add_product_attribute_evidence(self, evidence: ProductAttributeEvidence) -> int:
        if not evidence.field_name.strip():
            raise ValueError("Product evidence field is required")
        with self.database.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO product_attribute_evidence (
                    product_id, field_name, value_text, source_id, source_type,
                    confidence, confidence_state, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.product_id,
                    evidence.field_name,
                    evidence.value,
                    evidence.source_id,
                    evidence.source_type.upper() if evidence.source_type else None,
                    max(0.0, min(1.0, evidence.confidence)),
                    evidence.confidence_state.upper(),
                    self._timestamp(evidence.created_at) or self._now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_product_attribute_evidence(self, product_id: int, field_name: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM product_attribute_evidence WHERE product_id = ?"
        params: list[Any] = [product_id]
        if field_name:
            sql += " AND field_name = ?"
            params.append(field_name)
        sql += " ORDER BY field_name, confidence DESC, id DESC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def merge_products(
        self, source_product_id: int, target_product_id: int, *, reason: str | None = None, created_by: str | None = None
    ) -> int:
        if source_product_id == target_product_id:
            raise ValueError("A product cannot merge into itself")
        with self.database.connect() as db:
            target_product_id = self._resolve_product_id(db, target_product_id)
            if source_product_id == target_product_id:
                raise ValueError("A product cannot merge into its own resolved identity")
            active = db.execute(
                "SELECT id FROM product_merges WHERE source_product_id = ? AND undone_at IS NULL",
                (source_product_id,),
            ).fetchone()
            if active:
                raise ValueError("Source product already has an active merge")
            cursor = db.execute(
                """
                INSERT INTO product_merges (
                    source_product_id, target_product_id, reason, created_by, merged_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (source_product_id, target_product_id, reason, created_by, self._now()),
            )
            db.execute(
                "UPDATE products SET active = 0, merged_into_product_id = ?, updated_at = ? WHERE id = ?",
                (target_product_id, self._now(), source_product_id),
            )
            return int(cursor.lastrowid)

    def undo_product_merge(self, merge_id: int, *, undone_by: str | None = None) -> None:
        with self.database.connect() as db:
            merge = db.execute("SELECT * FROM product_merges WHERE id = ?", (merge_id,)).fetchone()
            if not merge or merge["undone_at"]:
                raise ValueError("Active product merge does not exist")
            now = self._now()
            db.execute("UPDATE product_merges SET undone_at = ?, undone_by = ? WHERE id = ?", (now, undone_by, merge_id))
            db.execute(
                "UPDATE products SET active = 1, merged_into_product_id = NULL, updated_at = ? WHERE id = ?",
                (now, merge["source_product_id"]),
            )

    def resolved_product_id(self, product_id: int) -> int:
        with self.database.connect() as db:
            return self._resolve_product_id(db, product_id)

    def product_merge_history(self, product_id: int) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    """
                    SELECT * FROM product_merges
                    WHERE source_product_id = ? OR target_product_id = ?
                    ORDER BY merged_at, id
                    """,
                    (product_id, product_id),
                )
            ]

    def historical_prices(self, product_id: int) -> list[dict[str, Any]]:
        """Return current and archived observations without double-counting linked scraper rows."""

        with self.database.connect() as db:
            product_ids = self._merged_product_ids(db, self._resolve_product_id(db, product_id))
            placeholders = ",".join("?" for _ in product_ids)
            rows = db.execute(
                f"""
                SELECT price, normal_price, observed_at, source_type, confidence_state,
                       raw_observation_id, 'PRICE_HISTORY' AS evidence_kind
                FROM price_history
                WHERE product_id IN ({placeholders})
                UNION ALL
                SELECT parsed_price AS price, NULL AS normal_price,
                       COALESCE(observed_at, created_at) AS observed_at,
                       source_type, matching_status AS confidence_state,
                       id AS raw_observation_id, 'RAW_OBSERVATION' AS evidence_kind
                FROM raw_observations r
                WHERE canonical_product_id IN ({placeholders})
                  AND parsed_price IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM price_history p WHERE p.raw_observation_id = r.id
                  )
                ORDER BY observed_at, raw_observation_id
                """,
                [*product_ids, *product_ids],
            )
            return [dict(row) for row in rows]

    def upsert_historical_source_document(self, document: HistoricalSourceDocument) -> int:
        """Store one historical document once, even when discovery sees it repeatedly."""

        if not document.url.strip():
            raise ValueError("Historical source URL is required")
        canonical_url = document.canonical_url or document.url
        with self.database.connect() as db:
            existing = None
            if document.content_hash:
                existing = db.execute(
                    "SELECT id FROM historical_source_documents WHERE content_hash = ? LIMIT 1",
                    (document.content_hash,),
                ).fetchone()
            if existing is None:
                existing = db.execute(
                    """
                    SELECT id FROM historical_source_documents
                    WHERE canonical_url = ? OR (canonical_url IS NULL AND url = ?)
                    ORDER BY id LIMIT 1
                    """,
                    (canonical_url, document.url),
                ).fetchone()
            if existing:
                document_id = int(existing["id"])
                db.execute(
                    """
                    UPDATE historical_source_documents
                    SET retrieved_at = ?, content_hash = COALESCE(?, content_hash),
                        extraction_status = ?, raw_metadata_json = COALESCE(?, raw_metadata_json)
                    WHERE id = ?
                    """,
                    (
                        self._timestamp(document.retrieved_at),
                        document.content_hash,
                        document.extraction_status.upper(),
                        json.dumps(document.raw_metadata, ensure_ascii=False)
                        if document.raw_metadata is not None
                        else None,
                        document_id,
                    ),
                )
                return document_id
            cursor = db.execute(
                """
                INSERT INTO historical_source_documents (
                    chain_id, merchant_id, store_id, source_type, url, canonical_url,
                    publication_date, valid_from, valid_until, content_hash, retrieved_at,
                    archived_at, extraction_status, raw_metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.chain_id,
                    document.merchant_id,
                    document.store_id,
                    document.source_type.upper(),
                    document.url,
                    canonical_url,
                    document.publication_date.isoformat() if document.publication_date else None,
                    document.valid_from.isoformat() if document.valid_from else None,
                    document.valid_until.isoformat() if document.valid_until else None,
                    document.content_hash,
                    self._timestamp(document.retrieved_at),
                    self._timestamp(document.archived_at),
                    document.extraction_status.upper(),
                    json.dumps(document.raw_metadata, ensure_ascii=False) if document.raw_metadata is not None else None,
                    self._now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_historical_source_documents(
        self, chain_id: str | None = None, extraction_status: str | None = None
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if chain_id:
            where.append("chain_id = ?")
            params.append(chain_id)
        if extraction_status:
            where.append("extraction_status = ?")
            params.append(extraction_status.upper())
        sql = "SELECT * FROM historical_source_documents"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY COALESCE(publication_date, retrieved_at) DESC, id DESC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def create_validation_task(self, task: ValidationTask) -> int:
        with self.database.connect() as db:
            usefulness_score = task.usefulness_score
            if usefulness_score <= 0:
                if task.raw_observation_id is not None:
                    raw = db.execute("SELECT raw_name FROM raw_observations WHERE id = ?", (task.raw_observation_id,)).fetchone()
                    usefulness_score = float(
                        db.execute(
                            "SELECT COUNT(*) FROM raw_observations WHERE raw_name = ?",
                            (raw["raw_name"],),
                        ).fetchone()[0]
                    ) if raw else 1.0
                elif task.candidate_product_id is not None:
                    usefulness_score = float(
                        db.execute(
                            "SELECT COUNT(*) FROM raw_observations WHERE canonical_product_id = ?",
                            (task.candidate_product_id,),
                        ).fetchone()[0]
                    )
                usefulness_score = max(1.0, usefulness_score)
            now = self._timestamp(task.created_at) or self._now()
            cursor = db.execute(
                """
                INSERT INTO validation_tasks (
                    task_type, raw_observation_id, candidate_product_id, payload_json,
                    status, usefulness_score, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_type.upper(),
                    task.raw_observation_id,
                    task.candidate_product_id,
                    json.dumps(task.payload, ensure_ascii=False) if task.payload is not None else None,
                    task.status.upper(),
                    usefulness_score,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_validation_tasks(self, status: str = "OPEN", limit: int = 50) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    """
                    SELECT * FROM validation_tasks
                    WHERE status = ?
                    ORDER BY usefulness_score DESC, created_at, id
                    LIMIT ?
                    """,
                    (status.upper(), limit),
                )
            ]

    def record_validation_answer(self, answer: ValidationAnswer) -> int:
        if not answer.contributor_id.strip():
            raise ValueError("Contributor identity is required for independent validation")
        with self.database.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO validation_answers (
                    validation_task_id, contributor_id, contributor_role, answer, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(validation_task_id, contributor_id) DO UPDATE SET
                    contributor_role=excluded.contributor_role,
                    answer=excluded.answer,
                    created_at=excluded.created_at
                """,
                (
                    answer.validation_task_id,
                    answer.contributor_id,
                    answer.contributor_role.upper(),
                    answer.answer.upper(),
                    self._timestamp(answer.created_at) or self._now(),
                ),
            )
            row = db.execute(
                """
                SELECT id FROM validation_answers
                WHERE validation_task_id = ? AND contributor_id = ?
                """,
                (answer.validation_task_id, answer.contributor_id),
            ).fetchone()
            return int(row["id"] if row else cursor.lastrowid)

    def validation_answers(self, task_id: int) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM validation_answers WHERE validation_task_id = ? ORDER BY created_at, id",
                    (task_id,),
                )
            ]

    def set_validation_task_status(self, task_id: int, status: str) -> None:
        with self.database.connect() as db:
            now = self._now()
            db.execute(
                """
                UPDATE validation_tasks
                SET status = ?, updated_at = ?, resolved_at = CASE WHEN ? IN ('CONFIRMED', 'REJECTED', 'NEEDS_REVIEW')
                    THEN ? ELSE NULL END
                WHERE id = ?
                """,
                (status.upper(), now, status.upper(), now, task_id),
            )

    def add_basket_item(self, query: str, quantity: int = 1) -> None:
        with self.database.connect() as db:
            db.execute(
                "INSERT INTO basket_items (query, quantity, created_at) VALUES (?, ?, ?)",
                (query, quantity, self._now()),
            )

    def list_basket_items(self) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM basket_items ORDER BY created_at, id")
            ]

    def clear_basket(self) -> None:
        with self.database.connect() as db:
            db.execute("DELETE FROM basket_items")

    def latest_sync_label(self) -> str | None:
        with self.database.connect() as db:
            row = db.execute(
                "SELECT MAX(finished_at) AS latest FROM scrape_runs WHERE finished_at IS NOT NULL"
            ).fetchone()
            return row["latest"] if row and row["latest"] else None

    def diagnostics(self) -> dict[str, Any]:
        with self.database.connect() as db:
            stores = [dict(row) for row in db.execute("SELECT * FROM stores ORDER BY name")]
            runs = [
                dict(row)
                for row in db.execute(
                    """
                    SELECT sr.*
                    FROM scrape_runs sr
                    JOIN (
                        SELECT store_id, MAX(started_at) AS started_at
                        FROM scrape_runs
                        GROUP BY store_id
                    ) latest
                      ON latest.store_id = sr.store_id
                     AND latest.started_at = sr.started_at
                    ORDER BY sr.store_id
                    """
                )
            ]
            counts = {
                row["store_id"]: row["count"]
                for row in db.execute(
                    "SELECT store_id, COUNT(*) AS count FROM offers GROUP BY store_id"
                )
            }
            merchant_count = db.execute("SELECT COUNT(*) AS count FROM merchants").fetchone()[
                "count"
            ]
            total_offer_count = db.execute("SELECT COUNT(*) AS count FROM offers").fetchone()[
                "count"
            ]
            food_values = category_filter_values(None)
            food_offer_count = db.execute(
                f"SELECT COUNT(*) AS count FROM offers WHERE category IN ({','.join('?' for _ in food_values)})",
                food_values,
            ).fetchone()["count"]
            community_sync = [
                dict(row)
                for row in db.execute("SELECT * FROM community_sync_state ORDER BY source")
            ]
        source_statuses = self._source_statuses(runs, counts)
        return {
            "stores": stores,
            "last_runs": runs,
            "offer_counts": counts,
            "merchant_count": merchant_count,
            "total_offer_count": total_offer_count,
            "food_offer_count": food_offer_count,
            "community_sync": community_sync,
            "source_statuses": source_statuses,
            "database_writable": self._database_writable(),
            "app_smoke": app_smoke_check(self.database.path.parent / "cache"),
        }

    def diagnostics_summary(self) -> dict[str, Any]:
        """Return a compact diagnostics shape for the Settings screen."""

        diagnostics = self.diagnostics()
        smoke = diagnostics["app_smoke"]
        sources = diagnostics["source_statuses"]
        return {
            "store_count": len(sources),
            "live_store_count": sum(item["availability"] == "live" for item in sources),
            "total_offer_count": diagnostics["total_offer_count"],
            "food_offer_count": diagnostics["food_offer_count"],
            "merchant_count": diagnostics["merchant_count"],
            "last_sync": self.latest_sync_label(),
            "cache_writable": smoke["cache_directory_writable"],
            "translation_service": smoke["translation_service"],
            "database_writable": diagnostics["database_writable"],
            "last_scraper_runs": sources,
        }

    def source_statuses(self) -> list[dict[str, Any]]:
        """Return source capability and latest scraper state for transparent UI."""

        return self.diagnostics()["source_statuses"]

    def _source_statuses(
        self,
        runs: list[dict[str, Any]],
        offer_counts: dict[str, int],
    ) -> list[dict[str, Any]]:
        by_store = {run["store_id"]: run for run in runs}
        return [
            {
                **source,
                "offer_count": offer_counts.get(source["id"], 0),
                "last_run": by_store.get(source["id"]),
            }
            for source in SOURCE_STATUS_CONFIG
        ]

    def _database_writable(self) -> bool:
        try:
            with self.database.connect() as db:
                db.execute("UPDATE user_preferences SET updated_at = updated_at WHERE 1 = 0")
            return True
        except (OSError, sqlite3.Error):
            return False

    def add_merchant(self, merchant: Merchant) -> str:
        now = self._now()
        created = (merchant.created_at.isoformat(timespec="seconds") if merchant.created_at else now)
        updated = (merchant.updated_at.isoformat(timespec="seconds") if merchant.updated_at else now)
        with self.database.connect() as db:
            db.execute(
                """
                INSERT INTO merchants (
                    id, name, merchant_type, chain_id, latitude, longitude,
                    address, city, neighborhood, phone, website, opening_hours_json,
                    payment_cash, payment_card, community_added, claimed_by_merchant,
                    verification_status, source_type, source_id, osm_type, osm_id,
                    osm_tags_json, source_last_seen_at, merchant_last_verified_at,
                    description, photo_path, community_status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    merchant_type=excluded.merchant_type,
                    chain_id=excluded.chain_id,
                    latitude=excluded.latitude,
                    longitude=excluded.longitude,
                    address=excluded.address,
                    city=excluded.city,
                    neighborhood=excluded.neighborhood,
                    phone=excluded.phone,
                    website=excluded.website,
                    opening_hours_json=excluded.opening_hours_json,
                    payment_cash=excluded.payment_cash,
                    payment_card=excluded.payment_card,
                    community_added=excluded.community_added,
                    claimed_by_merchant=excluded.claimed_by_merchant,
                    verification_status=excluded.verification_status,
                    source_type=excluded.source_type,
                    source_id=excluded.source_id,
                    osm_type=excluded.osm_type,
                    osm_id=excluded.osm_id,
                    osm_tags_json=excluded.osm_tags_json,
                    source_last_seen_at=excluded.source_last_seen_at,
                    merchant_last_verified_at=excluded.merchant_last_verified_at,
                    description=excluded.description,
                    photo_path=excluded.photo_path,
                    community_status=excluded.community_status,
                    updated_at=excluded.updated_at
                """,
                (
                    merchant.id,
                    merchant.name,
                    merchant.merchant_type,
                    merchant.chain_id,
                    merchant.latitude,
                    merchant.longitude,
                    merchant.address,
                    merchant.city,
                    merchant.neighborhood,
                    merchant.phone,
                    merchant.website,
                    json.dumps(merchant.opening_hours) if merchant.opening_hours else None,
                    self._optional_bool(merchant.payment_cash),
                    self._optional_bool(merchant.payment_card),
                    int(merchant.community_added),
                    int(merchant.claimed_by_merchant),
                    merchant.verification_status,
                    merchant.source_type,
                    merchant.source_id,
                    merchant.osm_type,
                    merchant.osm_id,
                    json.dumps(merchant.osm_tags) if merchant.osm_tags else None,
                    self._timestamp(merchant.source_last_seen_at),
                    self._timestamp(merchant.merchant_last_verified_at),
                    merchant.description,
                    merchant.photo_path,
                    merchant.community_status,
                    created,
                    updated,
                ),
            )
        return merchant.id

    def list_merchants(self) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM merchants ORDER BY name")]

    def get_merchant(self, merchant_id: str) -> dict[str, Any] | None:
        with self.database.connect() as db:
            row = db.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,)).fetchone()
            return dict(row) if row else None

    def get_merchant_by_source(self, source_type: str, source_id: str) -> dict[str, Any] | None:
        with self.database.connect() as db:
            row = db.execute(
                "SELECT * FROM merchants WHERE source_type = ? AND source_id = ? LIMIT 1",
                (source_type, source_id),
            ).fetchone()
            return dict(row) if row else None

    def find_merchants_in_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        merchant_types: tuple[str, ...] | list[str] | None = None,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        """Return cached merchants in an inclusive map viewport query."""

        where = ["latitude >= ?", "latitude <= ?", "longitude >= ?", "longitude <= ?"]
        params: list[Any] = [min_lat, max_lat, min_lon, max_lon]
        if merchant_types:
            where.append(f"merchant_type IN ({','.join('?' for _ in merchant_types)})")
            params.extend(merchant_types)
        params.append(limit)
        sql = f"""
            SELECT * FROM merchants
            WHERE {' AND '.join(where)}
            ORDER BY CASE WHEN community_added = 1 THEN 0 ELSE 1 END, name
            LIMIT ?
        """
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def add_pantry_item(
        self,
        raw_name: str,
        quantity: float | None = None,
        unit: str | None = None,
        expires_at: datetime | None = None,
    ) -> int:
        normalized = normalize_product_name(raw_name)
        with self.database.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO pantry_items (
                    raw_name, normalized_name, quantity, unit, expires_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_name,
                    normalized.normalized_name,
                    quantity if quantity is not None else normalized.quantity,
                    unit or normalized.unit,
                    expires_at.isoformat(timespec="seconds") if expires_at else None,
                    self._now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_pantry_items(self) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM pantry_items ORDER BY created_at, id")
            ]

    def clear_pantry(self) -> None:
        with self.database.connect() as db:
            db.execute("DELETE FROM pantry_items")

    def upsert_recipe(self, recipe: Recipe) -> int:
        now = self._now()
        with self.database.connect() as db:
            db.execute(
                """
                INSERT INTO recipes (
                    slug, title, cuisine, servings, instructions_json, source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title=excluded.title,
                    cuisine=excluded.cuisine,
                    servings=excluded.servings,
                    instructions_json=excluded.instructions_json,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (
                    recipe.slug,
                    recipe.title,
                    recipe.cuisine,
                    recipe.servings,
                    json.dumps(list(recipe.instructions)),
                    recipe.source,
                    now,
                    now,
                ),
            )
            recipe_id = int(
                db.execute("SELECT id FROM recipes WHERE slug = ?", (recipe.slug,)).fetchone()[
                    "id"
                ]
            )
            db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
            db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
            for ingredient in recipe.ingredients:
                normalized = normalize_product_name(ingredient.raw_name)
                db.execute(
                    """
                    INSERT INTO recipe_ingredients (
                        recipe_id, raw_name, normalized_name, quantity, unit, required
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recipe_id,
                        ingredient.raw_name,
                        ingredient.normalized_name or normalized.normalized_name,
                        ingredient.quantity if ingredient.quantity is not None else normalized.quantity,
                        ingredient.unit or normalized.unit,
                        int(ingredient.required),
                    ),
                )
            for tag in recipe.tags:
                db.execute(
                    "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?, ?)",
                    (recipe_id, tag),
                )
            return recipe_id

    def list_recipes(self) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM recipes ORDER BY title")]

    def recipe_ingredients(self, recipe_id: int) -> list[RecipeIngredient]:
        with self.database.connect() as db:
            return [
                RecipeIngredient(
                    id=row["id"],
                    raw_name=row["raw_name"],
                    normalized_name=row["normalized_name"],
                    quantity=row["quantity"],
                    unit=row["unit"],
                    required=bool(row["required"]),
                )
                for row in db.execute(
                    "SELECT * FROM recipe_ingredients WHERE recipe_id = ? ORDER BY id",
                    (recipe_id,),
                )
            ]

    def record_quality_observation(self, observation: QualityObservation) -> int:
        with self.database.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO quality_observations (
                    product_id, merchant_id, observed_at, taste_score, freshness_score,
                    appearance_score, value_score, comment, confidence, confirmation_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.product_id,
                    observation.merchant_id,
                    observation.observed_at.isoformat(timespec="seconds"),
                    observation.taste_score,
                    observation.freshness_score,
                    observation.appearance_score,
                    observation.value_score,
                    observation.comment,
                    observation.confidence,
                    observation.confirmation_count,
                ),
            )
            return int(cursor.lastrowid)

    def list_quality_observations(
        self, product_id: int | None = None, merchant_id: str | None = None
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if product_id is not None:
            where.append("product_id = ?")
            params.append(product_id)
        if merchant_id is not None:
            where.append("merchant_id = ?")
            params.append(merchant_id)
        sql = "SELECT * FROM quality_observations"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY observed_at DESC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def record_origin_observation(self, observation: OriginObservation) -> int:
        with self.database.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO origin_observations (
                    product_id, merchant_id, raw_name, normalized_name, country, region,
                    producer, source, confidence, observed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.product_id,
                    observation.merchant_id,
                    observation.raw_name,
                    observation.normalized_name,
                    observation.country,
                    observation.region,
                    observation.producer,
                    observation.source,
                    observation.confidence,
                    observation.observed_at.isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def list_origin_observations(self, product_id: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM origin_observations"
        params: list[Any] = []
        if product_id is not None:
            sql += " WHERE product_id = ?"
            params.append(product_id)
        sql += " ORDER BY observed_at DESC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def origin_observations_for_offer(self, offer: Offer) -> list[OriginObservation]:
        product_id = self.find_product_id_for_offer(offer)
        if product_id is None:
            return []
        return [
            OriginObservation(
                product_id=row["product_id"],
                merchant_id=row["merchant_id"],
                raw_name=row["raw_name"],
                normalized_name=row["normalized_name"],
                country=row["country"],
                region=row["region"],
                producer=row["producer"],
                source=row["source"],
                confidence=row["confidence"],
                observed_at=datetime.fromisoformat(row["observed_at"]),
            )
            for row in self.list_origin_observations(product_id)
        ]

    def record_user_price_observation(self, observation: UserPriceObservation) -> int:
        """Store a local price update without pretending it is a live store price."""

        if observation.price <= 0:
            raise ValueError("Price observations must be greater than zero")
        if not observation.merchant_name.strip():
            raise ValueError("A merchant name is required")
        with self.database.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO user_price_observations (
                    product_id, merchant_id, merchant_name, raw_name, normalized_name,
                    price, quantity, unit, origin_country, origin_region, origin_source,
                    origin_confidence, photo_path, quality, notes, observed_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.product_id,
                    observation.merchant_id,
                    observation.merchant_name.strip(),
                    observation.raw_name,
                    observation.normalized_name,
                    observation.price,
                    observation.quantity,
                    observation.unit,
                    observation.origin_country or None,
                    observation.origin_region or None,
                    observation.origin_source.upper(),
                    observation.origin_confidence.casefold(),
                    observation.photo_path or None,
                    observation.quality or None,
                    observation.notes or None,
                    observation.observed_at.isoformat(timespec="seconds"),
                    self._now(),
                ),
            )
            if observation.origin_country:
                confidence = {
                    "verified": 0.9,
                    "probable": 0.6,
                    "unknown": 0.4,
                }.get(observation.origin_confidence.casefold(), 0.4)
                db.execute(
                    """
                    INSERT INTO origin_observations (
                        product_id, merchant_id, raw_name, normalized_name, country, region,
                        producer, source, confidence, observed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        observation.product_id,
                        observation.merchant_id,
                        observation.raw_name,
                        observation.normalized_name,
                        observation.origin_country,
                        observation.origin_region or None,
                        observation.origin_source.upper(),
                        confidence,
                        observation.observed_at.isoformat(timespec="seconds"),
                    ),
                )
            return int(cursor.lastrowid)

    def list_user_price_observations(
        self,
        product_id: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM user_price_observations"
        params: list[Any] = []
        if product_id is not None:
            sql += " WHERE product_id = ?"
            params.append(product_id)
        sql += " ORDER BY observed_at DESC, id DESC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def record_merchant_product_observation(self, observation: MerchantProductObservation) -> int:
        """Store local product evidence for a place, with price intentionally optional."""

        if not observation.merchant_id:
            raise ValueError("A merchant is required")
        if not observation.raw_name.strip():
            raise ValueError("A product name is required")
        if observation.price is not None and observation.price <= 0:
            raise ValueError("Price observations must be greater than zero")
        with self.database.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO merchant_product_observations (
                    product_id, merchant_id, raw_name, normalized_name, price, quantity, unit,
                    origin_country, origin_region, origin_source, origin_confidence, photo_path,
                    quality, notes, observed_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.product_id,
                    observation.merchant_id,
                    observation.raw_name.strip(),
                    observation.normalized_name,
                    observation.price,
                    observation.quantity,
                    observation.unit or None,
                    observation.origin_country or None,
                    observation.origin_region or None,
                    observation.origin_source.upper(),
                    observation.origin_confidence.casefold(),
                    observation.photo_path or None,
                    observation.quality or None,
                    observation.notes or None,
                    observation.observed_at.isoformat(timespec="seconds"),
                    self._now(),
                ),
            )
            return int(cursor.lastrowid)

    def latest_product_evidence(self, product_id: int) -> dict[str, dict[str, Any]]:
        """Return the newest known observation per merchant for map product mode."""

        sql = """
            SELECT merchant_id, product_id, raw_name, normalized_name, price, quantity, unit,
                   origin_country, origin_region, origin_source, origin_confidence, photo_path,
                   quality, notes, observed_at, 'user_price' AS evidence_type
            FROM user_price_observations
            WHERE product_id = ? AND merchant_id IS NOT NULL
            UNION ALL
            SELECT merchant_id, product_id, raw_name, normalized_name, price, quantity, unit,
                   origin_country, origin_region, origin_source, origin_confidence, photo_path,
                   quality, notes, observed_at, 'merchant_product' AS evidence_type
            FROM merchant_product_observations
            WHERE product_id = ?
            ORDER BY observed_at DESC, evidence_type ASC
        """
        newest: dict[str, dict[str, Any]] = {}
        with self.database.connect() as db:
            for row in db.execute(sql, (product_id, product_id)):
                item = dict(row)
                newest.setdefault(item["merchant_id"], item)
        return newest

    def list_merchant_product_observations(
        self, product_id: int | None = None, merchant_id: str | None = None
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if product_id is not None:
            where.append("product_id = ?")
            params.append(product_id)
        if merchant_id is not None:
            where.append("merchant_id = ?")
            params.append(merchant_id)
        sql = "SELECT * FROM merchant_product_observations"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY observed_at DESC, id DESC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def record_merchant_report(self, report: MerchantReport) -> int:
        """Keep community place reports locally pending a future server workflow."""

        if not report.merchant_id or not report.report_type:
            raise ValueError("Merchant and report type are required")
        with self.database.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO merchant_reports (merchant_id, report_type, notes, reported_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    report.merchant_id,
                    report.report_type,
                    report.notes or None,
                    report.reported_at.isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def list_merchant_reports(self, merchant_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM merchant_reports WHERE merchant_id = ? ORDER BY reported_at DESC",
                    (merchant_id,),
                )
            ]

    def set_preference(self, key: str, value: Any) -> None:
        with self.database.connect() as db:
            db.execute(
                """
                INSERT INTO user_preferences (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """,
                (key, json.dumps(value), self._now()),
            )

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self.database.connect() as db:
            row = db.execute(
                "SELECT value_json FROM user_preferences WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value_json"])
        except json.JSONDecodeError:
            return default

    def _resolve_product_id(self, db, product_id: int) -> int:
        """Follow active merge links without changing the original evidence owner."""

        seen: set[int] = set()
        current = product_id
        while current not in seen:
            seen.add(current)
            row = db.execute(
                """
                SELECT target_product_id FROM product_merges
                WHERE source_product_id = ? AND undone_at IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                (current,),
            ).fetchone()
            if not row:
                return current
            current = int(row["target_product_id"])
        raise ValueError("Product merge cycle detected")

    def _merged_product_ids(self, db, root_product_id: int) -> list[int]:
        rows = db.execute(
            """
            WITH RECURSIVE merged_products(id) AS (
                SELECT ?
                UNION
                SELECT m.source_product_id
                FROM product_merges m
                JOIN merged_products p ON m.target_product_id = p.id
                WHERE m.undone_at IS NULL
            )
            SELECT id FROM merged_products
            """,
            (root_product_id,),
        )
        return [int(row["id"]) for row in rows]

    def _now(self) -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def _timestamp(self, value: datetime | None) -> str | None:
        return value.isoformat(timespec="seconds") if value else None

    def _optional_bool(self, value: bool | None) -> int | None:
        return None if value is None else int(value)
