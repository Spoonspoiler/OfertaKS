"""SQLite schema for OfertaKS."""

SCHEMA_VERSION = 3

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stores (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    website TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_successful_sync TEXT
);

CREATE TABLE IF NOT EXISTS chains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    website TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS merchants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    merchant_type TEXT NOT NULL,
    chain_id TEXT REFERENCES chains(id),
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    city TEXT,
    neighborhood TEXT,
    phone TEXT,
    website TEXT,
    opening_hours_json TEXT,
    payment_cash INTEGER,
    payment_card INTEGER,
    community_added INTEGER NOT NULL DEFAULT 0,
    claimed_by_merchant INTEGER NOT NULL DEFAULT 0,
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
    merchant_id TEXT REFERENCES merchants(id),
    chain_id TEXT REFERENCES chains(id),
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
    origin_country TEXT,
    origin_region TEXT,
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

CREATE TABLE IF NOT EXISTS pantry_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    quantity REAL,
    unit TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    cuisine TEXT,
    servings INTEGER NOT NULL DEFAULT 1,
    instructions_json TEXT,
    source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    quantity REAL,
    unit TEXT,
    required INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS recipe_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    UNIQUE(recipe_id, tag)
);

CREATE TABLE IF NOT EXISTS merchant_price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity REAL,
    unit TEXT,
    observed_at TEXT NOT NULL,
    submitter_id TEXT,
    photo_path TEXT,
    origin_country TEXT,
    confidence REAL NOT NULL DEFAULT 0.5,
    confirmation_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS user_price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    merchant_id TEXT REFERENCES merchants(id),
    merchant_name TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    price REAL NOT NULL CHECK(price > 0),
    quantity REAL,
    unit TEXT,
    origin_country TEXT,
    origin_region TEXT,
    origin_source TEXT NOT NULL DEFAULT 'UNKNOWN',
    origin_confidence TEXT NOT NULL DEFAULT 'unknown',
    photo_path TEXT,
    quality TEXT,
    notes TEXT,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    observed_at TEXT NOT NULL,
    taste_score REAL,
    freshness_score REAL,
    appearance_score REAL,
    value_score REAL,
    comment TEXT,
    photo_path TEXT,
    confidence REAL NOT NULL DEFAULT 0.5,
    confirmation_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS origin_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    merchant_id TEXT REFERENCES merchants(id),
    raw_name TEXT,
    normalized_name TEXT,
    country TEXT NOT NULL,
    region TEXT,
    producer TEXT,
    source TEXT NOT NULL DEFAULT 'UNKNOWN',
    confidence REAL NOT NULL DEFAULT 0.4,
    observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_sync_state (
    source TEXT PRIMARY KEY,
    last_attempt_at TEXT,
    last_success_at TEXT,
    status TEXT NOT NULL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_offers_store ON offers(store_id);
CREATE INDEX IF NOT EXISTS idx_offers_normalized ON offers(normalized_name);
CREATE INDEX IF NOT EXISTS idx_offers_raw ON offers(raw_name);
CREATE INDEX IF NOT EXISTS idx_offers_category ON offers(category);
CREATE INDEX IF NOT EXISTS idx_price_history_product ON price_history(product_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_price_history_store ON price_history(store_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_aliases_lookup ON product_aliases(normalized_name);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_store ON scrape_runs(store_id, started_at);
CREATE INDEX IF NOT EXISTS idx_merchants_location ON merchants(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_merchants_type ON merchants(merchant_type);
CREATE INDEX IF NOT EXISTS idx_merchants_chain ON merchants(chain_id);
CREATE INDEX IF NOT EXISTS idx_pantry_normalized ON pantry_items(normalized_name);
CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_lookup ON recipe_ingredients(normalized_name);
CREATE INDEX IF NOT EXISTS idx_merchant_price_freshness
ON merchant_price_observations(merchant_id, normalized_name, observed_at);
CREATE INDEX IF NOT EXISTS idx_user_price_product
ON user_price_observations(product_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_quality_product_merchant
ON quality_observations(product_id, merchant_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_origin_product
ON origin_observations(product_id, observed_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_unique
ON products (
    canonical_name,
    COALESCE(brand, ''),
    COALESCE(quantity, -1),
    COALESCE(unit, '')
);
"""

OFFER_MIGRATION_COLUMNS = {
    "merchant_id": "TEXT REFERENCES merchants(id)",
    "chain_id": "TEXT REFERENCES chains(id)",
    "origin_country": "TEXT",
    "origin_region": "TEXT",
}

POST_MIGRATION_SQL = """
CREATE INDEX IF NOT EXISTS idx_offers_merchant ON offers(merchant_id);
CREATE INDEX IF NOT EXISTS idx_offers_chain ON offers(chain_id);
"""
