"""Canonical product models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Product:
    id: int | None
    canonical_name: str
    brand: str | None
    quantity: float | None
    unit: str | None
    category: str | None
