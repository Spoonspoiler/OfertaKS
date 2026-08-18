"""Date parsing for Kosovo offer ranges."""

from __future__ import annotations

import re
from datetime import date

DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?")


def _make_date(day: str, month: str, year: str | None, fallback_year: int) -> date | None:
    use_year = fallback_year
    if year:
        use_year = int(year)
        if use_year < 100:
            use_year += 2000
    try:
        return date(use_year, int(month), int(day))
    except ValueError:
        return None


def parse_date_range(text: str, today: date | None = None) -> tuple[date | None, date | None]:
    today = today or date.today()
    matches = list(DATE_RE.finditer(text))
    if not matches:
        return None, None

    if len(matches) == 1:
        m = matches[0]
        parsed = _make_date(m.group(1), m.group(2), m.group(3), today.year)
        return parsed, parsed

    first, second = matches[0], matches[1]
    end_year = second.group(3)
    fallback_year = today.year
    if end_year:
        fallback_year = int(end_year) + (2000 if int(end_year) < 100 else 0)
    start = _make_date(first.group(1), first.group(2), first.group(3), fallback_year)
    end = _make_date(second.group(1), second.group(2), second.group(3), fallback_year)
    return start, end
