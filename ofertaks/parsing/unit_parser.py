"""Product quantity and unit parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ofertaks.utils.text import comparable_text


@dataclass(slots=True)
class ParsedQuantity:
    quantity: float
    unit: str
    raw: str


MULTIPACK_RE = re.compile(
    r"(?<!\w)(\d{1,3})\s*x\s*(\d+(?:[,.]\d+)?)\s*(ml|milliliter|litra|liter|litre|l|kg|kilogram|g|gr|gram|pcs|cope|cope|cop[eë])\b",
    re.IGNORECASE,
)
SIMPLE_RE = re.compile(
    r"(?<!\w)(\d+(?:[,.]\d+)?)\s*(ml|milliliter|litra|liter|litre|l|kg|kilogram|g|gr|gram|pcs|cope|cop[eë])\b",
    re.IGNORECASE,
)

UNIT_ALIASES = {
    "ml": "ml",
    "milliliter": "ml",
    "l": "ml",
    "liter": "ml",
    "litre": "ml",
    "litra": "ml",
    "kg": "g",
    "kilogram": "g",
    "g": "g",
    "gr": "g",
    "gram": "g",
    "pcs": "piece",
    "cope": "piece",
    "copë": "piece",
}


def _number(value: str) -> float:
    return float(value.replace(",", "."))


def _canonical(quantity: float, unit: str) -> tuple[float, str]:
    normalized_unit = UNIT_ALIASES[unit.casefold()]
    if unit.casefold() in {"l", "liter", "litre", "litra"}:
        return quantity * 1000, "ml"
    if unit.casefold() in {"kg", "kilogram"}:
        return quantity * 1000, "g"
    return quantity, normalized_unit


def parse_quantity(text: str) -> ParsedQuantity | None:
    normalized = comparable_text(text).replace("×", "x")

    match = MULTIPACK_RE.search(normalized)
    if match:
        count = int(match.group(1))
        amount = _number(match.group(2))
        quantity, unit = _canonical(count * amount, match.group(3))
        return ParsedQuantity(quantity=quantity, unit=unit, raw=match.group(0))

    match = SIMPLE_RE.search(normalized)
    if match:
        amount = _number(match.group(1))
        quantity, unit = _canonical(amount, match.group(2))
        return ParsedQuantity(quantity=quantity, unit=unit, raw=match.group(0))

    return None


def calculate_unit_price(price: float, quantity: float | None, unit: str | None) -> float | None:
    if not quantity or not unit or quantity <= 0:
        return None
    if unit in {"g", "ml"}:
        return round(price / quantity * 1000, 4)
    if unit == "piece":
        return round(price / quantity, 4)
    return None


def format_quantity(quantity: float | None, unit: str | None) -> str:
    if quantity is None or unit is None:
        return ""
    if unit == "ml" and quantity >= 1000 and quantity % 1000 == 0:
        return f"{quantity / 1000:.0f} L"
    if unit == "ml" and quantity >= 1000:
        return f"{quantity / 1000:g} L"
    if unit == "g" and quantity >= 1000 and quantity % 1000 == 0:
        return f"{quantity / 1000:.0f} kg"
    if unit == "g" and quantity >= 1000:
        return f"{quantity / 1000:g} kg"
    if unit == "piece":
        return f"{quantity:g} pcs"
    return f"{quantity:g} {unit}"


def format_unit_price(unit_price: float | None, unit: str | None) -> str:
    if unit_price is None or unit is None:
        return ""
    label = {"ml": "L", "g": "kg", "piece": "piece"}.get(unit, unit)
    return f"{unit_price:.2f} EUR/{label}"
