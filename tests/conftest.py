"""Shared stand-ins: the deployment's records of a Fannie Mae pool, a Freddie
Mac pool and a Freddie Mac REMIC class, as the platform's templates state
them; the lake answering a batch of factors as it does; the template
catalogue; and the lake's wants as the sidecar delivers them."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder

from gse_disclosures.feed import Disclosures
from gse_disclosures.files import Samples, Source, Store
from gse_disclosures.library import Library
from gse_disclosures.preview import calendar_answer
from gse_disclosures.terms import Terms

INSTANCE = "gse-disclosures-1"
#: A moment after November 2026's publication, as the samples are read.
AT = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)
TESTS = Path(__file__).parent / "responses"

FANNIE_POOL = "INS-01JPOOL00000000000000000001"
FREDDIE_POOL = "INS-01JPOOL00000000000000000002"
FREDDIE_CLASS = "INS-01JCLASS0000000000000000001"
FREDDIE_FIXED_CLASS = "INS-01JCLASS0000000000000000002"
BOND = "INS-01JBOND00000000000000000001"
NOT_PUBLISHED = "INS-01JPOOL00000000000000000009"


def pool(
    instrument_id: str, number: str, agency: ops.MortgageAgency, source: str
) -> ops.InstrumentRecord:
    record = ops.InstrumentRecord(
        instrument_id=instrument_id,
        identifiers=[ops.Identifier(scheme="agency_pool", value=number, source=source)],
        asset_class=ops.ASSET_CLASS_DEBT,
        instrument_type=ops.INSTRUMENT_TYPE_MBS_POOL,
        currency="USD",
        template_id="TPL-mbs-pool",
        template_version="1",
        missing_fields=["original_face", "payment_delay_days", "payment_day"],
    )
    record.mbs_pool.agency = agency
    record.mbs_pool.pool_number = number
    return record


def tranche(
    instrument_id: str, deal: str, name: str, interest: list[ops.InterestType]
) -> ops.InstrumentRecord:
    record = ops.InstrumentRecord(
        instrument_id=instrument_id,
        asset_class=ops.ASSET_CLASS_DEBT,
        instrument_type=ops.INSTRUMENT_TYPE_CMO_TRANCHE,
        currency="USD",
        template_id="TPL-cmo-tranche",
        template_version="1",
    )
    record.cmo_tranche.agency = ops.MORTGAGE_AGENCY_FHLMC
    record.cmo_tranche.deal = deal
    record.cmo_tranche.class_name = name
    record.cmo_tranche.interest_types.extend(interest)
    return record


def records() -> dict[str, ops.InstrumentRecord]:
    bond = ops.InstrumentRecord(
        instrument_id=BOND,
        asset_class=ops.ASSET_CLASS_DEBT,
        instrument_type=ops.INSTRUMENT_TYPE_BOND,
        identifiers=[ops.Identifier(scheme="figi", value="BBG01BOND0001")],
    )
    return {
        FANNIE_POOL: pool(FANNIE_POOL, "MA5123", ops.MORTGAGE_AGENCY_FNMA, "FNMA"),
        FREDDIE_POOL: pool(FREDDIE_POOL, "QF0001", ops.MORTGAGE_AGENCY_FHLMC, "FHLMC"),
        NOT_PUBLISHED: pool(NOT_PUBLISHED, "MA9999", ops.MORTGAGE_AGENCY_FNMA, "FNMA"),
        FREDDIE_CLASS: tranche(FREDDIE_CLASS, "5XXX05", "EF", [ops.INTEREST_TYPE_FLOATER]),
        FREDDIE_FIXED_CLASS: tranche(FREDDIE_FIXED_CLASS, "5XXX05", "A", [ops.INTEREST_TYPE_FIXED]),
        BOND: bond,
    }


#: The fields of the platform's v29 pool and tranche templates (platform
#: `publish_v29_reference`).
TEMPLATES = {
    "TPL-mbs-pool": [
        "identifiers", "description", "currency", "instrument_type", "agency", "program",
        "pool_number", "pass_through_rate", "issue_date", "maturity_date", "original_face",
        "original_term_months", "day_count", "payment_delay_days", "payment_day",
        "record_date_rule", "payment_calendar_id",
    ],
    "TPL-cmo-tranche": [
        "identifiers", "description", "currency", "instrument_type", "agency", "deal",
        "class_name", "issue_date", "principal_types", "interest_types", "original_face",
        "coupon_rate", "floating", "maturity_date", "day_count", "payment_delay_days",
        "payment_day", "record_date_rule", "record_date_days",
    ],
}  # fmt: skip


class Lake:
    """The lake's answer to a batch of factors: a row key new is recorded,
    the same factor again unchanged, a changed one the next version."""

    def __init__(self) -> None:
        self.versions: dict[str, tuple[int, Any]] = {}

    def __call__(self, params: Any) -> ops.RecordFactorsResult:
        recorded = restated = unchanged = 0
        for row in params.factors:
            # As the lake compares them: a row's values, its raw record and
            # business date among them.
            value = (
                as_decimal(row.factor),
                row.payment_date,
                row.meta.raw.key,
                row.meta.business_date,
            )
            held = self.versions.get(row.meta.row_key)
            if held is None:
                self.versions[row.meta.row_key] = (1, value)
                recorded += 1
            elif held[1] == value:
                unchanged += 1
            else:
                self.versions[row.meta.row_key] = (held[0] + 1, value)
                restated += 1
        return ops.RecordFactorsResult(recorded=recorded, restated=restated, unchanged=unchanged)


def answering(recorder: Recorder, ambiguous: bool = False) -> Recorder:
    """A recorder answering as the deployment does: each record read by its
    ID, a pool's number resolved to its record (or meeting two), each
    template read, and the lake recording factors."""
    held = records()

    def read(params: Any) -> ops.ResolveInstrumentResult:
        found = held.get(params.instrument_id)
        if found is None:
            return ops.ResolveInstrumentResult(found=False)
        return ops.ResolveInstrumentResult(found=True, instrument=found)

    def resolve(params: Any) -> ops.ResolveIdentifierResult:
        if ambiguous:
            return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS)
        for record in held.values():
            for named in params.identifiers:
                if any(
                    (i.scheme, i.value, i.source) == (named.scheme, named.value, named.source)
                    for i in record.identifiers
                ):
                    return ops.ResolveIdentifierResult(
                        found=True, instrument_id=record.instrument_id
                    )
        return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND)

    def template(params: Any) -> ops.ReadTemplateResult:
        return ops.ReadTemplateResult(
            template=ops.SecurityTemplate(
                template_id=params.template_id,
                template_version=params.template_version,
                fields=[ops.TemplateField(path=p) for p in TEMPLATES.get(params.template_id, [])],
            )
        )

    recorder.answer("ResolveInstrument", read)
    recorder.answer("ResolveIdentifier", resolve)
    recorder.answer("ReadTemplate", template)
    recorder.answer("RecordFactors", Lake())
    recorder.answer("ReadCalendar", calendar_answer)
    return recorder


def library(tmp: Path, source: Source | None = None) -> Library:
    return Library(source or Samples(), Store(tmp))


def feed(
    recorder: Recorder, tmp: Path, terms: Terms | None = None, source: Source | None = None
) -> Disclosures:
    """The data role's class on the samples, bound to the recorder."""
    return recorder.bind(Disclosures(library(tmp, source), now=lambda: AT, terms=terms))


def want(
    want_id: str,
    subjects: list[str],
    *,
    key: str = "fannie_mae",
    standing: bool = True,
    data_type: str = "meridian.v1.Factor",
) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=f"{INSTANCE}:{key}",
            data_type=data_type,
            subjects=[ops.SubjectRef(entity_id=s) for s in subjects],
            standing=standing,
        ),
    )


def factors(recorder: Recorder) -> list[ops.Factor]:
    return [f for params in recorder.on("RecordFactors") for f in params.factors]
