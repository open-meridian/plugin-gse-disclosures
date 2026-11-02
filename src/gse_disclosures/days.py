"""A GSE factor's dates.

The agencies date a factor by the month it is in effect from, the month they
publish it in: Fannie Mae's file published on 5 November 2026 states the
factor of November 2026. The contract's `factor_month` is the month whose
payments the factor reflects, the month before (`FNMA:MA5123:202610`,
record date 31 October, paid 25 November), so a fill settling in November
takes the row of October (991). Here:

- `factor_month(effective)`: the agency's month less one;
- `record_date(month)`: the factor month's last day, the holder of record
  then being paid (the pools' record-date rule, last day of the prior month
  to the payment);
- `payment_date(month, delay, days)`: by the security's payment delay as the
  agencies state it -- 45 days the 15th of the month after the factor
  month, 55 days the 25th of it, 75 days the 15th of the month after that
  -- moved to the next business day by the record's payment calendar (or
  the deployment's US dollar calendar, `agency.Days`); None where the
  calendar does not answer;
- `published(month, days)`: the fourth business day of the month after the
  factor month, when both GSEs publish their monthly files (4:30 p.m.
  Eastern); None where the calendar does not answer.
"""

from __future__ import annotations

import calendar
from datetime import date

from .agency import Days, add_months, month_of

#: Each payment delay the GSEs' securities state (S-06, Payment Delay Days),
#: as months after the factor month and the day of that month it pays.
DELAYS: dict[int, tuple[int, int]] = {45: (1, 15), 55: (1, 25), 75: (2, 15)}
#: The business day of the month the monthly files are published on.
PUBLICATION_DAY = 4

__all__ = [
    "DELAYS",
    "PUBLICATION_DAY",
    "add_months",
    "factor_month",
    "month_of",
    "payment_date",
    "published",
    "record_date",
]


def factor_month(effective: str) -> str:
    """The contract's factor month for the month an agency says its factor
    is in effect from: the month before."""
    return add_months(effective, -1)


def record_date(month: str) -> date:
    """A factor month's record date: its last day."""
    year, number = month_of(month)
    return date(year, number, calendar.monthrange(year, number)[1])


async def payment_date(
    month: str, delay_days: int, days: Days, calendar_id: str = "", day: int = 0
) -> date | None:
    """When a factor month's payment is made for a security of this delay
    (or on `day` of that month, where the record states its payment day);
    None for a delay the GSEs do not state, or a day the calendar does not
    answer for."""
    if delay_days not in DELAYS:
        return None
    after, nominal = DELAYS[delay_days]
    year, number = month_of(add_months(month, after))
    return await days.on_or_after(date(year, number, day or nominal), calendar_id)


async def published(month: str, days: Days) -> date | None:
    """When the monthly files stating a factor month's factors are
    published: the fourth business day of the month after it."""
    year, number = month_of(add_months(month, 1))
    return await days.nth_business_day(year, number, PUBLICATION_DAY)
