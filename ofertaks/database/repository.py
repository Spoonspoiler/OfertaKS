"""Repository layer for SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
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
from ofertaks.models.offer import Offer
from ofertaks.models.recipe import Recipe, RecipeIngredient
from ofertaks.normalization.product_normalizer import normalize_product_name
from ofertaks.utils.categories import category_filter_values


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
                INSERT OR IGNORE INTO products (canonical_name, brand, quantity, unit, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    canonical_name,
                    canonical.brand,
                    canonical.quantity,
                    canonical.unit,
                    canonical.category,
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

    def _now(self) -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def _timestamp(self, value: datetime | None) -> str | None:
        return value.isoformat(timespec="seconds") if value else None

    def _optional_bool(self, value: bool | None) -> int | None:
        return None if value is None else int(value)
