"""SQLite connection management."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from ofertaks.database.schema import (
    MERCHANT_MIGRATION_COLUMNS,
    OFFER_MIGRATION_COLUMNS,
    POST_MIGRATION_SQL,
    PRICE_HISTORY_MIGRATION_COLUMNS,
    PRODUCT_MIGRATION_COLUMNS,
    SCHEMA_SQL,
    SCHEMA_VERSION,
)
from ofertaks.normalization.gtin import (
    FRESH_BULK_ARTISANAL,
    GTIN_CONFLICT,
    GTIN_NOT_APPLICABLE,
    PROVISIONAL_NO_GTIN,
    VERIFIED_GTIN,
    gtin_type,
    identity_strategy_for,
    validate_gtin,
)


class _ConnectionManager:
    def __init__(self, path: Path):
        self.path = path
        self.connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.connection is None:
            return
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
            self.connection = None


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> _ConnectionManager:
        return _ConnectionManager(self.path)

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            self._migrate_offer_columns(connection)
            self._migrate_merchant_columns(connection)
            self._migrate_product_columns(connection)
            self._migrate_gtin_identity(connection)
            self._migrate_price_history_columns(connection)
            self._migrate_product_aliases(connection)
            self._backfill_legacy_offer_evidence(connection)
            connection.executescript(POST_MIGRATION_SQL)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _migrate_offer_columns(self, connection: sqlite3.Connection) -> None:
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(offers)")
        }
        for column, definition in OFFER_MIGRATION_COLUMNS.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE offers ADD COLUMN {column} {definition}")

    def _migrate_merchant_columns(self, connection: sqlite3.Connection) -> None:
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(merchants)")
        }
        for column, definition in MERCHANT_MIGRATION_COLUMNS.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE merchants ADD COLUMN {column} {definition}")

    def _migrate_product_columns(self, connection: sqlite3.Connection) -> None:
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(products)")}
        for column, definition in PRODUCT_MIGRATION_COLUMNS.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")
        now = datetime.now(UTC).isoformat(timespec="seconds")
        connection.execute("UPDATE products SET active = 1 WHERE active IS NULL")
        connection.execute("UPDATE products SET created_at = ? WHERE created_at IS NULL", (now,))
        connection.execute("UPDATE products SET updated_at = ? WHERE updated_at IS NULL", (now,))
        connection.execute(
            """
            INSERT OR IGNORE INTO brands (name, normalized_name, created_at, updated_at)
            SELECT DISTINCT TRIM(brand), LOWER(TRIM(brand)), ?, ?
            FROM products
            WHERE brand IS NOT NULL AND TRIM(brand) != ''
            """,
            (now, now),
        )
        connection.execute(
            """
            UPDATE products
            SET brand_id = (
                SELECT brands.id FROM brands
                WHERE brands.normalized_name = LOWER(TRIM(products.brand))
            )
            WHERE brand_id IS NULL AND brand IS NOT NULL AND TRIM(brand) != ''
            """
        )

    def _migrate_gtin_identity(self, connection: sqlite3.Connection) -> None:
        """Classify legacy codes without deleting or silently merging any product."""

        connection.execute("DROP INDEX IF EXISTS idx_products_gtin")
        connection.execute("DROP INDEX IF EXISTS idx_products_unique")
        rows = connection.execute(
            "SELECT id, barcode_gtin, category, active, gtin_status FROM products ORDER BY id"
        ).fetchall()
        seen: set[str] = set()
        now = datetime.now(UTC).isoformat(timespec="seconds")
        for row in rows:
            raw_code = row["barcode_gtin"]
            strategy = identity_strategy_for(row["category"], raw_code)
            if not raw_code:
                if row["gtin_status"] == GTIN_CONFLICT:
                    connection.execute(
                        "UPDATE products SET identity_strategy = ? WHERE id = ?",
                        (strategy, row["id"]),
                    )
                    continue
                status = GTIN_NOT_APPLICABLE if strategy == FRESH_BULK_ARTISANAL else PROVISIONAL_NO_GTIN
                connection.execute(
                    "UPDATE products SET gtin_type = 'UNKNOWN', gtin_status = ?, identity_strategy = ? WHERE id = ?",
                    (status, strategy, row["id"]),
                )
                continue
            try:
                code = validate_gtin(raw_code)
            except ValueError:
                connection.execute(
                    "UPDATE products SET gtin_status = ?, gtin_type = 'UNKNOWN', identity_strategy = ? WHERE id = ?",
                    (GTIN_CONFLICT, strategy, row["id"]),
                )
                self._ensure_gtin_validation_task(connection, row["id"], raw_code, "invalid")
                continue
            if code in seen:
                connection.execute(
                    "UPDATE products SET barcode_gtin = ?, gtin_status = ?, gtin_type = ?, identity_strategy = ? WHERE id = ?",
                    (code, GTIN_CONFLICT, gtin_type(code), strategy, row["id"]),
                )
                self._ensure_gtin_validation_task(connection, row["id"], code, "duplicate")
                continue
            seen.add(code)
            connection.execute(
                """
                UPDATE products
                SET barcode_gtin = ?, gtin_type = ?, gtin_status = ?,
                    gtin_verified_at = COALESCE(gtin_verified_at, ?),
                    identity_strategy = ?
                WHERE id = ?
                """,
                (code, gtin_type(code), VERIFIED_GTIN, now, strategy, row["id"]),
            )

    @staticmethod
    def _ensure_gtin_validation_task(
        connection: sqlite3.Connection, product_id: int, value: str, reason: str
    ) -> None:
        payload = f'{{"gtin":"{value}","reason":"{reason}"}}'
        existing = connection.execute(
            """
            SELECT id FROM validation_tasks
            WHERE task_type = 'GTIN_REVIEW' AND candidate_product_id = ? AND payload_json = ?
              AND status = 'OPEN'
            LIMIT 1
            """,
            (product_id, payload),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO validation_tasks (
                    task_type, candidate_product_id, payload_json, status, usefulness_score, created_at, updated_at
                ) VALUES ('GTIN_REVIEW', ?, ?, 'OPEN', 1.0, ?, ?)
                """,
                (
                    product_id,
                    payload,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )

    def _migrate_price_history_columns(self, connection: sqlite3.Connection) -> None:
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(price_history)")}
        for column, definition in PRICE_HISTORY_MIGRATION_COLUMNS.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE price_history ADD COLUMN {column} {definition}")

    def _migrate_product_aliases(self, connection: sqlite3.Connection) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(product_aliases)")}
        if {"merchant_id", "chain_id", "matching_status", "matching_confidence", "created_at"} <= columns:
            return
        connection.execute("DROP INDEX IF EXISTS idx_aliases_lookup")
        connection.execute("ALTER TABLE product_aliases RENAME TO product_aliases_legacy_v5")
        connection.executescript(
            """
            CREATE TABLE product_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                store_id TEXT REFERENCES stores(id),
                merchant_id TEXT REFERENCES merchants(id),
                chain_id TEXT REFERENCES chains(id),
                raw_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                source_context TEXT,
                matching_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                matching_confidence REAL NOT NULL DEFAULT 0.0,
                source_raw_observation_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(store_id, merchant_id, chain_id, raw_name, normalized_name)
            );
            """
        )
        connection.execute(
            """
            INSERT INTO product_aliases (
                id, product_id, store_id, raw_name, normalized_name,
                source_context, matching_status, matching_confidence, created_at
            )
            SELECT id, product_id, store_id, raw_name, normalized_name,
                   'LEGACY_STORE_ALIAS', 'AUTO_MATCHED', 0.75, CURRENT_TIMESTAMP
            FROM product_aliases_legacy_v5
            """
        )
        connection.execute("DROP TABLE product_aliases_legacy_v5")

    def _backfill_legacy_offer_evidence(self, connection: sqlite3.Connection) -> None:
        """Preserve current legacy offers as evidence without inventing missing raw price text."""

        connection.execute(
            """
            INSERT OR IGNORE INTO raw_observations (
                store_id, raw_name, raw_price_text, parsed_price, raw_quantity_text,
                source_type, source_url, observed_at, canonical_product_id,
                matching_status, matching_confidence, dedupe_key, created_at
            )
            SELECT o.store_id, o.raw_name, NULL, o.offer_price, NULL,
                   'LEGACY_SCRAPER', o.source_url, o.scraped_at, a.product_id,
                   'AUTO_MATCHED', 0.75, 'legacy-offer:' || o.id, o.scraped_at
            FROM offers o
            LEFT JOIN product_aliases a
              ON a.store_id = o.store_id
             AND a.raw_name = o.raw_name
             AND a.normalized_name = o.normalized_name
            """
        )
