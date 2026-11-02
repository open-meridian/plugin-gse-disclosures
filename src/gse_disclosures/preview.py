"""The pages on sample data, each printed as one HTML file, for looking at
them without a deployment:

    python -m gse_disclosures.preview connection > preview/connection.html
    python -m gse_disclosures.preview datasets > preview/datasets.html

The plugin's work runs on a recorder standing in for the sidecar, the
samples' records held: a want for the Fannie Mae pool answered and kept
current, one for a bond declined, then the daily check. Each page links the
kit where the dashboard serves it; `make preview SHOTS=...` checks each in a
browser with the kit.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import meridian
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder
from meridian.testing import PageClient

from .feed import Disclosures
from .files import Samples, Store
from .library import Library
from .page import hold, pages
from .terms import Terms

AT = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
INSTANCE = "gse-disclosures"
PAGES = {"connection": "/", "datasets": "/datasets"}
#: The records the preview holds, resolved by their identifiers at its start.
held: dict[str, str] = {}


def _record(params: Any) -> ops.ResolveInstrumentResult:
    if params.instrument_id != held["pool"]:
        return ops.ResolveInstrumentResult(
            found=True,
            instrument=ops.InstrumentRecord(
                instrument_id=params.instrument_id, instrument_type=ops.INSTRUMENT_TYPE_BOND
            ),
        )
    record = ops.InstrumentRecord(
        instrument_id=held["pool"],
        instrument_type=ops.INSTRUMENT_TYPE_MBS_POOL,
        identifiers=[ops.Identifier(scheme="agency_pool", value="MA5123", source="FNMA")],
        template_id="TPL-mbs-pool",
        template_version="1",
    )
    record.mbs_pool.agency = ops.MORTGAGE_AGENCY_FNMA
    record.mbs_pool.pool_number = "MA5123"
    return ops.ResolveInstrumentResult(found=True, instrument=record)


def _want(want_id: str, subject: str) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=f"{INSTANCE}:fannie_mae",
            data_type="meridian.v1.Factor",
            subjects=[ops.SubjectRef(entity_id=subject)],
            standing=True,
        ),
    )


async def sampled() -> tuple[Disclosures, Terms]:
    recorder = Recorder(INSTANCE)
    terms = recorder.bind(Terms())
    library = Library(Samples(), Store(Path(tempfile.mkdtemp(prefix="gse-preview-"))))
    feed = recorder.bind(Disclosures(library, now=lambda: AT, terms=terms))
    # The pool and a bond, as the deployment would hold them: resolved by
    # what each states.
    for name, scheme, value, source in (
        ("pool", "agency_pool", "MA5123", "FNMA"),
        ("bond", "figi", "BBG01BOND0001", ""),
    ):
        found = await feed.resolve_identifier(
            identifiers=[meridian.Identifier(scheme=scheme, value=value, source=source)],
            stated_description=name,
            stated_currency="USD",
        )
        held[name] = found.instrument_id
    recorder.answer("ResolveInstrument", _record)
    recorder.answer(
        "ResolveIdentifier",
        lambda _: ops.ResolveIdentifierResult(found=True, instrument_id=held["pool"]),
    )
    for want_id, subject in (("want-pool", held["pool"]), ("want-bond", held["bond"])):
        await feed.on_observations_wanted(_want(want_id, subject))
    await feed.check()
    return feed, terms


def render(page: str) -> str:
    feed, terms = asyncio.run(sampled())
    hold(feed, terms)
    answer = PageClient(pages).get(PAGES[page], "admin")
    if answer.status != 200:
        raise SystemExit(f"{page} answered {answer.status}: {answer.text[:200]}")
    return answer.text


def main() -> None:
    page = sys.argv[1] if len(sys.argv) > 1 else "connection"
    if page not in PAGES:
        raise SystemExit(f"no page {page!r}: {', '.join(PAGES)}")
    sys.stdout.write(render(page))


if __name__ == "__main__":
    main()
