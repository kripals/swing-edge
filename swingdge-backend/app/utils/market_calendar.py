"""
Market calendar helper — TSX + NYSE holiday guard.

Used by the price-check trigger to skip processing on market holidays,
preventing false stop/target alerts from stale quotes.

Holidays are hardcoded per year. Update annually.
Both TSX and NYSE holidays are included (we trade both markets).
"""
from __future__ import annotations

from datetime import date

# ── 2025 holidays (TSX + NYSE) ────────────────────────────────────────────────

_HOLIDAYS_2025: frozenset[date] = frozenset([
    date(2025, 1, 1),   # New Year's Day
    date(2025, 2, 17),  # Family Day (TSX) / Presidents' Day (NYSE)
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 19),  # Victoria Day (TSX only — NYSE open, but we skip both)
    date(2025, 7, 1),   # Canada Day (TSX)
    date(2025, 7, 4),   # Independence Day (NYSE)
    date(2025, 8, 4),   # Civic Holiday (TSX — Ontario)
    date(2025, 9, 1),   # Labour Day
    date(2025, 10, 13), # Thanksgiving (TSX)
    date(2025, 11, 11), # Remembrance Day (TSX)
    date(2025, 11, 27), # Thanksgiving (NYSE)
    date(2025, 12, 25), # Christmas Day
    date(2025, 12, 26), # Boxing Day (TSX)
])

# ── 2026 holidays (TSX + NYSE) ────────────────────────────────────────────────

_HOLIDAYS_2026: frozenset[date] = frozenset([
    date(2026, 1, 1),   # New Year's Day
    date(2026, 2, 16),  # Family Day (TSX) / Presidents' Day (NYSE)
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 18),  # Victoria Day (TSX)
    date(2026, 7, 1),   # Canada Day (TSX)
    date(2026, 7, 3),   # Independence Day observed (NYSE)
    date(2026, 8, 3),   # Civic Holiday (TSX — Ontario)
    date(2026, 9, 7),   # Labour Day
    date(2026, 10, 12), # Thanksgiving (TSX)
    date(2026, 11, 11), # Remembrance Day (TSX)
    date(2026, 11, 26), # Thanksgiving (NYSE)
    date(2026, 12, 25), # Christmas Day
    date(2026, 12, 28), # Boxing Day observed (TSX)
])

_HOLIDAYS_BY_YEAR: dict[int, frozenset[date]] = {
    2025: _HOLIDAYS_2025,
    2026: _HOLIDAYS_2026,
}


def is_market_open(today: date | None = None) -> bool:
    """
    Returns False if today is a weekend or a known TSX/NYSE holiday.
    Returns True on any regular weekday not in the holiday list.
    Falls back to True for years not in _HOLIDAYS_BY_YEAR (fail open).
    """
    if today is None:
        today = date.today()

    # Weekends are always closed
    if today.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False

    holidays = _HOLIDAYS_BY_YEAR.get(today.year)
    if holidays is None:
        # Year not covered — fail open so we don't block price-checks
        return True

    return today not in holidays
