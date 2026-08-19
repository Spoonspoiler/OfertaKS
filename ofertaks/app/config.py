"""Runtime configuration for OfertaKS."""

from __future__ import annotations

import os
from pathlib import Path

from ofertaks import __version__
from ofertaks.app.paths import get_app_data_dir

APP_NAME = "OfertaKS"
APP_VERSION = __version__
PACKAGE_NAME = "com.ptitspot.ofertaks"
DEFAULT_LANGUAGE = "en"
DEBUG_SCRAPERS = os.environ.get("OFERTAKS_DEBUG_SCRAPERS", "0") == "1"
AUTO_SYNC_MAX_AGE_HOURS = 6
HTTP_TIMEOUT_SECONDS = 15
HTTP_MAX_RETRIES = 2
HTTP_MAX_CONCURRENT = 2
HTTP_USER_AGENT = (
    "OfertaKS/0.1 (+https://github.com/Spoonspoiler/OfertaKS; respectful local food discovery)"
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

# Chains are broader than scraper sources. A chain can have known locations while
# its prices remain unavailable or only partially extracted.
CHAIN_CONFIG = {
    "etc": {"name": "ETC", "website": "https://etc-ks.com/", "enabled": True, "aliases": ("etc",)},
    "viva_fresh": {
        "name": "Viva Fresh",
        "website": "https://vivafresh-rks.com/",
        "enabled": True,
        "aliases": ("viva fresh", "vivafresh"),
    },
    "interex": {"name": "Interex", "website": "https://interex-rks.com/", "enabled": True, "aliases": ("interex",)},
    "albi_market": {"name": "Albi Market", "website": None, "enabled": True, "aliases": ("albi market", "albi")},
    "maxi": {"name": "Maxi", "website": None, "enabled": True, "aliases": ("maxi",)},
    "meridian": {
        "name": "Meridian Express",
        "website": None,
        "enabled": True,
        "aliases": ("meridian express", "meridian"),
    },
    "emona": {"name": "Emona Center", "website": None, "enabled": True, "aliases": ("emona center", "emona")},
    "spar_kosovo": {"name": "SPAR Kosovo", "website": None, "enabled": True, "aliases": ("spar kosovo", "spar")},
}

# This is a capability declaration, not a claim that every source currently
# provides a complete catalogue. Albi is deliberately tracked here without a
# scraper entry so it remains visible to users without generating fake offers.
SOURCE_STATUS_CONFIG = (
    {
        "id": "etc",
        "name": "ETC",
        "availability": "live",
        "status_key": "store_status_live",
    },
    {
        "id": "viva_fresh",
        "name": "Viva Fresh",
        "availability": "live",
        "status_key": "store_status_live",
    },
    {
        "id": "interex",
        "name": "Interex",
        "availability": "partial",
        "status_key": "store_status_interex_partial",
    },
    {
        "id": "albi_market",
        "name": "Albi Market",
        "availability": "not_implemented",
        "status_key": "store_status_not_implemented",
    },
    {
        "id": "maxi",
        "name": "Maxi",
        "availability": "location_only",
        "status_key": "store_status_location_only",
    },
    {
        "id": "meridian",
        "name": "Meridian Express",
        "availability": "location_only",
        "status_key": "store_status_location_only",
    },
    {
        "id": "emona",
        "name": "Emona Center",
        "availability": "location_only",
        "status_key": "store_status_location_only",
    },
    {
        "id": "spar_kosovo",
        "name": "SPAR Kosovo",
        "availability": "location_only",
        "status_key": "store_status_location_only",
    },
)


def get_data_dir() -> Path:
    """Return a writable app data directory on desktop and Android."""
    return get_app_data_dir()
