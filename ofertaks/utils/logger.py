"""Structured local logging."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ofertaks.app.paths import get_app_data_dir


def configure_logging() -> Path:
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "ofertaks.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )
    return log_path


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
