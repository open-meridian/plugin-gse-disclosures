"""The role logic both agency disclosure plugins hold the same --
`plugin-gse-disclosures` and `plugin-ginnie-mae` (ruling 686) -- kept in this
one module, the same in each repository, until the SDK carries it (proposed
for `meridian.helpers.debt`). Only the agencies' files, layouts and names are
each plugin's own.

- **Business days** (`Days`): the deployment's calendar, read through the
  data role with the SDK's `MarketDays` -- a record's payment calendar, else
  the US dollar's (the Federal Reserve Banks', K.8), the days the agencies
  pay and publish on: a day moved to the next business day, a month's nth
  business day; a day the calendar does not answer for, or outside its
  coverage, not known, never guessed. And a month YYYYMM moved by months.
- **A pool's number confirmed** (`confirmed`): a pool's number under the
  open scheme `agency_pool` resolved, so one meeting two records is reported
  ambiguous (ReportMissingInstrument) and nothing is recorded for it.
- **A factor want answered** (`answer`, W10.7; rulings 680 and 749): each
  subject's record read and identified as a pool or class of the plugin's
  agency, else declined `not_covered`; its rows found over the months asked,
  else declined `source_silent`; what was found recorded against the want,
  and a standing want kept for the subjects found.
- **Terms offered** (`Offers`, W3.23): the record read first
  (ResolveInstrument), a pool's number confirmed to be the record's, the
  template's paths read once (ReadTemplate), and the fields the template has
  offered (OfferTemplateFields), once for each record and file content; a
  refusal said, never raised.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import date, timedelta
from typing import Any

import meridian
from meridian.helpers.calendars import MarketDays
from meridian.plugin.v1 import operations_pb2 as ops

log = logging.getLogger("meridian.agency")

# ── Business days ────────────────────────────────────────────────────────

#: The platform's "US dollar (Federal Reserve Banks)" calendar (currency
#: kind, the Board's K.8 holidays, 2016 to 2030): the days the agencies pay
#: and publish on, P&I moving over Fedwire. A deployment may name its own
#: copy (the `payment_calendar` setting); a record's `payment_calendar_id`
#: goes first.
USD_CALENDAR = "CAL-01M4VF0F3HJ73RFTB0XWVK1B73"


class _Seen:
    """The role's `read_calendar`, each answer's coverage kept: a day outside
    it is not known, never taken as open."""

    def __init__(self, role: Any) -> None:
        self.role = role
        self.coverage: tuple[str, str] | None = None

    async def read_calendar(self, **asked: Any) -> Any:
        answer = await self.role.read_calendar(**asked)
        if answer.found and answer.HasField("coverage"):
            self.coverage = (answer.coverage.from_date, answer.coverage.to_date)
        return answer


class Days:
    """Business days by the deployment's calendars, read through the role
    (`meridian.helpers.calendars.MarketDays`): the calendar a record names,
    else `default`. A day the calendar has not answered for, or outside its
    coverage, is not known: None, never guessed (`error` says why)."""

    def __init__(self, role: Any, default: str = USD_CALENDAR) -> None:
        self.role = role
        self.default = default
        self.calendars: dict[str, tuple[MarketDays, _Seen]] = {}

    def _held(self, calendar_id: str) -> tuple[MarketDays, _Seen]:
        named = calendar_id or self.default
        held = self.calendars.get(named)
        if held is None:
            seen = _Seen(self.role)
            held = (MarketDays(seen, named), seen)
            self.calendars[named] = held
        return held

    @property
    def error(self) -> str:
        return "; ".join(m.error for m, _ in self.calendars.values() if m.error)

    async def open(self, day: date, calendar_id: str = "") -> bool | None:
        market, seen = self._held(calendar_id)
        held = await market.is_open(day)
        if held is None or seen.coverage is None:
            return None
        first, last = seen.coverage
        if (first and day.isoformat() < first) or (last and day.isoformat() > last):
            return None
        return held

    async def on_or_after(self, day: date, calendar_id: str = "") -> date | None:
        """The day, or the next business day after it; None where not known."""
        for _ in range(31):
            held = await self.open(day, calendar_id)
            if held is None:
                return None
            if held:
                return day
            day += timedelta(days=1)
        return None

    async def nth_business_day(
        self, year: int, month: int, n: int, calendar_id: str = ""
    ) -> date | None:
        """A month's nth business day; None where not known."""
        day = await self.on_or_after(date(year, month, 1), calendar_id)
        for _ in range(n - 1):
            if day is None:
                return None
            day = await self.on_or_after(day + timedelta(days=1), calendar_id)
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


# ── A pool's number confirmed ────────────────────────────────────────────


def pool_identifier(pool: str, source: str) -> meridian.Identifier:
    return meridian.Identifier(scheme="agency_pool", value=pool, source=source)


async def resolves_to(role: Any, pool: str, source: str, as_of_ns: int) -> str:
    """The record a pool's number resolves to, or ""."""
    found = await role.resolve_identifier(
        identifiers=[pool_identifier(pool, source)], as_of_ns=as_of_ns
    )
    return str(found.instrument_id) if found.found else ""


async def confirmed(role: Any, pool: str, source: str, as_of_ns: int) -> bool:
    """Whether a pool's number may be recorded against: not where it meets two
    records, which is reported ambiguous."""
    named = [pool_identifier(pool, source)]
    found = await role.resolve_identifier(identifiers=named, as_of_ns=as_of_ns)
    if not found.found and found.miss_reason == ops.MISS_REASON_AMBIGUOUS:
        await role.report_missing_instrument(
            source=source, identifiers=named, as_of_ns=as_of_ns, reason=ops.MISS_REASON_AMBIGUOUS
        )
        return False
    return True


# ── A factor want answered ───────────────────────────────────────────────

#: What a plugin gives `answer`: the security a record is (None for one it
#: does not serve), whether it may be recorded against, its rows over the
#: months -- each (security, row, ...) with `.subject` on the security --,
#: and how they are recorded against a want.
Identify = Callable[[ops.InstrumentRecord], Any]
Confirm = Callable[[Any, int], Awaitable[bool]]
Rows = Callable[[list[Any], list[str]], Awaitable[Sequence[tuple[Any, ...]]]]
Record = Callable[[Sequence[tuple[Any, ...]], str], Awaitable[int]]


async def answer(
    role: Any,
    want: ops.ObservationsWantedEvent,
    subjects: list[str],
    kinds: tuple[int, ...],
    *,
    identify: Identify,
    confirm: Confirm,
    rows: Rows,
    record: Record,
    months: list[str],
    held: dict[str, Any],
    as_of_ns: int,
) -> dict[str, str]:
    """One want of factors answered (see the module): what it declines, by
    subject and reason."""
    declined: dict[str, str] = {}
    securities: list[Any] = []
    for subject in subjects:
        read = await role.resolve_instrument(instrument_id=subject, as_of_ns=as_of_ns)
        security = identify(read.instrument) if read.found else None
        if security is None or not await confirm(security, as_of_ns):
            declined[subject] = "not_covered"
        else:
            securities.append(security)
    found = await rows(securities, months)
    named = {row[0].subject for row in found}
    for security in securities:
        if security.subject not in named:
            declined[security.subject] = "source_silent"
    await record(found, want.want_id)
    kept = [s for s in securities if s.subject in named]
    log.info(
        "want %s: %d of %d subjects found, %d factors, declined %s",
        want.want_id,
        len(kept),
        len(subjects),
        len(found),
        declined or "none",
    )
    if want.standing and kept:
        for security in kept:
            held[security.subject] = security
        role.wants.stand(want, [s.subject for s in kept], kinds)
    return declined


def withdrawn(role: Any, want_id: str, held: dict[str, Any]) -> None:
    """A standing want withdrawn: its subjects no longer kept current unless
    another standing want names them."""
    role.wants.withdraw(want_id)
    still = {s for w in role.wants.standing.values() for s in w.subjects}
    for subject in [s for s in held if s not in still]:
        del held[subject]


# ── Terms offered ────────────────────────────────────────────────────────


class Offers:
    """What a reference role offered, and each template's paths, read once."""

    def __init__(self) -> None:
        self.offered: set[tuple[str, str]] = set()
        self.paths: dict[tuple[str, str], frozenset[str]] = {}
        self.offers = 0
        self.refused = ""

    async def template_paths(self, role: Any, template_id: str, version: str) -> frozenset[str]:
        held = self.paths.get((template_id, version))
        if held is None:
            read = await role.read_template(template_id=template_id, template_version=version)
            held = frozenset(f.path for f in read.template.fields)
            self.paths[(template_id, version)] = held
        return held

    async def offer(
        self,
        role: Any,
        subject: str,
        content: str,
        *,
        template: str,
        values: Callable[[], list[meridian.TemplateFieldValue]],
        pool: tuple[str, str] | None = None,
        as_of_ns: int = 0,
    ) -> bool:
        """Offer `values()` to `subject`'s record at its template (`template`
        where it names none), once for each record and file `content`;
        `pool` (number, source) confirmed to resolve to the record first.
        Whether an offer was made."""
        if (subject, content) in self.offered:
            return False
        self.offered.add((subject, content))
        try:
            read = await role.resolve_instrument(instrument_id=subject, as_of_ns=as_of_ns)
            if not read.found:
                return False
            if pool is not None and await resolves_to(role, *pool, as_of_ns) not in ("", subject):
                # The pool's number names another record: not this one's terms.
                return False
            record = read.instrument
            template_id = record.template_id or template
            version = record.template_version or "1"
            paths = await self.template_paths(role, template_id, version)
            fields = [v for v in values() if v.path in paths]
            if not fields:
                return False
            await role.offer_template_fields(
                instrument_id=subject,
                template_id=template_id,
                template_version=version,
                fields=fields,
            )
        except meridian.MeridianError as refused:
            # An offer refused -- a template not held, a value not of its
            # field's type -- is said, and the factor stands.
            self.refused = str(refused)
            log.warning("terms of %s not offered: %s", subject, refused)
            return False
        self.offers += 1
        log.info(
            "terms of %s offered to %s %s: %s",
            subject,
            template_id,
            version,
            ", ".join(v.path for v in fields),
        )
        return True
