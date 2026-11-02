"""The days the GSEs' disclosures keep: the Federal Reserve's holidays, a
month's business days, and each factor's dates.

Fannie Mae and Freddie Mac publish no file on a day the Federal Reserve
observes as a holiday (Freddie Mac's Disclosure Guide, "Timing and frequency
of disclosure"), and pay investors on the next business day when a payment
day is not one. The holidays are the Federal Reserve's eleven, a Sunday's
observed on the Monday after and a Saturday's not moved (the Board's holiday
schedule).

**A factor's dates** (contract v29, W10.4; the fixtures' convention). The
agencies date a factor by the month it is in effect from, the month they
publish it in: Fannie Mae's file published on 5 November 2026 states the
factor of November 2026. The contract's `factor_month` is the month whose
payments the factor reflects, the month before (`FNMA:MA5123:202610`,
record date 31 October, paid 25 November), so a fill settling in November
takes the row of October (991). Here:

- `factor_month(effective)`: the agency's month less one;
- `record_date(month)`: the factor month's last day, the holder of record
  then being paid (the pool's record-date rule, last day of the prior month
  to the payment);
- `payment_date(month, delay)`: by the security's payment delay as the
  agencies state it -- 45 days the 15th of the month after the factor
  month, 55 days the 25th of it, 75 days the 15th of the month after that
  -- moved to the next business day;
- `published(month)`: the fourth business day of the month after the
  factor month, when both GSEs publish their monthly files (4:30 p.m.
  Eastern).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

#: Each payment delay the GSEs' securities state (S-06, Payment Delay Days),
#: as months after the factor month and the day of that month it pays.
DELAYS: dict[int, tuple[int, int]] = {45: (1, 15), 55: (1, 25), 75: (2, 15)}
#: The business day of the month the monthly files are published on.
PUBLICATION_DAY = 4


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth `weekday` (Monday 0) of a month; n of -1 the last."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def holidays(year: int) -> frozenset[date]:
    """The Federal Reserve's holidays of a year, as observed."""
    fixed = [date(year, 1, 1), date(year, 7, 4), date(year, 11, 11), date(year, 12, 25)]
    if year >= 2022:
        fixed.append(date(year, 6, 19))
    observed = {d + timedelta(days=1) if d.weekday() == 6 else d for d in fixed}
    observed |= {
        _nth_weekday(year, 1, 0, 3),  # Birthday of Martin Luther King, Jr.
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _nth_weekday(year, 5, 0, -1),  # Memorial Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 10, 0, 2),  # Columbus Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving Day
    }
    return frozenset(observed)


def business_day(day: date) -> bool:
    """Whether the agencies publish and pay on a day."""
    return day.weekday() < 5 and day not in holidays(day.year)


def on_or_after(day: date) -> date:
    """The day, or the next business day after it."""
    while not business_day(day):
        day += timedelta(days=1)
    return day


def nth_business_day(year: int, month: int, n: int) -> date:
    """A month's nth business day."""
    day = on_or_after(date(year, month, 1))
    for _ in range(n - 1):
        day = on_or_after(day + timedelta(days=1))
    return day


def month_of(text: str) -> tuple[int, int]:
    """A month written YYYYMM, as (year, month)."""
    if len(text) != 6 or not text.isdigit() or not 1 <= int(text[4:]) <= 12:
        raise ValueError(f"a month is YYYYMM, not {text!r}")
    return int(text[:4]), int(text[4:])


def add_months(month: str, count: int) -> str:
    """A month YYYYMM moved by `count` months."""
    year, number = month_of(month)
    index = year * 12 + number - 1 + count
    return f"{index // 12:04d}{index % 12 + 1:02d}"


def factor_month(effective: str) -> str:
    """The contract's factor month for the month an agency says its factor
    is in effect from: the month before."""
    return add_months(effective, -1)


def record_date(month: str) -> date:
    """A factor month's record date: its last day."""
    year, number = month_of(month)
    return date(year, number, calendar.monthrange(year, number)[1])


def payment_date(month: str, delay_days: int) -> date | None:
    """When a factor month's payment is made for a security of this delay;
    None for a delay the GSEs do not state."""
    if delay_days not in DELAYS:
        return None
    after, day = DELAYS[delay_days]
    year, number = month_of(add_months(month, after))
    return on_or_after(date(year, number, day))


def published(month: str) -> date:
    """When the monthly files stating a factor month's factors are
    published: the fourth business day of the month after it."""
    year, number = month_of(add_months(month, 1))
    return nth_business_day(year, number, PUBLICATION_DAY)
