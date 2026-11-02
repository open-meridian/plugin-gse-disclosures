"""The aligned layouts read: Freddie Mac's published REMIC factor sample
(tests/responses/, as Freddie Mac publishes it with its technical resources,
randomised data) and the security-level rows of the samples."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from gse_disclosures.layouts import (
    ClassRow,
    PoolRow,
    Unread,
    class_row,
    lines,
    month_from,
    pool_row,
    same_deal,
    text_of,
)

TESTS = Path(__file__).parent / "responses"
SAMPLES = Path(__file__).parent.parent / "src" / "gse_disclosures" / "samples"


def test_freddie_macs_published_remic_sample() -> None:
    text = text_of((TESTS / "freddie-remic-factor-sample.txt").read_bytes())
    read = [class_row(n, f) for n, f in lines(text)]
    assert read[0] is None  # the header
    rows = [r for r in read if isinstance(r, ClassRow)]
    unread = [r for r in read if isinstance(r, Unread)]
    assert len(rows) + len(unread) == len(read) - 1
    first = rows[0]
    assert (first.trust, first.class_name, first.cusip) == ("101", "1", "12325VRK2")
    assert (first.factor, first.interest_rate, first.distribution) == (
        Decimal("0.03580942"),
        Decimal("3.50000"),
        "201607",
    )
    assert first.maturity == "204502" and first.issuance_upb == Decimal("9884543.00")
    accreting = next(r for r in rows if r.class_name == "VZ")
    assert accreting.accretion_factor == Decimal("0.00256321")
    # "N/AP" is not stated.
    assert next(r for r in rows if r.class_name == "AI").accretion_factor is None


def test_a_security_level_row() -> None:
    text = text_of((SAMPLES / "FNM_MF_202611.txt").read_bytes())
    [(number, fields), _] = list(lines(text))
    assert len(fields) == 99
    row = pool_row(number, fields)
    assert isinstance(row, PoolRow)
    assert (row.prefix, row.pool, row.effective, row.factor) == (
        "CL",
        "MA5123",
        "202611",
        Decimal("0.83102210"),
    )
    assert (row.delay_days, row.issuer, row.issue_date, row.maturity) == (
        55,
        "FNM",
        date(2023, 9, 1),
        "205309",
    )
    assert (row.net_rate, row.wac, row.wam, row.wala) == (
        Decimal("5.500"),
        Decimal("6.512"),
        331,
        27,
    )
    assert not row.corrected and not row.preliminary


def test_a_zipped_file_is_read_from_its_member() -> None:
    held = io.BytesIO()
    with zipfile.ZipFile(held, "w") as archive:
        archive.writestr("fd261105.txt", "a|b\n")
    assert text_of(held.getvalue()) == "a|b\n"


def test_what_does_not_read_is_said() -> None:
    short = pool_row(3, ["CL", "MA5123"])
    assert isinstance(short, Unread) and "columns" in short.why
    fields = ["CL", "MA5123", "", "132026"] + ["0.5"] * 30
    assert isinstance(pool_row(4, fields), Unread)
    fields = ["CL", "MA5123", "", "112026", "not a number"] + [""] * 30
    unread = pool_row(5, fields)
    assert isinstance(unread, Unread) and "S-05" in unread.why
    assert month_from("102026") == "202610" and month_from("2026-10") == ""


def test_a_deal_named_as_its_agency_writes_it() -> None:
    assert same_deal("FNR 2016-045", "2016-045")
    assert same_deal("2016-045", "2016045")
    assert not same_deal("2016-045", "2016-45")
    assert not same_deal("", "")
