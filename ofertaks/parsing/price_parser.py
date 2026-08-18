"""Conservative EUR price parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ofertaks.utils.text import clean_text


@dataclass(slots=True)
class ParsedPrice:
    value: float
    confidence: float
    raw: str


CURRENCY = r"(?:€|eur|\ufffd)"
NUMBER = r"(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:[,.]\d{1,2})?"
PRICE_WITH_CURRENCY_RE = re.compile(
    rf"(?:(?:{CURRENCY})\s*({NUMBER})|({NUMBER})\s*(?:{CURRENCY}))",
    re.IGNORECASE,
)
DECIMAL_RE = re.compile(r"(?<!\d)(\d{1,4}[,.]\d{1,2})(?!\d)")
SPLIT_CENTS_RE = re.compile(r"(?<!\d)(\d{1,3})\s+(\d{2})(?!\d)")


def _to_float(raw: str) -> float | None:
    value = raw.strip().replace(" ", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed < 0 or parsed > 10000:
        return None
    return round(parsed, 2)


def extract_prices(text: str) -> list[float]:
    """Extract likely EUR prices from text, ignoring percentages."""
    cleaned = clean_text(text).replace("^{€}", "€")
    prices: list[float] = []
    spans: list[tuple[int, int]] = []

    for match in PRICE_WITH_CURRENCY_RE.finditer(cleaned):
        raw = match.group(1) or match.group(2)
        value = _to_float(raw)
        if value is not None:
            prices.append(value)
            spans.append(match.span())

    if prices:
        return prices

    for match in DECIMAL_RE.finditer(cleaned):
        end = match.end()
        if cleaned[end : end + 1] == "%":
            continue
        value = _to_float(match.group(1))
        if value is not None:
            prices.append(value)
            spans.append(match.span())

    if prices:
        return prices

    match = SPLIT_CENTS_RE.search(cleaned)
    if match:
        value = _to_float(f"{match.group(1)}.{match.group(2)}")
        if value is not None:
            prices.append(value)

    return prices


def parse_price(text: str) -> ParsedPrice | None:
    cleaned = clean_text(text)
    match = PRICE_WITH_CURRENCY_RE.search(cleaned.replace("^{€}", "€"))
    if match:
        raw = match.group(1) or match.group(2)
        value = _to_float(raw)
        if value is not None:
            return ParsedPrice(value=value, confidence=0.95, raw=match.group(0))

    match = DECIMAL_RE.search(cleaned)
    if match and cleaned[match.end() : match.end() + 1] != "%":
        value = _to_float(match.group(1))
        if value is not None:
            return ParsedPrice(value=value, confidence=0.75, raw=match.group(1))

    match = SPLIT_CENTS_RE.search(cleaned)
    if match:
        value = _to_float(f"{match.group(1)}.{match.group(2)}")
        if value is not None:
            return ParsedPrice(
                value=value, confidence=0.65, raw=f"{match.group(1)} {match.group(2)}"
            )

    return None


def parse_discount_percent(text: str) -> float | None:
    match = re.search(r"(?<!\d)(\d{1,2})\s*%", text)
    if not match:
        return None
    value = float(match.group(1))
    if 0 < value < 95:
        return value
    return None
