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
- `quality_observations`: product + merchant + time quality evidence.
- `origin_observations`: product origin evidence with source and confidence.
- `community_sync_state`: optional future server sync state.
- `user_preferences`: local settings.

## Origin

Merchant location never implies product origin. Origin requires evidence such as store labels, packaging, flyer text, merchant claims, official data, or user observations.

## Freshness

Community prices have conceptual freshness. Fruit and vegetable prices become stale faster than packaged goods.
