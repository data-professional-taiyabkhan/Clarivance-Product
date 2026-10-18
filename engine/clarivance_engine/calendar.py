"""UK tax-year dates and HMRC Self Assessment payment dates."""
from __future__ import annotations

from datetime import date


def tax_year_start(d: date) -> date:
    start = date(d.year, 4, 6)
    return start if d >= start else date(d.year - 1, 4, 6)


def tax_year_end(d: date) -> date:
    s = tax_year_start(d)
    return date(s.year + 1, 4, 5)


def label(start: date) -> str:
    return f"{start.year}-{str(start.year + 1)[2:]}"


def payment_dates(year_start: date) -> dict[str, date]:
    """For the tax year beginning year_start: two payments on account and the balancing payment."""
    y = year_start.year
    return {
        "poa1": date(y + 1, 1, 31),
        "poa2": date(y + 1, 7, 31),
        "balancing": date(y + 2, 1, 31),
    }
