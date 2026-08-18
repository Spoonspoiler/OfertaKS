# Data Model

## Core Principle

Raw scraped and community observation data is evidence. It must be retained and enriched, not overwritten by normalization.

## Primary Tables

- `chains`: supermarket chains such as Viva Fresh, Interex, and ETC.
- `merchants`: concrete places with coordinates, merchant type, optional chain, verification state, and payment/opening-hour metadata.
- `stores`: scraper source compatibility table.
- `offers`: current scraped offers, optionally linked to merchant and chain.
- `products`: canonical products generated from deterministic normalization.
- `product_aliases`: observed store wording mapped to canonical products.
- `price_history`: append-only observations from syncs.
- `pantry_items`: local user-owned food.
- `recipes`, `recipe_ingredients`, `recipe_tags`: local recipe library.
- `merchant_price_observations`: manual/community price evidence.
- `user_price_observations`: local user-entered price updates, including a merchant name, optional merchant ID, optional photo path, origin provenance/confidence, quality, notes, and timestamp. These are not live scraped offers and are not synchronized yet.
- `quality_observations`: product + merchant + time quality evidence.
- `origin_observations`: product origin evidence with source and confidence.
- `community_sync_state`: optional future server sync state.
- `user_preferences`: local settings.

## Origin

Merchant location never implies product origin. Origin requires evidence such as store labels, packaging, flyer text, merchant claims, official data, or user observations.

## Food Catalog Policy

The main Home, Offers, and Search views are food-only. Food categories are detected deterministically from normalized product/source text: Fruits & Vegetables, Dairy, Meat & Fish, Pantry, Drinks, Bakery, Frozen, Snacks, and Other Food. Legacy `FOOD` values are shown under Pantry. Household, hygiene, baby, and unknown categories remain stored but hidden from default browsing; domain services can request the full retained catalog where appropriate.

## Freshness

Community prices have conceptual freshness. Fruit and vegetable prices become stale faster than packaged goods.
