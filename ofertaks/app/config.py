"""Runtime configuration for OfertaKS."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "OfertaKS"
PACKAGE_NAME = "com.ptitspot.ofertaks"
DEFAULT_LANGUAGE = "sq"
DEBUG_SCRAPERS = os.environ.get("OFERTAKS_DEBUG_SCRAPERS", "0") == "1"
AUTO_SYNC_MAX_AGE_HOURS = 6
HTTP_TIMEOUT_SECONDS = 15
HTTP_MAX_RETRIES = 2
HTTP_MAX_CONCURRENT = 2
HTTP_USER_AGENT = (
    "OfertaKS/0.1 (+local Android app; respectful Kosovo supermarket offer indexing)"
)
HOST_REQUEST_DELAY_SECONDS = 0.75
IMAGE_CACHE_LIMIT_BYTES = 30 * 1024 * 1024
DEBUG_CACHE_LIMIT_BYTES = 40 * 1024 * 1024

STORE_CONFIG = {
    "viva_fresh": {
        "name": "Viva Fresh",
        "website": "https://vivafresh-rks.com/",
        "enabled": True,
    },
    "interex": {
        "name": "Interex",
        "website": "https://interex-rks.com/",
        "enabled": True,
    },
    "etc": {
        "name": "ETC",
        "website": "https://etc-ks.com/",
        "enabled": True,
    },
}


def get_data_dir() -> Path:
    """Return a writable app data directory on desktop and Android."""
    android_private = os.environ.get("ANDROID_PRIVATE")
    if android_private:
        return Path(android_private) / "ofertaks"
    override = os.environ.get("OFERTAKS_DATA_DIR")
    if override:
        return Path(override)
    return Path.home() / ".ofertaks"
