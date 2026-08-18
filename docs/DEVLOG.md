# Development Log

## 2026-08-18

- Initial Kivy/SQLite/scraper MVP already existed at the start of this task.
- Git safe-directory checks can block `git log` under the sandbox user; use one-off `git -c safe.directory=...` inspection rather than writing global Git config.
- ETC live pages currently expose text offer data and are the first working real scraper source.
- ETC pages can contain encoding/currency replacement behavior, so price parsing accepts the replacement character only as a conservative currency marker.
- Viva Fresh public offers currently appear image-based; scraper reports `partial` instead of inserting fake offers.
- Interex flyer PDFs can be image-only or have no useful text layer; scraper reports `partial` / OCR required when `pypdf` cannot extract products.
- Added schema version 2 with merchant-first location tables, pantry, recipes, and community observation tables.
- Added explicit offer migration for optional `merchant_id`, `chain_id`, and origin fields to avoid breaking existing SQLite files.
- Recipe pantry matching now uses a stricter confidence threshold than offer purchasing to avoid silently marking unrelated pantry items as available.
- Android build could not be run on this Windows machine because no WSL distribution/Buildozer environment is installed.
- Android builds are now configured to run remotely on GitHub Actions using Ubuntu 22.04, Python 3.11, Java 17, Buildozer 1.5.0, and `cython<3`.
- Desktop development remains native Windows; ordinary app development should not require local Linux or WSL.
- Supported initial UI languages are `sq`, `en`, and `fr`; English is the fallback for unknown languages and missing translations.
- Manual language selection is stored locally in SQLite `user_preferences` and is applied on the next app start; current Kivy screens also refresh labels live where practical.
- Fixed the Kivy label layout regression where `text_size=(0, None)` collapsed visible text into narrow vertical columns; screens and bottom navigation are now centered with sensible max width while remaining mobile-safe.
- Android packaging has not been validated by an actual GitHub Actions run yet, so the first remote build may still reveal Buildozer/python-for-android issues.
