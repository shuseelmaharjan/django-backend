from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

MONEY_ZERO = Decimal("0.00")
MONEY_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    if value is None:
        return MONEY_ZERO
    return Decimal(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def nonnegative(value) -> Decimal:
    return max(money(value), MONEY_ZERO)
