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
  -> scraper adapter
  -> raw Offer evidence
  -> deterministic normalization
  -> SQLite current offers + price history
  -> services
  -> Kivy UI
```

Scrapers are independent. A broken scraper returns `failed` or `partial` and must not prevent other sources from syncing.

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
