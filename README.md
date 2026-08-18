# OfertaKS

OfertaKS is an offline-first Android-oriented Kivy app for comparing Kosovo supermarket offers and growing into a local food decision engine. It stores offers and price history locally in SQLite, normalizes product names and units, scores deals, searches cached data, optimizes a small shopping basket, and now includes foundations for merchants, pantry, recipes, routing, origin, quality, and community price observations.

The long-term question is practical: what can I eat well today, using what I already have, while spending as little as reasonably possible and considering where I am?

## Development On Windows

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Run tests and launch the desktop app:

```powershell
pytest -q
python main.py
```

The app database is stored under `~/.ofertaks/ofertaks.sqlite3` on desktop. Override this with `OFERTAKS_DATA_DIR=/path/to/data`.

Runtime dependencies stay in `requirements.txt`. Developer/test dependencies, including pytest, are in `requirements-dev.txt` so pytest is not packaged into the Android APK.

## Localization

OfertaKS officially supports:

- Albanian (`sq`, displayed as `Shqip`)
- English (`en`, displayed as `English`)
- French (`fr`, displayed as `Français`)

English is the fallback for unsupported system languages and missing translation keys. The app detects the system language on first launch, then a manual Settings selection overrides detection and is persisted locally.

## Android Debug Build With GitHub Actions

Windows is the primary local development environment. Android APKs are built remotely by GitHub Actions on Ubuntu, so local WSL/Linux is not required for ordinary development.

Workflow:

1. Commit changes.
2. Push to GitHub `main`.
3. Open the GitHub repository.
4. Go to **Actions**.
5. Open **Build Android APK**.
6. Wait for the run to finish, or run it manually with **Run workflow**.
7. Download the `OfertaKS-Android-Debug` artifact.
8. Extract the artifact ZIP.
9. Transfer the APK to the Android phone.
10. Install the APK.

Android may require enabling **Install unknown apps** for the browser, file manager, or app used to open the APK.

The workflow uses Python 3.11 and Java 17 for Buildozer/python-for-android compatibility. It uploads `bin/*.apk` plus `build-info.txt` as `OfertaKS-Android-Debug` and keeps the artifact for 14 days.

If Android builds become too slow for every push, remove or comment the `push` trigger in `.github/workflows/android-debug.yml` and keep `workflow_dispatch` for manual builds.

## Optional ADB Install From Windows

```powershell
adb devices
adb install -r path\to\ofertaks.apk
```

ADB is useful for frequent testing but is not required for ordinary APK installation.

## Android Workflow Troubleshooting

If the Android workflow fails, open GitHub -> Actions -> Build Android APK -> failed run -> Build debug APK logs. The first remote run still needs to validate the Buildozer environment and may reveal python-for-android packaging details to fix.

## Release Build Preparation

Before generating a release AAB or APK, create a signing key, configure signing in `buildozer.spec` or your CI secrets, test the debug build on real devices, then run the Buildozer release target appropriate for your Play Console flow.

## Scraper Status

Scrapers never insert fake production data.

- ETC: text offer pages are supported and are the first real data source.
- Interex: flyer metadata and PDF downloads are supported. Text extraction uses `pypdf`; image-only PDFs are marked `ocr_required`.
- Viva Fresh: JSON-LD and structured card parsing are supported. Current public offer pages may be image-based; those are recorded as partial, not fabricated.

## Merchant, Pantry, Recipes, Routing

OfertaKS treats concrete merchants/places as the fundamental location entity. Chains are metadata. The current app includes:

- `chains` and `merchants` tables
- Haversine distance and duplicate merchant detection
- local pantry items
- recipe ingredient matching
- missing ingredient calculation
- additional recipe cost from cached offers
- freshness, quality, and origin provenance helpers for future community observations

## Prishtina Food Map

The first geographic market is Prishtina and its immediate surroundings. `Map` is a primary navigation surface: it uses an OSM-compatible, on-demand tile provider for geographic context and SQLite for OfertaKS merchant, product, price, origin, quality, and freshness data. The map works from cached merchant data when offline; tiles are requested only for the visible viewport and retain visible `© OpenStreetMap contributors` attribution.

Food-place discovery is a user-triggered, one-request bounded Overpass import for the configured Prishtina region. It supports real OSM food places such as supermarkets, groceries, greengrocers, markets, bakeries, butchers, fish shops, farms, and specialty food shops. It does not import all Kosovo or fabricate stores. Chain locations and price-source capability are intentionally distinct: ETC is live, Viva Fresh and Interex are partial, while Albi Market, Maxi, Meridian Express, Emona Center, and SPAR Kosovo are location-only or not yet automated.

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
- `recipes`: pantry and recipe matching
- `routing`: distance helpers
- `community`: freshness, quality, and origin reasoning
- `ui`: Kivy screens and widgets

More detail is in `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, and `AGENTS.md`.

## Git Workflow

Before significant work, inspect status/history/diff. After meaningful changes, update `CHANGELOG.md` and `docs/DEVLOG.md`, run tests, and propose a commit message with a clear prefix such as `feat:`, `fix:`, `test:`, or `docs:`.

## Known MVP Limits

OCR is intentionally not implemented. Image-only flyers remain visible in diagnostics as partial scraper results until an OCR path is added. Background Android WorkManager sync is also deferred; refresh runs on app launch policy or user action and uses worker threads so the UI remains responsive.

Map routing is only an interface and route-polyline capability; no production navigation provider or GPS permission is included yet. Community places and product observations remain local until an explicit server sync is implemented.
