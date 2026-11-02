"""The data role on the samples: a pool's and a class's factors recorded when
the lake wants them, kept current, republished as the next version, and
what it does not serve declined with why."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from gse_disclosures import days
from gse_disclosures.feed import identify, latest_effective
from gse_disclosures.terms import Terms

from conftest import (
    BOND,
    FANNIE_POOL,
    FREDDIE_CLASS,
    FREDDIE_FIXED_CLASS,
    FREDDIE_POOL,
    INSTANCE,
    NOT_PUBLISHED,
    answering,
    factors,
    feed,
    records,
    want,
)


def recorder() -> Recorder:
    return answering(Recorder(INSTANCE))


async def test_a_pools_factors_as_the_fixtures_key_them(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [FANNIE_POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    rows = factors(lake)
    assert [(r.meta.row_key, str(as_decimal(r.factor)), r.factor_month) for r in rows] == [
        ("FNMA:MA5123:202609", "0.84017733", "202609"),
        ("FNMA:MA5123:202610", "0.83102210", "202610"),
    ]
    october = rows[1]
    assert (october.record_date, october.payment_date) == ("2026-10-31", "2026-11-25")
    # September's payment day, the 25th, a Sunday: the next business day.
    assert rows[0].payment_date == "2026-10-26"
    assert october.meta.business_date == "2026-11-05"
    assert october.meta.subjects[0].entity_id == FANNIE_POOL
    assert october.meta.source.dataset == f"{INSTANCE}:fannie_mae"
    assert october.meta.raw.key.endswith("#1")
    assert (str(as_decimal(october.wac)), october.wam, october.wala) == ("6.512", 331, 27)
    assert not october.HasField("coupon_rate")
    assert [p.want_id for p in lake.on("RecordFactors")] == ["w-1"]
    assert FANNIE_POOL in work.held
    assert not lake.on("DeclineWant")


async def test_a_republication_is_the_rows_next_version(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [FANNIE_POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    sent = await work.check()
    assert sent == 2
    again = lake.on("RecordFactors")[-1].factors
    assert [(r.meta.row_key, str(as_decimal(r.factor))) for r in again] == [
        ("FNMA:MA5123:202609", "0.84017733"),
        ("FNMA:MA5123:202610", "0.83102211"),
    ]
    counted = work.wants.sent_to("fannie_mae")
    assert (counted.recorded, counted.restated, counted.unchanged) == (2, 1, 1)


async def test_a_freddie_mac_pool_and_classes(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer(
        "ObservationsWanted",
        lambda _: (
            want(
                "w-2", [FREDDIE_POOL, FREDDIE_CLASS, FREDDIE_FIXED_CLASS], key="freddie_mac"
            ).message
        ),
    )
    await lake.hear(work, "ObservationsWanted")
    rows = {r.meta.row_key: r for r in factors(lake)}
    assert sorted(rows) == [
        "FHLMC:5XXX05:A:202609", "FHLMC:5XXX05:A:202610",
        "FHLMC:5XXX05:EF:202609", "FHLMC:5XXX05:EF:202610",
        "FHLMC:QF0001:202609", "FHLMC:QF0001:202610",
    ]  # fmt: skip
    floater = rows["FHLMC:5XXX05:EF:202610"]
    assert str(as_decimal(floater.coupon_rate)) == "5.43875"
    assert floater.payment_date == "2026-11-25" and not floater.record_date
    assert not rows["FHLMC:5XXX05:A:202610"].HasField("coupon_rate")
    # The October pool file read from its zip.
    assert str(as_decimal(rows["FHLMC:QF0001:202610"].factor)) == "0.92554310"


async def test_what_it_does_not_serve_is_declined_with_why(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer(
        "ObservationsWanted",
        lambda _: want("w-3", [BOND, FREDDIE_POOL, NOT_PUBLISHED, "INS-UNKNOWN"]).message,
    )
    await lake.hear(work, "ObservationsWanted")
    declined = {
        (s.entity_id, ops.UnansweredReason.Name(p.reason))
        for p in lake.on("DeclineWant")
        for s in p.subjects
    }
    assert declined == {
        (BOND, "UNANSWERED_REASON_NOT_COVERED"),
        # Freddie Mac's pool, asked of Fannie Mae's dataset.
        (FREDDIE_POOL, "UNANSWERED_REASON_NOT_COVERED"),
        (NOT_PUBLISHED, "UNANSWERED_REASON_SOURCE_SILENT"),
        ("INS-UNKNOWN", "UNANSWERED_REASON_NOT_COVERED"),
    }
    assert not factors(lake)


async def test_a_pool_number_meeting_two_records_is_never_recorded(tmp_path: Path) -> None:
    lake = answering(Recorder(INSTANCE), ambiguous=True)
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-4", [FANNIE_POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    [missing] = lake.on("ReportMissingInstrument")
    assert missing.reason == ops.MISS_REASON_AMBIGUOUS
    assert not factors(lake)


async def test_a_withdrawn_want_is_no_longer_kept_current(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [FANNIE_POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    lake.answer(
        "WantWithdrawn",
        lambda _: ops.WantWithdrawnEvent(want_id="w-1", dataset=f"{INSTANCE}:fannie_mae"),
    )
    await lake.hear(work, "WantWithdrawn")
    assert not work.held
    assert await work.check() == 0


async def test_terms_offered_to_the_pools_record(tmp_path: Path) -> None:
    lake = recorder()
    terms = lake.bind(Terms())
    work = feed(lake, tmp_path, terms=terms)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [FANNIE_POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    offers = lake.on("OfferTemplateFields")
    assert len(offers) == 2  # once for each month's file
    latest = {f.path: f.value for f in offers[-1].fields}
    assert latest == {
        "agency": "MORTGAGE_AGENCY_FNMA",
        "pool_number": "MA5123",
        "program": "CL",
        "pass_through_rate": "5.500",
        "issue_date": "2023-09-01",
        "maturity_date": "2053-09-01",
        "original_face": "1250000000.00",
        "payment_delay_days": "55",
        "payment_day": "25",
        "record_date_rule": "RECORD_DATE_RULE_LAST_DAY_OF_PRIOR_MONTH",
    }
    assert offers[-1].template_id == "TPL-mbs-pool" and offers[-1].template_version == "1"
    kinds = {f.path: ops.ProvenanceKind.Name(f.provenance.kind) for f in offers[-1].fields}
    assert kinds["original_face"] == "PROVENANCE_KIND_REPORTED"
    assert kinds["payment_day"] == "PROVENANCE_KIND_DERIVED"
    # The same contents again offer nothing more.
    await work.check()
    assert len(lake.on("OfferTemplateFields")) == 3  # the republished file, once


def test_the_dates_of_a_factor() -> None:
    assert days.factor_month("202611") == "202610"
    assert days.record_date("202610") == date(2026, 10, 31)
    assert days.payment_date("202610", 55) == date(2026, 11, 25)
    assert days.payment_date("202610", 45) == date(2026, 11, 16)  # the 15th, a Sunday
    assert days.payment_date("202610", 75) == date(2026, 12, 15)
    assert days.payment_date("202610", 30) is None
    assert days.published("202609") == date(2026, 10, 6)
    assert days.published("202610") == date(2026, 11, 5)
    assert date(2026, 11, 26) in days.holidays(2026)  # Thanksgiving
    assert date(2026, 7, 3) not in days.holidays(2026)  # a Saturday's is not moved
    assert latest_effective(date(2026, 11, 4)) == "202610"
    assert latest_effective(date(2026, 11, 5)) == "202611"


def test_a_record_is_identified_by_its_terms_or_its_identifier() -> None:
    held = records()
    fannie = identify(held[FANNIE_POOL])
    assert fannie is not None and (fannie.agency.key, fannie.pool) == ("fannie_mae", "MA5123")
    bare = ops.InstrumentRecord(
        instrument_id="LCL-POOL",
        instrument_type=ops.INSTRUMENT_TYPE_MBS_POOL,
        identifiers=[ops.Identifier(scheme="agency_pool", value="QF0001", source="FHLMC")],
    )
    freddie = identify(bare)
    assert freddie is not None and (freddie.agency.key, freddie.pool) == ("freddie_mac", "QF0001")
    assert identify(held[BOND]) is None
    floater = identify(held[FREDDIE_CLASS])
    assert floater is not None and floater.floating and floater.named == "5XXX05:EF"
    assert Decimal("0") == Decimal(0)


async def test_checks_again_send_nothing_new(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [FANNIE_POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    await work.check()
    before = {k: v[0] for k, v in lake._answers["RecordFactors"].versions.items()}  # type: ignore[attr-defined]
    await work.check()
    await work.check()
    after = {k: v[0] for k, v in lake._answers["RecordFactors"].versions.items()}  # type: ignore[attr-defined]
    assert after == before
