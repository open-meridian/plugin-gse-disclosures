"""The data and reference suites (meridian.suites) at contract v29, each case
the GSEs' files present mapped to the plugin's own work on the samples.

**Data.** Presented: `records-a-pools-factor` (Fannie Mae's pool MA5123,
September's and October's factors); `an-asset-that-does-not-resolve` (a
pool's number meeting two records, reported ambiguous); `a-subject-declined`
(a bond asked of a pool's dataset); `a-standing-want-withdrawn`;
`reads-its-datasets-licences`; `reports-its-feed-delay` (each factor's age
from its published time, the fourth business day at 4:30 p.m. Eastern); and
the cases the SDK answers. Every other case is about a kind of data the GSEs'
files never state, or work the plugin never does, and is not presented, with
why.

**Reference.** Presented: `fills-a-template` (the pool's record read, its
template read, its terms offered), `licensed-vendor-value-stays` (every value
is the agency's, under the deployment's terms, offered and kept in the
deployment), `offers-never-overwrite-a-person` (a person's value stands: the
plugin offers, never sets), `reads-the-record-it-fills`,
`resolves-a-security-it-reconciles` (the pool's number resolved read-only),
and the cases the SDK answers. Not presented: calendars and settlement dates,
which its work never uses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data.testing import feed_delay
from meridian.suites import ANSWERED_BY_SDK, Recorder, run, suite

from gse_disclosures.feed import Disclosures, identify
from gse_disclosures.terms import Terms

from conftest import (
    BOND,
    FANNIE_POOL,
    INSTANCE,
    answering,
    feed,
    library,
    records,
    want,
)

#: Why the GSEs' files present no case about each kind of data or work.
WHY = {
    "closes": "it records factors, never prices",
    "bars": "it records factors, never prices",
    "a currency's rate against another currency": "it records factors, never prices",
    "a crypto asset's price": "it records factors, never prices",
    "prices on a venue": "it records factors, never prices",
    "a security's price": "it records factors, never prices",
    "trades": "it records factors, never trades",
    "quotes": "it records factors, never quotes",
    "outcomes": "it records factors; no event contract's outcome",
    "disputed outcomes": "it records factors; no event contract's outcome",
    "rates": "it records factors, never rates",
    "streams": "it reads the agencies' monthly files daily and streams nothing",
    "option chains": "it lists no option chains",
    "filings": "it publishes no filings",
    "holdings": "it publishes no holdings",
    "corporate actions": "it publishes no corporate actions",
    "ratings": "it publishes no ratings",
    "derived series": "it publishes no figure of its own",
    "calendars": (
        "it dates each factor by the agencies' stated payment delays and the Federal Reserve's "
        "holidays, which their publication and payment schedules follow; it reads no calendar"
    ),
    "settlement dates": "it records factors as published; it never computes a settlement date",
}

DATA_PRESENTED = {
    "records-a-pools-factor",
    "an-asset-that-does-not-resolve",
    "a-subject-declined",
    "a-standing-want-withdrawn",
    "reads-its-datasets-licences",
    "reports-its-feed-delay",
}
REFERENCE_PRESENTED = {
    "fills-a-template",
    "licensed-vendor-value-stays",
    "offers-never-overwrite-a-person",
    "reads-the-record-it-fills",
    "resolves-a-security-it-reconciles",
}


def not_presented(role: str, presented: set[str]) -> dict[str, str]:
    return {
        case.name: WHY[case.about]
        for case in suite(role).cases
        if case.name not in presented and case.name not in ANSWERED_BY_SDK
    }


DATA_NOT_PRESENTED = not_presented("data", DATA_PRESENTED)
REFERENCE_NOT_PRESENTED = not_presented("reference", REFERENCE_PRESENTED)

Producer = Callable[[Recorder], Awaitable[None]]


def data_producers(tmp: Path) -> dict[str, Producer]:
    made = iter(range(100))

    def wanted(subjects: list[str], ambiguous: bool = False) -> Producer:
        async def produce(recorder: Recorder) -> None:
            answering(recorder, ambiguous=ambiguous)
            work = feed(recorder, tmp / f"d{next(made)}")
            recorder.answer("ObservationsWanted", lambda _: want("w-1", subjects).message)
            await recorder.hear(work, "ObservationsWanted")

        return produce

    async def withdrawn(recorder: Recorder) -> None:
        answering(recorder)
        work = feed(recorder, tmp / "withdrawn")
        recorder.answer(
            "WantWithdrawn",
            lambda _: ops.WantWithdrawnEvent(want_id="w-1", dataset=f"{INSTANCE}:fannie_mae"),
        )
        await recorder.hear(work, "WantWithdrawn")

    async def licences(recorder: Recorder) -> None:
        dataset = f"{INSTANCE}:fannie_mae"
        recorder.answer(
            "ListDatasets",
            lambda _: ops.ListDatasetsResult(licences=[ops.DatasetLicence(dataset=dataset)]),
        )
        work = feed(recorder, tmp / "licences")
        await work.wants.read_licences()
        assert work.wants.licensed == {dataset}

    async def delayed(recorder: Recorder, latency: Any) -> None:
        answering(recorder)
        work = feed(recorder, tmp / "delayed")
        work.wants.latency = latency
        recorder.answer("ObservationsWanted", lambda _: want("w-5", [FANNIE_POOL]).message)
        await recorder.hear(work, "ObservationsWanted")
        await work.check()

    return {
        "records-a-pools-factor": wanted([FANNIE_POOL]),
        "an-asset-that-does-not-resolve": wanted([FANNIE_POOL], ambiguous=True),
        "a-subject-declined": wanted([BOND]),
        "a-standing-want-withdrawn": withdrawn,
        "reads-its-datasets-licences": licences,
        "reports-its-feed-delay": feed_delay(delayed),
    }


def reference_producers(tmp: Path) -> dict[str, Producer]:
    made = iter(range(100))

    async def offered(recorder: Recorder, record: ops.InstrumentRecord | None = None) -> None:
        answering(recorder)
        if record is not None:
            recorder.answer(
                "ResolveInstrument",
                lambda _: ops.ResolveInstrumentResult(found=True, instrument=record),
            )
        security = identify(records()[FANNIE_POOL])
        assert security is not None
        rows = await Disclosures(library(tmp / f"r{next(made)}")).rows([security], ["202611"])
        terms = recorder.bind(Terms())
        assert await terms.offer(security, rows[0][1])

    async def a_persons_value(recorder: Recorder) -> None:
        # A person set the pool's original face; the plugin offers the
        # agency's, which never replaces it (W3.10).
        record = records()[FANNIE_POOL]
        record.sources.add(person="ada", note="original face as the custodian states it")
        await offered(recorder, record)

    return {
        "fills-a-template": offered,
        "licensed-vendor-value-stays": offered,
        "offers-never-overwrite-a-person": a_persons_value,
        "reads-the-record-it-fills": offered,
        "resolves-a-security-it-reconciles": offered,
    }


def test_the_data_suite_passes(tmp_path: Path) -> None:
    report = run(
        "data", data_producers(tmp_path), not_presented=DATA_NOT_PRESENTED, instance_id=INSTANCE
    )
    assert report.passed, report.failures
    assert set(report.passed_cases) == DATA_PRESENTED | set(ANSWERED_BY_SDK)
    assert sorted(report.not_presented) == sorted(DATA_NOT_PRESENTED)


def test_the_reference_suite_passes(tmp_path: Path) -> None:
    report = run(
        "reference",
        reference_producers(tmp_path),
        not_presented=REFERENCE_NOT_PRESENTED,
        instance_id=INSTANCE,
    )
    assert report.passed, report.failures
    assert set(report.passed_cases) == REFERENCE_PRESENTED | set(ANSWERED_BY_SDK)
    assert sorted(REFERENCE_NOT_PRESENTED) == ["asks-for-a-settlement-date", "reads-a-calendar"]
