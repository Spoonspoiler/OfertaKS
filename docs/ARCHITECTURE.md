# Architecture

OfertaKS is local-first. The Android app should remain useful when the network or future community server is unavailable.

## Current Shape

The current repository is a flat mobile app rather than the future monorepo layout. The code is organized so it can later move under `mobile/` with minimal changes.

```text
ofertaks/
  app/
  models/
  scrapers/
  parsing/
  normalization/
  product_sources/
  database/
  services/
  recipes/
  routing/
  maps/
  community/
  ui/
  utils/
tests/
```

## Data Flow

```text
public sources
  -> scraper / archive / official-source adapter
  -> immutable raw observation or source document
  -> deterministic normalization
  -> canonical product, aliases, and reversible merge links
  -> SQLite current offers + historical price archive
  -> services
  -> Kivy UI
```

Scrapers are independent. A broken scraper returns `failed` or `partial` and must not prevent other sources from syncing.

## Product Knowledge And History

`products` represents a purchasable canonical identity rather than a loose display name. Brand, manufacturer, producer, distributor, family, variant, pack size, GTIN, packaging, origin, and official references are kept as distinct fields when evidence supports them. Observed retailer wording stays in `product_aliases`, scoped to the most specific available merchant, chain, or store context.

`raw_observations` and `historical_source_documents` preserve retrieved evidence. They are append-only: matching may be confirmed later, but the original text, price, date, source, and document reference are not rewritten. Product consolidation uses a merge record and can be undone without moving the evidence rows.

`product_sources` and `product_attribute_evidence` make official-source enrichment traceable. Conflicting fields create validation work instead of silently replacing known values. Historical discovery starts at 2025-01-01 and only records metadata or evidence provided by an explicit adapter; OCR and bulk crawling are deliberately outside this layer.

## Price Integrity

`promotion_events` stores a merchant or chain advertising claim independently from `price_history`. A promotion can have an advertised reference price, discount amount/percentage, validity dates, raw source text, source URL/document, scope, and confidence. It is deduplicated but never treated as proof that the advertised reduction is a good price.

`HistoricalPriceStatsService` queries exact canonical identities only and computes bounded 30/90/365-day and all-time statistics. `PriceIntegrityService` compares the current package or compatible unit price with a stable regular-price reference. It produces a consumer-facing primary status and separate warnings. Three observations are the minimum for a historical claim. Package changes use unit pricing; products of a different size, variant, family, or category are not mixed into direct history.

`MerchantDealSummaryService` reads bounded, fresh current observations for the visible map merchants. It has no partner, revenue, sponsored, or chain-size input. Chain-level events may inform an associated chain offer, but they never become a concrete branch price without branch-specific evidence.

## Location Model

Merchant/place is the fundamental entity. A chain is an attribute. `stores` exists for scraper compatibility and should not become the primary real-world model.

```text
chain: Viva Fresh
  merchant: Viva Fresh Ulpiana
  merchant: Viva Fresh Dardania
```

Offers may initially have `merchant_id = NULL` when a chain-level flyer does not identify a branch. Community prices and local shops should attach to concrete merchants.

## Prishtina Map Scope

The initial active market is `prishtina`: its center, bounding box, default zoom, and discovery radius live in `ofertaks/maps/region.py`. This is intentionally a city-and-immediate-surroundings scope, not a Kosovo-wide index.

```text
OSM tiles -> configurable basemap provider -> Kivy map surface
OSM bounded importer -> SQLite merchants -> OfertaKS map overlay
community / scraper evidence -> SQLite observations -> price, origin, quality, freshness card
```

The basemap is not OfertaKS data. The overlay owns merchant provenance, optional product evidence, price history, origin, quality, reports, and future routes. Normal browsing queries SQLite by viewport; the OSM importer is a single user-triggered bounded request and can move to a server importer later. Only identical source IDs are automatically updated; other potential duplicates retain a confidence decision for review.

## Local Decision Engine

The app is being extended around:

- cached prices and price history
- merchant distance
- pantry contents
- recipe matching
- basket optimization
- community price freshness
- origin provenance
- quality observations

Recommendations must expose reasoning and avoid silent substitutions.
