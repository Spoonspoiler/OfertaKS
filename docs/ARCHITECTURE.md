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
