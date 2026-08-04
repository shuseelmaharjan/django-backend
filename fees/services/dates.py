from __future__ import annotations

import calendar
from datetime import date


def add_months(value: date, months: int) -> date:
    """Add months while clamping only that occurrence to the target month."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def recurrence_date(anchor: date, occurrence_index: int, interval_months: int) -> date:
    """Return an occurrence from the original anchor, preventing Jan-31 -> Feb-28 -> Mar-28 drift."""
    if occurrence_index < 0:
        raise ValueError("occurrence_index must be non-negative")
    if interval_months <= 0:
        raise ValueError("interval_months must be positive")
    return add_months(anchor, occurrence_index * interval_months)


def count_recurrences(anchor: date, start: date, end: date, interval_months: int) -> int:
    if end < start:
        return 0
    if end < anchor:
        return 0
    if interval_months <= 0:
        raise ValueError("interval_months must be positive")

    index = 0
    current = recurrence_date(anchor, index, interval_months)
    while current < start:
        index += 1
        current = recurrence_date(anchor, index, interval_months)

    count = 0
    while current <= end:
        count += 1
        index += 1
        current = recurrence_date(anchor, index, interval_months)
    return count
