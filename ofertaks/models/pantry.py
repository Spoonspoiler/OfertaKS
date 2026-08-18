"""Pantry item model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class PantryItem:
    raw_name: str
    normalized_name: str
    quantity: float | None
    unit: str | None
    expires_at: datetime | None = None
    id: int | None = None
    created_at: datetime | None = None
