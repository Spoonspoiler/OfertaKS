# Changelog

## Unreleased

### Added

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

### Known Limits

- Android APK generation is configured for GitHub Actions; the first GitHub run still needs to validate the remote build.
- Community server is documented but not implemented.
- Map rendering and Android location permissions are intentionally deferred.
