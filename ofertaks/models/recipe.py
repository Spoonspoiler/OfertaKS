"""Recipe models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RecipeIngredient:
    raw_name: str
    normalized_name: str
    quantity: float | None = None
    unit: str | None = None
    required: bool = True
    id: int | None = None


@dataclass(slots=True)
class Recipe:
    slug: str
    title: str
    cuisine: str | None
    servings: int
    ingredients: tuple[RecipeIngredient, ...]
    instructions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    source: str | None = None
    id: int | None = None
