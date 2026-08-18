# Scrapers

## Current Adapters

- `VivaFreshScraper`: JSON-LD/structured HTML first. Current public page appears image-based, so it returns `partial` when no text offer can be parsed.
- `InterexScraper`: flyer index and PDF download. Uses `pypdf`; marks image-only/no-text PDFs as OCR-required instead of faking data.
- `ETCScraper`: parses current ETC text offer pages and is the first real working source.

## Rules

- Keep scraper code separate from UI.
- Use the shared HTTP client.
- Never bypass access controls.
- Never insert fixture or invented production offers.
- Preserve raw names and source URLs.
- Store failures in `scrape_runs`.

## Adding a Scraper

Implement `BaseScraper.fetch_and_parse()` and register the class in `ofertaks/scrapers/registry.py`.

Return a `ScrapeResult` with:

- `success` when offers were parsed and persisted
- `partial` when metadata was found but product extraction needs a later capability
- `failed` when the source could not be parsed
