"""The plugin's data role class: each pool's and REMIC class's factor the
deployment's records name, from its GSE's monthly files, into the lake.

**What is recorded** (contract v29, W10.4; rulings 680, 749 and 995). A
reader asks the lake for a pool's or a class's factors (`ListFactors`); a
pool the lake holds none of is wanted, standing, of the dataset of its GSE
(`fannie_mae`, `freddie_mac`). The plugin reads the record the want names
(ResolveInstrument): a pool by its agency and pool number -- its
`mbs_pool` terms, or its `agency_pool` identifier, the identifier's source
the agency's code --, confirmed to resolve to that record alone
(ResolveIdentifier, a pool number meeting two records reported ambiguous and
never recorded); a class by its agency, deal and class name (`cmo_tranche`).
It records each factor the agency's files state for it over the last
thirteen months, against the want, and keeps the want current: each new
month's factor and each republication, as the files are read again.
A record of another agency, or of no pool or class, is declined not covered;
a pool or class no file names, source silent.

**Each factor** (`meridian.helpers.debt.factor`): its subject the record's
`INS-` (or `LCL-`) ID, its row key the agency's code, the pool or the deal
and class, and the factor month (`FNMA:MA5123:202610`, as the contract's
fixtures key it), the factor exactly as published, its factor month, record
date and payment date (days.py), its business date and published time the
files' publication (the fourth business day, 4:30 p.m. Eastern); a pool's
WAC, WAM and WALA as the security-level file states them (S-19, S-23,
S-24); a floating or inverse floating class's period coupon (RF-08). Its raw
record is the file it was read from, at the row's line. A factor published
again changed is the row's next version, which the lake numbers.

**Its terms** (the `reference` role, terms.py): each record a factor was
recorded for is offered the terms the same row states.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import meridian
from meridian.helpers import debt
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import Latency, data

from . import days
from .agencies import AGENCIES, BY_CODE, BY_ENUM, BY_KEY, Agency
from .layouts import ClassRow, PoolRow
from .library import Found, Library

log = logging.getLogger("gse_disclosures")

FACTOR = "meridian.v1.Factor"
#: How many months of factors a want is answered with: a year and the
#: month in effect.
HISTORY_MONTHS = 13
NEW_YORK = ZoneInfo("America/New_York")
#: When the monthly files are published, New York time.
PUBLISHED_AT = time(16, 30)
FLOATING = {ops.INTEREST_TYPE_FLOATER, ops.INTEREST_TYPE_INVERSE_FLOATER}


def _ns(moment: datetime) -> int:
    return int(moment.timestamp()) * 1_000_000_000 + moment.microsecond * 1000


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Security:
    """A pool or a class a want names, as its record states it."""

    subject: str
    agency: Agency
    pool: str = ""
    trust: str = ""
    class_name: str = ""
    delay_days: int = 0
    payment_day: int = 0
    record_rule: int = 0
    floating: bool = False
    record: ops.InstrumentRecord | None = None

    @property
    def is_pool(self) -> bool:
        return bool(self.pool)

    @property
    def named(self) -> str:
        return self.pool if self.is_pool else f"{self.trust}:{self.class_name}"


def identify(record: ops.InstrumentRecord) -> Security | None:
    """The pool or class a record is, by its GSE's names for it; None for a
    record of no pool or class of Fannie Mae's or Freddie Mac's."""
    subject = record.instrument_id
    if record.instrument_type == ops.INSTRUMENT_TYPE_MBS_POOL or record.HasField("mbs_pool"):
        terms = record.mbs_pool
        agency = BY_ENUM.get(ops.MortgageAgency.Name(terms.agency))
        pool = terms.pool_number
        for held in record.identifiers:
            if held.scheme == "agency_pool" and BY_CODE.get(held.source.upper()) is not None:
                agency = agency or BY_CODE[held.source.upper()]
                pool = pool or held.value
        if agency is None or not pool:
            return None
        return Security(
            subject, agency, pool=pool, delay_days=terms.payment_delay_days,
            payment_day=terms.payment_day, record_rule=terms.record_date_rule, record=record,
        )  # fmt: skip
    if record.instrument_type == ops.INSTRUMENT_TYPE_CMO_TRANCHE or record.HasField("cmo_tranche"):
        terms = record.cmo_tranche
        agency = BY_ENUM.get(ops.MortgageAgency.Name(terms.agency))
        if agency is None or not terms.deal or not terms.class_name:
            return None
        return Security(
            subject, agency, trust=terms.deal, class_name=terms.class_name,
            delay_days=terms.payment_delay_days, payment_day=terms.payment_day,
            record_rule=terms.record_date_rule,
            floating=bool(FLOATING & set(terms.interest_types)), record=record,
        )  # fmt: skip
    return None


def latest_effective(today: date) -> str:
    """The latest month whose factors are published by `today`: this
    month's once its fourth business day has come, else last month's."""
    this = f"{today.year:04d}{today.month:02d}"
    if today >= days.nth_business_day(today.year, today.month, days.PUBLICATION_DAY):
        return this
    return days.add_months(this, -1)


class Disclosures(data.Role):
    """The data role's class (open-meridian 0.35: each role one class),
    its acts made on itself: registered with `meridian.run`, or bound to the
    suite's `Recorder` in its tests."""

    def __init__(
        self,
        library: Library,
        now: Callable[[], datetime] = utc_now,
        terms: Any = None,
    ) -> None:
        self.library = library
        self.now = now
        #: The reference role's class, offered each record's terms.
        self.terms = terms
        self.wants = data.Wants(self, tuple(BY_KEY), clock_ns=lambda: _ns(self.now()))
        # Contract v28 (ruling 518): each factor recorded unasked or for a
        # standing want has its age at the edge recorded from its published
        # time, reported every 10 seconds.
        self.latency = Latency(self, clock_ns=lambda: _ns(self.now()))
        self.wants.latency = self.latency
        #: The pools and classes standing wants name, by subject.
        self.held: dict[str, Security] = {}
        self.last_check: datetime | None = None
        self.error = ""

    def dataset(self, agency: Agency) -> str:
        return self.wants.dataset(agency.key)

    def today(self) -> date:
        """New York's day: the samples' own with sample data, else now."""
        fixed = getattr(self.library.source, "today", None)
        moment = fixed() if callable(fixed) else self.now()
        return moment.astimezone(NEW_YORK).date()

    # ── Resolving ───────────────────────────────────────────────────────

    async def security(self, subject: str, as_of_ns: int) -> Security | None:
        """The pool or class a subject is, read from its record; None where
        the deployment holds no such record or it is no GSE's pool or class."""
        found = await self.resolve_instrument(instrument_id=subject, as_of_ns=as_of_ns)
        if not found.found:
            return None
        return identify(found.instrument)

    async def confirmed(self, security: Security, as_of_ns: int) -> bool:
        """Whether a pool's number resolves to its record alone: one meeting
        two records is reported ambiguous, and nothing is recorded for it."""
        if not security.is_pool:
            return True
        named = [
            meridian.Identifier(
                scheme="agency_pool", value=security.pool, source=security.agency.code
            )
        ]
        found = await self.resolve_identifier(identifiers=named, as_of_ns=as_of_ns)
        if found.found and found.instrument_id == security.subject:
            return True
        if not found.found and found.miss_reason == ops.MISS_REASON_AMBIGUOUS:
            await self.report_missing_instrument(
                source=security.agency.code,
                identifiers=named,
                as_of_ns=as_of_ns,
                reason=ops.MISS_REASON_AMBIGUOUS,
            )
            return False
        # Matched elsewhere or not matched by the number alone: the record the
        # want names is the subject, as it states the pool.
        return True

    # ── Rows ────────────────────────────────────────────────────────────

    def factor(self, security: Security, found: Found) -> meridian.Factor:
        """One row found, as the lake's `Factor`."""
        row = found.row
        agency = security.agency
        if isinstance(row, PoolRow):
            month = days.factor_month(row.effective)
            delay = row.delay_days or security.delay_days
            paid = days.payment_date(month, delay) if delay else None
            if paid is not None and security.payment_day:
                paid = days.on_or_after(paid.replace(day=security.payment_day))
            record: date | None = days.record_date(month)
            key = f"{agency.code}:{row.pool}:{month}"
            coupon = None
        else:
            assert isinstance(row, ClassRow)
            month = days.factor_month(row.distribution)
            year, number = days.month_of(row.distribution)
            day = security.payment_day or found.payment_day
            paid = days.on_or_after(date(year, number, day)) if day else None
            record = (
                days.record_date(month)
                if security.record_rule == ops.RECORD_DATE_RULE_LAST_DAY_OF_PRIOR_MONTH
                else None
            )
            key = f"{agency.code}:{row.trust}:{row.class_name}:{month}"
            coupon = row.interest_rate if security.floating else None
        on = days.published(month)
        made = debt.factor(
            security.subject,
            row.factor,
            month,
            dataset=self.dataset(agency),
            published=on,
            record_date=record.isoformat() if record else "",
            payment_date=paid.isoformat() if paid else "",
            coupon_rate=coupon,
            wac=row.wac if isinstance(row, PoolRow) else None,
            wam=row.wam if isinstance(row, PoolRow) else None,
            wala=row.wala if isinstance(row, PoolRow) else None,
            raw=self.plugin.raw_record(f"{found.kept.key}#{row.line}"),
        )
        at = datetime.combine(on, PUBLISHED_AT, NEW_YORK)
        assert made.meta is not None
        meta = dataclasses.replace(
            made.meta,
            row_key=key,
            source_times=[meridian.SourceTime(kind="published", at_ns=_ns(at))],
        )
        return dataclasses.replace(made, meta=meta)

    async def rows(
        self, securities: list[Security], months: list[str], again: bool = False
    ) -> list[tuple[Security, Found]]:
        """Each security's rows over the months named, oldest month first."""
        out: list[tuple[Security, Found]] = []
        for agency in AGENCIES:
            mine = [s for s in securities if s.agency.key == agency.key]
            pools = [s for s in mine if s.is_pool]
            classes = [s for s in mine if not s.is_pool]
            if not mine:
                continue
            for effective in months:
                month = await self.library.read(agency, effective, again=again)
                if pools:
                    found = self.library.pools(month, [s.pool for s in pools])
                    out += [(s, found[s.pool.upper()]) for s in pools if s.pool.upper() in found]
                if classes:
                    named = self.library.classes(month, [(s.trust, s.class_name) for s in classes])
                    out += [
                        (s, named[(s.trust, s.class_name)])
                        for s in classes
                        if (s.trust, s.class_name) in named
                    ]
        return out

    async def record(self, found: list[tuple[Security, Found]], want_id: str = "") -> int:
        """The rows found, recorded to each agency's dataset; their terms
        offered."""
        sent = 0
        for agency in AGENCIES:
            factors = [self.factor(s, f) for s, f in found if s.agency.key == agency.key]
            if factors:
                sent += await self.wants.record("factors", factors, agency.key, want_id)
        if self.terms is not None:
            for security, row in found:
                await self.terms.offer(security, row)
        return sent

    def months(self) -> list[str]:
        """The months a want is answered with, oldest first."""
        latest = latest_effective(self.today())
        return [days.add_months(latest, -n) for n in range(HISTORY_MONTHS - 1, -1, -1)]

    # ── Wants ───────────────────────────────────────────────────────────

    async def on_observations_wanted(
        self, heard: meridian.Heard[ops.ObservationsWantedEvent]
    ) -> None:
        """What the lake wants of the plugin's datasets: recorded, or declined
        (the SDK's `Wants.hear`, answered by `answer`)."""
        await self.wants.hear(heard, self.answer)

    async def answer(
        self,
        want: ops.ObservationsWantedEvent,
        key: str,
        subjects: list[str],
        kinds: tuple[int, ...],
    ) -> dict[str, str]:
        """One want answered from the agency's files: each factor recorded
        against it, and each subject declined with why."""
        agency = BY_KEY.get(key)
        if agency is None or want.data_type != FACTOR:
            return dict.fromkeys(subjects, "not_covered")
        as_of = _ns(self.now())
        declined: dict[str, str] = {}
        securities: list[Security] = []
        for subject in subjects:
            security = await self.security(subject, as_of)
            if (
                security is None
                or security.agency.key != agency.key
                or not await self.confirmed(security, as_of)
            ):
                declined[subject] = "not_covered"
            else:
                securities.append(security)
        found = await self.rows(securities, self.months())
        named = {s.subject for s, _ in found}
        for security in securities:
            if security.subject not in named:
                declined[security.subject] = "source_silent"
        await self.record(found, want.want_id)
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
                self.held[security.subject] = security
            self.wants.stand(want, [s.subject for s in kept], kinds)
        return declined

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        """A standing want no reader renewed: its pools and classes no longer
        kept current, unless another standing want names them."""
        self.wants.withdraw(heard.message.want_id)
        still = {s for w in self.wants.standing.values() for s in w.subjects}
        for subject in [s for s in self.held if s not in still]:
            del self.held[subject]

    # ── Keeping current ─────────────────────────────────────────────────

    async def check(self) -> int:
        """Read the latest two months' files again, and record each held
        pool's and class's rows: a new month's factor, or one republished.
        How many rows were sent."""
        self.last_check = self.now()
        if not self.held:
            return 0
        latest = latest_effective(self.today())
        months = [days.add_months(latest, -1), latest]
        try:
            found = await self.rows(list(self.held.values()), months, again=True)
            sent = await self.record(found)
        except (OSError, meridian.MeridianError) as failed:
            self.error = str(failed)
            raise
        self.error = ""
        log.info("checked %s and %s: %d factors sent", *months, sent)
        return sent


def checked_at(feed: Disclosures) -> str:
    """When the files were last checked, as Connection says it."""
    held = feed.last_check
    return held.astimezone(UTC).isoformat(timespec="seconds") if held else ""


__all__ = ["Disclosures", "Security", "identify", "latest_effective"]
