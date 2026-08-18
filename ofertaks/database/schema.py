"""SQLite schema for OfertaKS."""

SCHEMA_VERSION = 6

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
    source_type TEXT NOT NULL DEFAULT 'UNKNOWN',
    source_id TEXT,
    osm_type TEXT,
    osm_id TEXT,
    osm_tags_json TEXT,
    source_last_seen_at TEXT,
    merchant_last_verified_at TEXT,
    description TEXT,
    photo_path TEXT,
    community_status TEXT NOT NULL DEFAULT 'NOT_COMMUNITY',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    website TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manufacturers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    website TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS producers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    website TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS distributors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    website TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    brand TEXT,
    brand_id INTEGER REFERENCES brands(id),
    manufacturer_id INTEGER REFERENCES manufacturers(id),
    producer_id INTEGER REFERENCES producers(id),
    distributor_id INTEGER REFERENCES distributors(id),
    product_family TEXT,
    variant TEXT,
    quantity REAL,
    unit TEXT,
    packaging TEXT,
    flavor TEXT,
    fat_percentage REAL,
    processing_type TEXT,
    category TEXT,
    origin_country TEXT,
    origin_region TEXT,
    barcode_gtin TEXT,
    official_product_url TEXT,
    official_image_url TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    merged_into_product_id INTEGER REFERENCES products(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_aliases (
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

CREATE TABLE IF NOT EXISTS promotion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    merchant_id TEXT REFERENCES merchants(id),
    chain_id TEXT REFERENCES chains(id),
    promo_price REAL NOT NULL,
    advertised_reference_price REAL,
    advertised_discount_percent REAL,
    advertised_discount_amount REAL,
    valid_from TEXT,
    valid_until TEXT,
    published_at TEXT,
    observed_at TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    source_document_id INTEGER REFERENCES historical_source_documents(id),
    source_url TEXT,
    raw_offer_text TEXT,
    geographic_scope TEXT NOT NULL DEFAULT 'UNKNOWN',
    confidence REAL NOT NULL DEFAULT 0.5,
    dedupe_key TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    store_id TEXT NOT NULL REFERENCES stores(id),
    merchant_id TEXT REFERENCES merchants(id),
    chain_id TEXT REFERENCES chains(id),
    price REAL NOT NULL,
    normal_price REAL,
    unit_price REAL,
    quantity REAL,
    unit TEXT,
    observed_at TEXT NOT NULL,
    valid_from TEXT,
    valid_until TEXT,
    observation_context TEXT NOT NULL DEFAULT 'REGULAR',
    promotion_event_id INTEGER REFERENCES promotion_events(id),
    raw_observation_id INTEGER,
    source_type TEXT,
    confidence_state TEXT
);

CREATE TABLE IF NOT EXISTS historical_source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id TEXT REFERENCES chains(id),
    merchant_id TEXT REFERENCES merchants(id),
    store_id TEXT REFERENCES stores(id),
    source_type TEXT NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT,
    publication_date TEXT,
    valid_from TEXT,
    valid_until TEXT,
    content_hash TEXT,
    retrieved_at TEXT NOT NULL,
    archived_at TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'PENDING',
    raw_metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id TEXT REFERENCES merchants(id),
    chain_id TEXT REFERENCES chains(id),
    store_id TEXT REFERENCES stores(id),
    raw_name TEXT NOT NULL,
    raw_description TEXT,
    raw_price_text TEXT,
    parsed_price REAL,
    raw_quantity_text TEXT,
    source_type TEXT NOT NULL,
    source_url TEXT,
    source_document_id INTEGER REFERENCES historical_source_documents(id),
    valid_from TEXT,
    valid_until TEXT,
    observed_at TEXT,
    image_reference TEXT,
    canonical_product_id INTEGER REFERENCES products(id),
    matching_status TEXT NOT NULL DEFAULT 'UNMATCHED',
    matching_confidence REAL NOT NULL DEFAULT 0.0,
    dedupe_key TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    publisher TEXT NOT NULL,
    url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    last_checked_at TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    confidence REAL NOT NULL DEFAULT 0.0,
    raw_metadata_json TEXT,
    UNIQUE(product_id, url)
);

CREATE TABLE IF NOT EXISTS product_attribute_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    value_text TEXT NOT NULL,
    source_id INTEGER REFERENCES product_sources(id),
    source_type TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    confidence_state TEXT NOT NULL DEFAULT 'UNVERIFIED',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_merges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_product_id INTEGER NOT NULL REFERENCES products(id),
    target_product_id INTEGER NOT NULL REFERENCES products(id),
    reason TEXT,
    created_by TEXT,
    merged_at TEXT NOT NULL,
    undone_at TEXT,
    undone_by TEXT,
    CHECK(source_product_id <> target_product_id)
);

CREATE TABLE IF NOT EXISTS validation_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    raw_observation_id INTEGER REFERENCES raw_observations(id),
    candidate_product_id INTEGER REFERENCES products(id),
    payload_json TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    usefulness_score REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS validation_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validation_task_id INTEGER NOT NULL REFERENCES validation_tasks(id) ON DELETE CASCADE,
    contributor_id TEXT NOT NULL,
    contributor_role TEXT NOT NULL DEFAULT 'CONTRIBUTOR',
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(validation_task_id, contributor_id)
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

CREATE TABLE IF NOT EXISTS merchant_product_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    price REAL,
    quantity REAL,
    unit TEXT,
    origin_country TEXT,
    origin_region TEXT,
    origin_source TEXT NOT NULL DEFAULT 'USER_OBSERVATION',
    origin_confidence TEXT NOT NULL DEFAULT 'unknown',
    photo_path TEXT,
    quality TEXT,
    notes TEXT,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS merchant_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    report_type TEXT NOT NULL,
    notes TEXT,
    reported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
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
CREATE INDEX IF NOT EXISTS idx_raw_observations_product ON raw_observations(canonical_product_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_raw_observations_document ON raw_observations(source_document_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_observations_dedupe
ON raw_observations(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_historical_documents_lookup
ON historical_source_documents(chain_id, publication_date, source_type);
CREATE INDEX IF NOT EXISTS idx_product_sources_product ON product_sources(product_id, status);
CREATE INDEX IF NOT EXISTS idx_product_attribute_evidence_product
ON product_attribute_evidence(product_id, field_name, created_at);
CREATE INDEX IF NOT EXISTS idx_product_merges_source ON product_merges(source_product_id, undone_at);
CREATE INDEX IF NOT EXISTS idx_validation_tasks_priority ON validation_tasks(status, usefulness_score DESC);
CREATE INDEX IF NOT EXISTS idx_validation_answers_task ON validation_answers(validation_task_id, created_at);
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
CREATE INDEX IF NOT EXISTS idx_merchant_product_observation_lookup
ON merchant_product_observations(merchant_id, product_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_merchant_reports_merchant ON merchant_reports(merchant_id, reported_at);
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

CREATE TRIGGER IF NOT EXISTS raw_observations_preserve_evidence
BEFORE UPDATE OF merchant_id, chain_id, store_id, raw_name, raw_description,
                 raw_price_text, parsed_price, raw_quantity_text, source_type,
                 source_url, source_document_id, valid_from, valid_until,
                 observed_at, image_reference, dedupe_key, created_at
ON raw_observations
BEGIN
    SELECT RAISE(ABORT, 'Raw observation evidence is immutable');
END;
"""

OFFER_MIGRATION_COLUMNS = {
    "merchant_id": "TEXT REFERENCES merchants(id)",
    "chain_id": "TEXT REFERENCES chains(id)",
    "origin_country": "TEXT",
    "origin_region": "TEXT",
}

MERCHANT_MIGRATION_COLUMNS = {
    "source_type": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
    "source_id": "TEXT",
    "osm_type": "TEXT",
    "osm_id": "TEXT",
    "osm_tags_json": "TEXT",
    "source_last_seen_at": "TEXT",
    "merchant_last_verified_at": "TEXT",
    "description": "TEXT",
    "photo_path": "TEXT",
    "community_status": "TEXT NOT NULL DEFAULT 'NOT_COMMUNITY'",
}

PRODUCT_MIGRATION_COLUMNS = {
    "brand_id": "INTEGER REFERENCES brands(id)",
    "manufacturer_id": "INTEGER REFERENCES manufacturers(id)",
    "producer_id": "INTEGER REFERENCES producers(id)",
    "distributor_id": "INTEGER REFERENCES distributors(id)",
    "product_family": "TEXT",
    "variant": "TEXT",
    "packaging": "TEXT",
    "flavor": "TEXT",
    "fat_percentage": "REAL",
    "processing_type": "TEXT",
    "origin_country": "TEXT",
    "origin_region": "TEXT",
    "barcode_gtin": "TEXT",
    "official_product_url": "TEXT",
    "official_image_url": "TEXT",
    "active": "INTEGER NOT NULL DEFAULT 1",
    "merged_into_product_id": "INTEGER REFERENCES products(id)",
    "created_at": "TEXT",
    "updated_at": "TEXT",
}

PRICE_HISTORY_MIGRATION_COLUMNS = {
    "merchant_id": "TEXT REFERENCES merchants(id)",
    "chain_id": "TEXT REFERENCES chains(id)",
    "unit_price": "REAL",
    "quantity": "REAL",
    "unit": "TEXT",
    "valid_from": "TEXT",
    "valid_until": "TEXT",
    "observation_context": "TEXT NOT NULL DEFAULT 'REGULAR'",
    "promotion_event_id": "INTEGER",
    "raw_observation_id": "INTEGER",
    "source_type": "TEXT",
    "confidence_state": "TEXT",
}

POST_MIGRATION_SQL = """
CREATE INDEX IF NOT EXISTS idx_offers_merchant ON offers(merchant_id);
CREATE INDEX IF NOT EXISTS idx_offers_chain ON offers(chain_id);
CREATE INDEX IF NOT EXISTS idx_merchants_source ON merchants(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_price_history_raw_observation ON price_history(raw_observation_id);
CREATE INDEX IF NOT EXISTS idx_price_history_merchant ON price_history(merchant_id, product_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_price_history_chain ON price_history(chain_id, product_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_price_history_context ON price_history(product_id, observation_context, observed_at);
CREATE INDEX IF NOT EXISTS idx_promotion_events_product_active
ON promotion_events(canonical_product_id, valid_until, observed_at);
CREATE INDEX IF NOT EXISTS idx_promotion_events_merchant_active
ON promotion_events(merchant_id, valid_until, observed_at);
CREATE INDEX IF NOT EXISTS idx_promotion_events_chain_active
ON promotion_events(chain_id, valid_until, observed_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_promotion_events_dedupe
ON promotion_events(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_aliases_merchant_lookup ON product_aliases(merchant_id, normalized_name);
CREATE INDEX IF NOT EXISTS idx_aliases_chain_lookup ON product_aliases(chain_id, normalized_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_gtin
ON products(barcode_gtin) WHERE barcode_gtin IS NOT NULL;
"""
