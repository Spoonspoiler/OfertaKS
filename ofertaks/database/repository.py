"""Repository layer for SQLite persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from ofertaks.app.config import STORE_CONFIG
from ofertaks.database.database import Database
from ofertaks.models.offer import Offer
from ofertaks.normalization.product_normalizer import normalize_product_name


class Repository:
    def __init__(self, database: Database):
        self.database = database

    def initialize(self) -> None:
        self.database.initialize()
        self.seed_stores()

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
        now = datetime.utcnow().isoformat(timespec="seconds")
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
        now = datetime.utcnow().isoformat(timespec="seconds")
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
                        store_id, raw_name, normalized_name, brand, quantity, unit,
                        normal_price, offer_price, unit_price, discount_percent,
                        category, valid_from, valid_until, source_url, image_url, scraped_at
                    )
                    VALUES (
                        :store_id, :raw_name, :normalized_name, :brand, :quantity, :unit,
                        :normal_price, :offer_price, :unit_price, :discount_percent,
                        :category, :valid_from, :valid_until, :source_url, :image_url, :scraped_at
                    )
                    """,
                    offer.to_record(),
                )
                db.execute(
                    """
                    INSERT OR IGNORE INTO product_aliases (
                        product_id, store_id, raw_name, normalized_name
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (product_id, offer.store_id, offer.raw_name, offer.normalized_name),
                )
                db.execute(
                    """
                    INSERT INTO price_history (
                        product_id, store_id, price, normal_price, observed_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        offer.store_id,
                        offer.offer_price,
                        offer.normal_price,
                        offer.scraped_at.isoformat(timespec="seconds"),
                    ),
                )

    def insert_offer(self, offer: Offer) -> int:
        with self.database.connect() as db:
            product_id = self._upsert_product(db, offer)
            cursor = db.execute(
                """
                INSERT INTO offers (
                    store_id, raw_name, normalized_name, brand, quantity, unit,
                    normal_price, offer_price, unit_price, discount_percent,
                    category, valid_from, valid_until, source_url, image_url, scraped_at
                )
                VALUES (
                    :store_id, :raw_name, :normalized_name, :brand, :quantity, :unit,
                    :normal_price, :offer_price, :unit_price, :discount_percent,
                    :category, :valid_from, :valid_until, :source_url, :image_url, :scraped_at
                )
                """,
                offer.to_record(),
            )
            db.execute(
                """
                INSERT INTO price_history (product_id, store_id, price, normal_price, observed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    offer.store_id,
                    offer.offer_price,
                    offer.normal_price,
                    offer.scraped_at.isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def _upsert_product(self, db, offer: Offer) -> int:
        canonical = normalize_product_name(offer.raw_name, offer.category)
        canonical_name = canonical.normalized_name or offer.normalized_name
        db.execute(
            """
            INSERT OR IGNORE INTO products (canonical_name, brand, quantity, unit, category)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                canonical_name,
                offer.brand or canonical.brand,
                offer.quantity if offer.quantity is not None else canonical.quantity,
                offer.unit or canonical.unit,
                offer.category or canonical.category,
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
                offer.brand or canonical.brand,
                offer.quantity if offer.quantity is not None else canonical.quantity,
                offer.unit or canonical.unit,
            ),
        ).fetchone()
        return int(row["id"])

    def list_offers(
        self,
        store_id: str | None = None,
        category: str | None = None,
        sort: str = "best",
        limit: int | None = 200,
    ) -> list[Offer]:
        where = []
        params: list[Any] = []
        if store_id:
            where.append("o.store_id = ?")
            params.append(store_id)
        if category:
            where.append("o.category = ?")
            params.append(category)
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

    def search_offers(self, query: str, limit: int = 100) -> list[Offer]:
        like = f"%{query.casefold()}%"
        with self.database.connect() as db:
            rows = db.execute(
                """
                SELECT o.*, s.name AS store_name
                FROM offers o
                JOIN stores s ON s.id = o.store_id
                WHERE lower(o.raw_name) LIKE ?
                   OR lower(o.normalized_name) LIKE ?
                   OR lower(COALESCE(o.brand, '')) LIKE ?
                ORDER BY COALESCE(o.unit_price, o.offer_price) ASC
                LIMIT ?
                """,
                (like, like, like, limit),
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

    def price_history(self, product_id: int, days: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM price_history WHERE product_id = ?"
        params: list[Any] = [product_id]
        if days is not None:
            sql += " AND observed_at >= datetime('now', ?)"
            params.append(f"-{days} days")
        sql += " ORDER BY observed_at ASC"
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(sql, params)]

    def add_basket_item(self, query: str, quantity: int = 1) -> None:
        with self.database.connect() as db:
            db.execute(
                "INSERT INTO basket_items (query, quantity, created_at) VALUES (?, ?, ?)",
                (query, quantity, datetime.utcnow().isoformat(timespec="seconds")),
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
            counts = dict(
                db.execute(
                    "SELECT store_id, COUNT(*) AS count FROM offers GROUP BY store_id"
                ).fetchall()
            )
        return {"stores": stores, "last_runs": runs, "offer_counts": counts}
