from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from fees.services.dates import add_months, count_recurrences, recurrence_date
from fees.services.money import money


class MoneyTests(SimpleTestCase):
    def test_rounds_half_up_to_two_places(self):
        self.assertEqual(money("10.005"), Decimal("10.01"))
        self.assertEqual(money("10.004"), Decimal("10.00"))

    def test_none_is_zero(self):
        self.assertEqual(money(None), Decimal("0.00"))


class RecurrenceTests(SimpleTestCase):
    def test_end_of_month_anchor_does_not_drift(self):
        anchor = date(2026, 1, 31)
        self.assertEqual(recurrence_date(anchor, 1, 1), date(2026, 2, 28))
        self.assertEqual(recurrence_date(anchor, 2, 1), date(2026, 3, 31))
        self.assertEqual(count_recurrences(anchor, date(2026, 1, 1), date(2026, 3, 31), 1), 3)

    def test_leap_year_clamp(self):
        self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_recurring_window_is_inclusive(self):
        anchor = date(2026, 1, 15)
        self.assertEqual(count_recurrences(anchor, date(2026, 2, 15), date(2026, 4, 15), 1), 3)
        self.assertEqual(count_recurrences(anchor, date(2026, 2, 16), date(2026, 4, 14), 1), 1)

    def test_invalid_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            count_recurrences(date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 31), 0)
