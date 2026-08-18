"""Store model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Store:
    id: str
    name: str
    website: str
    enabled: bool = True
    last_successful_sync: datetime | None = None
