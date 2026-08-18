"""Lightweight internal app compatibility checks."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from ofertaks.app.paths import get_cache_dir
from ofertaks.localization import t


def check_writable_directory(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    try:
        with NamedTemporaryFile(prefix="ofertaks-", dir=path, delete=True) as handle:
            handle.write(b"ok")
        return True
    except OSError:
        return False


def app_smoke_check(cache_dir: Path | None = None) -> dict[str, Any]:
    cache_dir = cache_dir or get_cache_dir()
    return {
        "cache_directory": str(cache_dir),
        "cache_directory_writable": check_writable_directory(cache_dir),
        "translation_service": t("app_title") == "OfertaKS",
    }
