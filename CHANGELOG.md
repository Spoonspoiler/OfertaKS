# Changelog

## Unreleased

### Added

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

- Scraped offers now carry a chain identifier when the source represents a known chain.
- Diagnostics include merchant count and community sync state.
- Application data, cache, debug scraper, and SQLite paths now go through centralized portable path helpers.
- English is the fallback UI language.
- Kivy screens and offer cards now bind label text width correctly and constrain desktop layout width to avoid vertical text collapse.

### Known Limits

- Android APK generation is configured for GitHub Actions; the first GitHub run still needs to validate the remote build.
- Community server is documented but not implemented.
- Map rendering and Android location permissions are intentionally deferred.
