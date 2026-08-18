"""Portable application paths for desktop and Android."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "ofertaks"


def get_app_data_dir(app_name: str = APP_DIR_NAME) -> Path:
    """Return an app-specific writable data directory."""
    override = os.environ.get("OFERTAKS_DATA_DIR")
    if override:
        return Path(override)

    android_private = os.environ.get("ANDROID_PRIVATE")
    if android_private:
        return Path(android_private) / app_name

    try:
        from kivy.utils import platform
    except Exception:
        platform = ""

    if platform == "android":
        return Path(os.environ.get("ANDROID_PRIVATE", ".")) / app_name

    return Path.home() / f".{app_name}"


def get_database_path() -> Path:
    return get_app_data_dir() / "ofertaks.sqlite3"


def get_cache_dir() -> Path:
    return get_app_data_dir() / "cache"


def get_debug_scrape_dir() -> Path:
    return get_cache_dir() / "debug_scrapes"


def ensure_app_dirs() -> None:
    get_app_data_dir().mkdir(parents=True, exist_ok=True)
    get_cache_dir().mkdir(parents=True, exist_ok=True)
