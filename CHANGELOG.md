# Changelog

## Unreleased

### Added

- Canonical product knowledge base with normalized organizations, structured purchasable identities, merchant/chain/store aliases, GTIN and source references.
- Append-only raw observation and historical source-document archive starting at 2025-01-01, with reversible product merges, validation tasks, and independent-answer consensus.
- Conservative official product metadata parsing/enrichment with source provenance and conflict evidence, plus promotion analysis based on observed history.
- Food browsing categories and filters for fruit and vegetables, dairy, meat and fish, pantry, drinks, bakery, frozen food, snacks, and other food.
- Local user price-update observations with merchant name, product, quantity/unit, origin provenance/confidence, optional photo path, quality, notes, and timestamp.
- Price-status classification against observed history and transparent source capability statuses for ETC, Viva Fresh, Interex, and Albi.
- Merchant-first SQLite tables for chains, merchants, pantry, recipes, community price observations, quality observations, origin observations, sync state, and preferences.
- Optional `merchant_id`, `chain_id`, `origin_country`, and `origin_region` fields on offers.
- Haversine distance helpers and merchant duplicate detection.
- Pantry and recipe matching with additional-cost estimation from cached offers.
- Community freshness, quality aggregation, and origin provenance helpers.
- Offline tests for merchants, recipes, community observations, scrapers, database, parsing, matching, and basket optimization.
- Root `AGENTS.md` and architecture/development documentation.
- GitHub Actions Android debug APK workflow for Ubuntu/Buildozer builds.
- Central localization package with Albanian, English, and French strings.
- Persistent manual language selection in Settings.
- Windows development dependencies file with pytest.
- Prishtina and immediate-surroundings map scope with a configurable OSM-compatible tile provider, visible attribution, viewport-only tile cache, semantic food merchant markers, and a future route-polyline surface.
- Bounded, user-triggered Overpass importer for real OSM food places with source provenance, raw tags, chain detection, local SQLite caching, and no Kosovo-wide import.
- Expanded chain registry for ETC, Viva Fresh, Interex, Albi Market, Maxi, Meridian Express, Emona Center, and SPAR Kosovo, with honest location-only or not-implemented price source states.
- SQLite merchant bounding-box queries, source indexes, conservative duplicate confidence, community place reports, and price-optional merchant product observations.
- Map-driven local Add place, Add product, and Update price context flows, plus product Search/Product Detail links to Map.
- Price Integrity Engine with append-only normalized price observations, unit-price evidence, independent promotion events, active-promotion deduplication, and source/context/scope metadata.
- Exact-product historical statistics (30/90/365-day and all-time medians, averages, ranges, confidence, and stable references) plus deterministic price-change events.
- Consumer-first deal assessments and merchant summaries for exceptional, good, normal, expensive, very expensive, weak-promotion, insufficient-history, price-increase, discount-mismatch, and package-shrink signals.
- GTIN-first packaged-product identity with check-digit validation, typed GTIN-8/12/13/14 states, safe migration of legacy codes, conflict review tasks, and distinct fresh/bulk identity handling.
- Manual barcode lookup and contribution flow with a platform-neutral future camera-scanner boundary.
- Explicit merchant ownership classifications and a local-first recommendation service that selects only explicitly classified local merchants within a documented price tolerance.

### Changed

- Main browsing and search now default to food-only offers without deleting retained non-food data.
- Offer cards now use an image when available or a category artwork placeholder, and show store, category, price, discount, origin, and history-based price status.
- Product detail now shows comparable current prices, provenance, price history context, and an entry point for a local price update.
- Settings now presents a readable diagnostics summary; the raw diagnostic report is optional and remains copyable.
- Scraped offers now carry a chain identifier when the source represents a known chain.
- Diagnostics include merchant count and community sync state.
- Application data, cache, debug scraper, and SQLite paths now go through centralized portable path helpers.
- English is the fallback UI language.
- Kivy screens and offer cards now bind label text width correctly and constrain desktop layout width to avoid vertical text collapse.
- Prishtina's online basemap now prioritizes tiles nearest the viewport center, keeps unresolved tiles transparent, and retains its local cache for re-visits.
- Price history services now include archived raw evidence and reversible merged identities without double-counting synchronized scraper observations.
- Offer cards, product detail, and the Prishtina map now use historical price integrity instead of advertised discount alone. The map includes Best deals and Price warnings filters and only attributes a current price to a concrete merchant when direct merchant evidence exists.
- Offer-card price verdict caching now includes the actual price and scrape timestamp, preventing two differently priced lines with the same name from borrowing one another's status.
- Product history graphs now plot the observed price fluctuation and mark promotion observations in orange; regular observations remain green.
- Prishtina map markers now show the known chain or merchant name. Selecting a place exposes an `Offers here` action; chain-wide scraper offers are labelled as chain scope rather than represented as branch-specific facts.

### Known Limits

- Android APK generation is configured for GitHub Actions; the first GitHub run still needs to validate the remote build.
- Community server is documented but not implemented.
- Map routing remains an interface only, and location permission is not requested until a reliable current-location feature exists.
- Deal labels are conservative until enough exact-product observations exist; they do not validate promotion claims or chain-wide prices as branch-specific facts without evidence.
- Camera barcode capture is an interface only until it is validated in a real Android build; barcode entry is available now.
