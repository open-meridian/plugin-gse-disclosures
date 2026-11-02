"""The plugin's reference role class: the terms a GSE's files state of a pool
or a class, offered to the record's template (W3.23; ruling 686, the first
`reference` plugins).

When the data role records a pool's or a class's factor, the row it read
states terms of the security too, and this offers them to the record the
deployment holds, at the record's template and version (`TPL-mbs-pool`,
`TPL-cmo-tranche`): each value at its field's path, with its provenance --
the file it was read from, at the row's line, or the rule it was derived by.
Only the fields the template has are offered (ReadTemplate), each as an
offer: a value is in force once a person accepts it, a value a person set
stands (W3.10), and an offer never leaves the deployment (W1.25). The plugin
never asks for a mint.

A pool (the security-level file): its agency, pool number, program (the
prefix, S-01), pass-through rate (S-17), issue date (S-12), maturity date
(S-13, the first of its month), original face (S-15) and payment delay days
(S-06); and, derived from the delay by the GSEs' convention, its payment day
and record-date rule. A class (the REMIC factor file): its agency, deal and
class, original face (RF-05), maturity date (RF-04, the first of its month)
and payment day (the file's). A class's interest rate is a period's, so it
is never offered as its coupon.

Each record is offered once for each file content it was read from.
"""

from __future__ import annotations

import logging
from typing import Any

import meridian
from meridian import edge
from meridian.roles import reference

from . import agency, days
from .layouts import ClassRow, PoolRow
from .library import Found

log = logging.getLogger("gse_disclosures")

#: Each security's template where its record names none.
POOL_TEMPLATE = "TPL-mbs-pool"
CLASS_TEMPLATE = "TPL-cmo-tranche"


def _maturity(month: str) -> str:
    return f"{month[:4]}-{month[4:]}-01" if len(month) == 6 else ""


def pool_terms(row: PoolRow, agency: str, reported: Any) -> list[meridian.TemplateFieldValue]:
    """A pool's terms as its security-level row states them."""
    values: list[tuple[str, str, Any]] = [
        ("agency", agency, reported("agency")),
        ("pool_number", row.pool, reported("pool_number")),
        ("program", row.prefix, reported("program")),
    ]
    if row.net_rate is not None:
        values.append(("pass_through_rate", str(row.net_rate), reported("pass_through_rate")))
    if row.issue_date is not None:
        values.append(("issue_date", row.issue_date.isoformat(), reported("issue_date")))
    if row.maturity:
        values.append(
            (
                "maturity_date",
                _maturity(row.maturity),
                edge.derived("maturity_date", "the month S-13 states, its first day"),
            )
        )
    if row.issuance_upb is not None:
        values.append(("original_face", str(row.issuance_upb), reported("original_face")))
    if row.delay_days in days.DELAYS:
        _, day = days.DELAYS[row.delay_days]
        values += [
            ("payment_delay_days", str(row.delay_days), reported("payment_delay_days")),
            (
                "payment_day",
                str(day),
                edge.derived("payment_day", f"a {row.delay_days}-day delay pays on the {day}th"),
            ),
            (
                "record_date_rule",
                "RECORD_DATE_RULE_LAST_DAY_OF_PRIOR_MONTH",
                edge.derived("record_date_rule", "the GSEs' pools: the month before payment"),
            ),
        ]
    return [meridian.TemplateFieldValue(path=p, value=v, provenance=w) for p, v, w in values]


def class_terms(
    row: ClassRow, agency: str, payment_day: int, reported: Any
) -> list[meridian.TemplateFieldValue]:
    """A class's terms as its REMIC factor row states them."""
    values: list[tuple[str, str, Any]] = [
        ("agency", agency, reported("agency")),
        ("deal", row.trust, reported("deal")),
        ("class_name", row.class_name, reported("class_name")),
    ]
    if row.issuance_upb is not None:
        values.append(("original_face", str(row.issuance_upb), reported("original_face")))
    if row.maturity:
        values.append(
            (
                "maturity_date",
                _maturity(row.maturity),
                edge.derived("maturity_date", "the month RF-04 states, its first day"),
            )
        )
    if payment_day:
        values.append(
            (
                "payment_day",
                str(payment_day),
                edge.derived("payment_day", "the distribution day of the file it is read from"),
            )
        )
    return [meridian.TemplateFieldValue(path=p, value=v, provenance=w) for p, v, w in values]


class Terms(reference.Role):
    """The reference role's class (open-meridian 0.35): what a row states,
    offered through `agency.Offers`."""

    def __init__(self) -> None:
        self.offers = agency.Offers()

    async def offer(self, security: Any, found: Found, as_of_ns: int = 0) -> bool:
        """Offer what a row states to the security's record, once for each
        file content; whether an offer was made. A pool's number is
        confirmed to resolve to the record first."""
        row = found.row
        ref = self.plugin.raw_record(f"{found.kept.key}#{row.line}")

        def reported(path: str) -> Any:
            return edge.reported(path, ref)

        gse = security.agency.mortgage_agency
        if isinstance(row, PoolRow):
            return await self.offers.offer(
                self,
                security.subject,
                found.kept.key,
                template=POOL_TEMPLATE,
                values=lambda: pool_terms(row, gse, reported),
                pool=(security.pool, security.agency.code),
                as_of_ns=as_of_ns,
            )
        assert isinstance(row, ClassRow)
        return await self.offers.offer(
            self,
            security.subject,
            found.kept.key,
            template=CLASS_TEMPLATE,
            values=lambda: class_terms(row, gse, found.payment_day, reported),
            as_of_ns=as_of_ns,
        )
