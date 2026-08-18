"""SQLite schema for OfertaKS."""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stores (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    website TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_successful_sync TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    brand TEXT,
    quantity REAL,
    unit TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS product_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    store_id TEXT NOT NULL REFERENCES stores(id),
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    UNIQUE(store_id, raw_name, normalized_name)
);

CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL REFERENCES stores(id),
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    brand TEXT,
    quantity REAL,
    unit TEXT,
    normal_price REAL,
    offer_price REAL NOT NULL,
    unit_price REAL,
    discount_percent REAL,
    category TEXT,
    valid_from TEXT,
    valid_until TEXT,
    source_url TEXT NOT NULL,
    image_url TEXT,
    scraped_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    store_id TEXT NOT NULL REFERENCES stores(id),
    price REAL NOT NULL,
    normal_price REAL,
    observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL REFERENCES stores(id),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    items_found INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS basket_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    target_price REAL,
    created_at TEXT NOT NULL,
    UNIQUE(product_id)
);

CREATE INDEX IF NOT EXISTS idx_offers_store ON offers(store_id);
CREATE INDEX IF NOT EXISTS idx_offers_normalized ON offers(normalized_name);
CREATE INDEX IF NOT EXISTS idx_offers_raw ON offers(raw_name);
CREATE INDEX IF NOT EXISTS idx_offers_category ON offers(category);
CREATE INDEX IF NOT EXISTS idx_price_history_product ON price_history(product_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_price_history_store ON price_history(store_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_aliases_lookup ON product_aliases(normalized_name);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_store ON scrape_runs(store_id, started_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_unique
ON products (
    canonical_name,
    COALESCE(brand, ''),
    COALESCE(quantity, -1),
    COALESCE(unit, '')
);
"""
