"""The GSEs' aligned disclosure layouts, read: one row of a security-level
file, and one of a multiclass (REMIC) factor file.

Since the Single Security Initiative (2019-06-03) Fannie Mae and Freddie Mac
publish UMBS and their other single-class securities in one aligned
format, and their REMIC classes in another, each a pipe-delimited text file,
zipped (Freddie Mac's Disclosure Guide, its Security Level File; Fannie
Mae's Single-Family Disclosure Guide, its REMIC Factor File; Freddie Mac's
multiclass conversion overview, its aligned factor format).

**Security level file** (S-01 to S-99, the monthly file of the same layout
as at issuance): a row's prefix (S-01), security identifier -- the pool
number (S-02) --, CUSIP (S-03), factor date (S-04, MMCCYY, the month the
factor is in effect from), factor (S-05, rounded to eight places), payment
delay days (S-06), correction indicator (S-07), status (S-08), notification
indicator (S-09: preliminary, final or not applicable), issuer (S-11, FNM or
FRE), issue date (S-12, MMDDCCYY), maturity date (S-13, MMCCYY), issuance
and current investor UPB (S-15, S-16), WA net interest rate (S-17, the pass-
through rate), WA current interest rate (S-19, the WAC), WA current
remaining months to maturity (S-23, the WAM) and WA loan age (S-24, the
WALA). The rest of the row is not read.

**REMIC factor file** (RF-01 to RF-17): the trust (RF-01) and class
(RF-02), CUSIP (RF-03), maturity date (RF-04, MMCCYY), class issuance UPB
(RF-05), the factor (RF-06), class current UPB (RF-07), the period's
interest rate (RF-08), the accretion factor (RF-13) and the scheduled
distribution date (RF-15, MMCCYY). A file's first line naming the columns
("Trust Identifier|...", as Freddie Mac's published sample has it) is a
header, not a row.

Every number is read from its text as a `Decimal`, exactly; an empty or
"N/AP" value is not stated. A row whose factor or month does not read is
returned as not read, with why, never guessed.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

#: What a column says when it does not apply.
NOT_APPLICABLE = frozenset({"", "N/AP", "N/A", "NA"})


@dataclass(frozen=True)
class PoolRow:
    """One security's row of a security-level file."""

    line: int
    prefix: str
    pool: str
    cusip: str
    effective: str
    factor: Decimal
    delay_days: int | None
    corrected: bool
    preliminary: bool
    issuer: str
    issue_date: date | None
    maturity: str
    issuance_upb: Decimal | None
    current_upb: Decimal | None
    net_rate: Decimal | None
    wac: Decimal | None
    wam: int | None
    wala: int | None


@dataclass(frozen=True)
class ClassRow:
    """One class's row of a REMIC factor file."""

    line: int
    trust: str
    class_name: str
    cusip: str
    maturity: str
    issuance_upb: Decimal | None
    factor: Decimal
    interest_rate: Decimal | None
    accretion_factor: Decimal | None
    distribution: str


@dataclass(frozen=True)
class Unread:
    """A row that did not read, and why."""

    line: int
    why: str


def text_of(body: bytes) -> str:
    """A file's text: the first text member of a zip, else the bytes as text."""
    if body[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = [m for m in archive.namelist() if not m.endswith("/")]
            if not members:
                return ""
            return archive.read(members[0]).decode("utf-8", errors="replace")
    return body.decode("utf-8", errors="replace")


def lines(text: str) -> Iterator[tuple[int, list[str]]]:
    """Each row's fields with its line number, from 1; blank lines left out."""
    for number, line in enumerate(io.StringIO(text), start=1):
        stripped = line.rstrip("\r\n")
        if stripped.strip():
            yield number, [field.strip() for field in stripped.split("|")]


def _decimal(text: str) -> Decimal | None:
    if text.upper() in NOT_APPLICABLE:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _int(text: str) -> int | None:
    value = _decimal(text)
    return int(value) if value is not None and value == value.to_integral_value() else None


def month_from(mmccyy: str) -> str:
    """A month written MMCCYY, as YYYYMM; empty where it does not read."""
    if len(mmccyy) != 6 or not mmccyy.isdigit() or not 1 <= int(mmccyy[:2]) <= 12:
        return ""
    return mmccyy[2:] + mmccyy[:2]


def _day(mmddccyy: str) -> date | None:
    if len(mmddccyy) != 8 or not mmddccyy.isdigit():
        return None
    try:
        return date(int(mmddccyy[4:]), int(mmddccyy[:2]), int(mmddccyy[2:4]))
    except ValueError:
        return None


def _field(fields: list[str], index: int) -> str:
    return fields[index] if index < len(fields) else ""


def pool_row(number: int, fields: list[str]) -> PoolRow | Unread:
    """A security-level row, or why it did not read."""
    if len(fields) < 24:
        return Unread(number, f"{len(fields)} columns, not the layout's 99")
    effective = month_from(fields[3])
    factor = _decimal(fields[4])
    if not fields[1]:
        return Unread(number, "no security identifier (S-02)")
    if not effective:
        return Unread(number, f"factor date (S-04) {fields[3]!r} is not MMCCYY")
    if factor is None or factor < 0:
        return Unread(number, f"factor (S-05) {fields[4]!r} is not a number")
    return PoolRow(
        line=number,
        prefix=fields[0],
        pool=fields[1],
        cusip=fields[2],
        effective=effective,
        factor=factor,
        delay_days=_int(fields[5]),
        corrected=fields[6].upper() == "Y",
        preliminary=fields[8].upper() == "P",
        issuer=fields[10].upper(),
        issue_date=_day(fields[11]),
        maturity=month_from(fields[12]),
        issuance_upb=_decimal(fields[14]),
        current_upb=_decimal(fields[15]),
        net_rate=_decimal(fields[16]),
        wac=_decimal(fields[18]),
        wam=_int(fields[22]),
        wala=_int(fields[23]),
    )


def class_row(number: int, fields: list[str]) -> ClassRow | Unread | None:
    """A REMIC factor row, None for the header, or why it did not read."""
    if fields and fields[0].lower() == "trust identifier":
        return None
    if len(fields) < 15:
        return Unread(number, f"{len(fields)} columns, not the layout's 17")
    factor = _decimal(fields[5])
    distribution = month_from(fields[14])
    if not fields[0] or not fields[1]:
        return Unread(number, "no trust or class identifier (RF-01, RF-02)")
    if factor is None or factor < 0:
        return Unread(number, f"factor (RF-06) {fields[5]!r} is not a number")
    if not distribution:
        return Unread(number, f"distribution date (RF-15) {fields[14]!r} is not MMCCYY")
    return ClassRow(
        line=number,
        trust=fields[0],
        class_name=fields[1],
        cusip=fields[2],
        maturity=month_from(fields[3]),
        issuance_upb=_decimal(fields[4]),
        factor=factor,
        interest_rate=_decimal(fields[7]),
        accretion_factor=_decimal(_field(fields, 12)),
        distribution=distribution,
    )


def same_deal(one: str, other: str) -> bool:
    """Whether two writings of a trust or class name one: their letters and
    digits alike, ignoring case, spaces, hyphens and an agency's prefix --
    "FNR 2016-045", "2016-045" and "2016045" are one; "2016-45" another."""

    def plain(text: str) -> str:
        text = text.upper()
        for prefix in ("FNR", "FHR", "FNMA", "FHLMC"):
            if text.startswith(prefix + " "):
                text = text[len(prefix) + 1 :]
        return "".join(c for c in text if c.isalnum())

    return bool(plain(one)) and plain(one) == plain(other)
