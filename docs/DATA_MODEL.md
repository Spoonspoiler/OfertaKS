# Data Model

## Core Principle

Raw scraped and community observation data is evidence. It must be retained and enriched, not overwritten by normalization.

## Primary Tables

- `chains`: supermarket chains such as Viva Fresh, Interex, and ETC.
- `merchants`: concrete places with coordinates, merchant type, optional chain, verification state, and payment/opening-hour metadata.
- `stores`: scraper source compatibility table.
- `offers`: current scraped offers, optionally linked to merchant and chain.
- `products`: canonical purchasable identities with structured brand, producer, family, variant, pack, GTIN, packaging, origin, official-reference, active, and reversible-merge fields.
- `brands`, `manufacturers`, `producers`, `distributors`: normalized organization identities linked to a canonical product when evidence supports them.
- `product_aliases`: observed merchant/chain/store wording mapped to canonical products with context, match state, confidence, and evidence reference.
- `raw_observations`: append-only price/name/quantity/source evidence. Original raw fields are immutable; only an evidence-to-product match may be resolved later.
- `historical_source_documents`: historical page, flyer, archive, or document metadata with dates, source context, extraction state, and content identity.
- `price_history`: append-only normalized price facts with observed/valid dates, regular/promotion/community/receipt/shelf-label context, optional merchant/chain scope, package and unit price fields, source/confidence, and links to raw evidence or a promotion event.
- `promotion_events`: deduplicated advertising claims stored separately from price facts, including advertised reference and reduction, price, validity, source/document/URL, merchant or chain scope, raw wording, geographic scope, and confidence.
- `product_sources`, `product_attribute_evidence`: official or structured source provenance and field-level evidence, including conflicts.
- `product_merges`: reversible canonical-product consolidation records; historical evidence keeps its original product link.
- `validation_tasks`, `validation_answers`: contributor/admin data-quality work with independent-answer consensus and explicit unresolved conflicts.
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

## Historical Archive Policy

The archive begins at `2025-01-01`. A historical row is stored only when a scraper, explicit archive adapter, receipt, flyer, or other allowed source supplies it. The app does not infer unavailable historical prices and does not require OCR to record a source document. Exact product identity, same variant in a different size, product family, category equivalence, and unrelated products remain separate relationship levels; only exact identity should be used for direct price history.

## Price Integrity Policy

Commercial promotion labels and observed price facts are different records. OfertaKS evaluates a price only from exact-product history: the median is the default robust reference, with 30/90/365-day and all-time windows and a stable regular-price reference when enough non-promotion observations exist. Compatible unit prices are preferred for package-size comparisons. At least three observations are required; otherwise the only valid state is insufficient history.

Historical analysis assigns one primary status (exceptional deal, good deal, normal price, expensive, very expensive, weak promotion, or insufficient history) and can attach warnings such as recent increase, increase before promotion, advertised-discount mismatch, or unchanged package price with a higher unit price. A current merchant price is branch-specific only when its evidence has that merchant ID. Chain-wide evidence remains chain-wide.
