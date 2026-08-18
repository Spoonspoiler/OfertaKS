# OfertaKS Agent Guide

OfertaKS is an offline-first Android-capable Python/Kivy app. It is growing from supermarket offer comparison into a local food decision engine for Kosovo.

## Repository Structure

- `main.py`: desktop entrypoint.
- `buildozer.spec`: Android packaging configuration.
- `requirements.txt`: mobile/runtime dependencies.
- `ofertaks/app`: config and localization.
- `ofertaks/models`: dataclasses for offers, products, merchants, pantry, recipes, and observations.
- `ofertaks/scrapers`: store adapters. Scraper code must stay out of UI modules.
- `ofertaks/parsing`: price, unit, date, HTML, and PDF parsing.
- `ofertaks/normalization`: deterministic product/brand matching.
- `ofertaks/product_sources`: source-attributed product parsers and conservative enrichment.
- `ofertaks/database`: SQLite schema, migrations, and repository.
- `ofertaks/services`: sync, basket, history, comparison, and merchant services.
- `ofertaks/recipes`: recipe and pantry matching.
- `ofertaks/routing`: distance helpers.
- `ofertaks/maps`: regional scope, OSM discovery, provider configuration, and map overlay logic.
- `ofertaks/community`: community observation reasoning.
- `ofertaks/ui`: Kivy screens and widgets.
- `tests`: offline unit tests and fixtures.
- `docs`: architecture and development notes.

## Commands

Desktop app:

```powershell
python main.py
```

Tests:

```powershell
pytest -q
```

Android debug build:

Use GitHub Actions on Ubuntu via `.github/workflows/android-debug.yml`. The primary developer environment is Windows; do not require local Linux/WSL for ordinary development.

Server:

No server package exists yet. When added, keep it optional and make the mobile app degrade gracefully when it is unavailable.

Database migrations:

SQLite schema lives in `ofertaks/database/schema.py`. Increment `SCHEMA_VERSION` for structural changes and add safe migrations in `ofertaks/database/database.py`.

## Architecture Rules

- Primary developer environment: Windows.
- Android packaging: GitHub Actions + Ubuntu + Buildozer.
- Supported UI languages: `sq`, `en`, `fr`.
- English is the fallback language.
- Never hard-code user-facing UI strings; add stable keys to the central localization package.
- Android-specific paths must use application writable directories from `ofertaks/app/paths.py`.
- Merchant/place is the fundamental location entity.
- Initial geographic market is Prishtina and immediate surroundings only. Keep viewport and import queries bounded.
- Chain is not the fundamental entity; it is an attribute/relationship of merchants and scraper sources.
- `stores` remains a scraper compatibility table only.
- Raw scraped data must never be destroyed.
- Historical source documents and raw observations are append-only evidence. Preserve original values; later matching must use links, validation state, or reversible merges rather than rewrites.
- Canonical-product matching must distinguish exact product, same variant/different size, same product family, category equivalent, and unrelated items. Only exact products share direct price history.
- Promotion claims must be stored separately from observed price history. Deal ranking must use deterministic consumer-facing historical/unit-price evidence, never partner, payment, sponsored, or commercial-relationship inputs.
- A chain-wide offer is not a branch-specific merchant price. Map summaries may use only fresh current evidence tied to the concrete merchant; label unknown or chain scope honestly.
- Price history is append-only. Do not update or delete observations to make a promotion appear better; preserve package quantity/unit and source context for later integrity checks.
- Official-source data may fill blanks but must not silently overwrite conflicts; persist field evidence and create validation work instead.
- Fake production data is forbidden. Fixtures belong only in tests or explicit developer data.
- Scraping failure must not crash the app.
- Community observations require provenance, timestamps, confidence, and freshness handling.
- Basemap tiles and OfertaKS merchant/product overlays are separate. Display OSM attribution and never bulk-prefetch public tiles.
- Stale prices must be visually marked once exposed in UI.
- Recommendation algorithms must expose reasoning.
- Never silently replace an unmatched shopping item or recipe ingredient.
- Tests must run after structural changes.

## Scraping Rules

- Use only publicly available information.
- Do not bypass authentication, CAPTCHA, bot protection, paywalls, or access restrictions.
- Use the shared HTTP client for rate limits, retries, timeouts, and conditional headers.
- OSM discovery must be a single bounded regional request initiated by the user or developer, then served from SQLite during normal map browsing.
- Prefer JSON, JSON-LD, schema metadata, data attributes, semantic HTML, and stable repeated structures.
- Avoid brittle `nth-child` selectors.
- Return `failed` or `partial` honestly when extraction is not possible.

## Privacy Expectations

- No analytics or advertising SDK.
- No contacts, microphone, or unrelated storage permissions.
- Location permission should be added only when a location feature explicitly needs it.
- Pantry, preferences, and shopping behavior remain local unless future explicit sync is implemented.
- Do not expose reporter location history for community submissions.

## Git Expectations

- Inspect `git status`, `git log --oneline -20`, and `git diff` before significant work.
- Do not reset or discard user work unless explicitly requested.
- Use incremental changes and clear commit prefixes: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `perf:`.
- Update `CHANGELOG.md` and `docs/DEVLOG.md` for meaningful behavior, schema, scraper, or packaging changes.

## Do Not

- Do not add heavy ML, browser automation, or plotting dependencies for MVP behavior.
- Do not move to a backend-first architecture.
- Do not make the UI depend on images.
- Do not present old community prices as guaranteed current.
- Do not infer product origin from merchant location.
