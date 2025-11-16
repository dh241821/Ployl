"""Maintenance-related helper functions."""

from __future__ import annotations

from datetime import date
from typing import MutableMapping, Optional


def _as_date(value: Optional[str | date]) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def calculate_next_due(
    last_date: Optional[date | str], interval_months: Optional[int]
) -> Optional[date]:
    """Return the next due date based on ``last_date`` and ``interval_months``."""

    last = _as_date(last_date)
    if not last or not interval_months:
        return None
    months = last.month - 1 + int(interval_months)
    year = last.year + months // 12
    month = months % 12 + 1
    day = min(last.day, _days_in_month(year, month))
    return date(year, month, day)


def update_maintenance_dates(
    product: MutableMapping[str, object]
) -> MutableMapping[str, object]:
    """Derive next STK/MTK dates based on the stored intervals."""

    stk_next = calculate_next_due(product.get("letzte_stk"), product.get("stk_intervall"))
    mtk_next = calculate_next_due(product.get("letzte_mtk"), product.get("mtk_intervall"))
    if stk_next:
        product["naechste_stk"] = stk_next
    if mtk_next:
        product["naechste_mtk"] = mtk_next
    return product


def _days_in_month(year: int, month: int) -> int:
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    if month in {1, 3, 5, 7, 8, 10, 12}:
        return 31
    return 30


__all__ = ["calculate_next_due", "update_maintenance_dates"]
