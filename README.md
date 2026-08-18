# OfertaKS

OfertaKS is an offline-first Android-oriented Kivy app for comparing Kosovo supermarket offers. It stores offers and price history locally in SQLite, normalizes product names and units, scores deals, searches cached data, and optimizes a small shopping basket.

## Desktop Development

Create a virtual environment, install dependencies, then run:

```bash
pip install -r requirements.txt
python main.py
```

The app database is stored under `~/.ofertaks/ofertaks.sqlite3` on desktop. Override this with `OFERTAKS_DATA_DIR=/path/to/data`.

Run tests without network access:

```bash
python -m unittest discover -s tests -q
```

## Android Debug Build

Buildozer is best run from Linux or WSL because python-for-android needs a Linux build toolchain.

Typical WSL setup:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git zip unzip openjdk-17-jdk
python3 -m pip install --user buildozer cython
buildozer android debug
```

The debug APK is produced under `bin/`, usually with a name similar to:

```text
bin/ofertaks-0.1.0-arm64-v8a-debug.apk
```

Install on a connected Android device:

```bash
adb install -r bin/ofertaks-0.1.0-arm64-v8a-debug.apk
```

## Release Build Preparation

Before generating a release AAB or APK, create a signing key, configure signing in `buildozer.spec` or your CI secrets, test the debug build on real devices, then run the Buildozer release target appropriate for your Play Console flow.

## Scraper Status

Scrapers never insert fake production data.

- ETC: text offer pages are supported and are the first real data source.
- Interex: flyer metadata and PDF downloads are supported. Text extraction uses `pypdf`; image-only PDFs are marked `ocr_required`.
- Viva Fresh: JSON-LD and structured card parsing are supported. Current public offer pages may be image-based; those are recorded as partial, not fabricated.

## Scraper Maintenance

Add a new supermarket by implementing `BaseScraper` and registering it in `ofertaks/scrapers/registry.py`.

```python
class NewStoreScraper(BaseScraper):
    store_id = "new_store"
    store_name = "New Store"
    website = "https://example.test/"

    def fetch_and_parse(self):
        response = self.client.get(self.website)
        offers = []
        # Parse public HTML, JSON, or text PDFs here.
        return ScrapeResult(self.store_id, self.store_name, "success", offers)
```

Keep selectors semantic, use fallbacks, and return `failed` or `partial` when a site changes instead of crashing the sync.

## Architecture

Core modules are separated from the UI:

- `models`: dataclasses for offers, products, stores
- `parsing`: price, unit, date, HTML, PDF helpers
- `normalization`: deterministic product and brand normalization plus fuzzy matching
- `database`: SQLite schema and repository
- `scrapers`: store-specific adapters
- `services`: sync, history, comparison, basket optimizer
- `ui`: Kivy screens and widgets

## Known MVP Limits

OCR is intentionally not implemented. Image-only flyers remain visible in diagnostics as partial scraper results until an OCR path is added. Background Android WorkManager sync is also deferred; refresh runs on app launch policy or user action and uses worker threads so the UI remains responsive.
