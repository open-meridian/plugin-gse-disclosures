"""The two GSEs this plugin reads, one dataset each (ruling 686: one plugin
for their aligned UMBS format, a dataset per GSE), and the files each
publishes a month.

Each publishes, on the fourth business day of a month at 4:30 p.m. Eastern,
the factors in effect from that month (Fannie Mae's Single-Family Disclosure
Guide, "Publication times"; Freddie Mac's disclosure file directory):

- **Fannie Mae**: its MBS Monthly Security Factor File, `FNM_MF_YYYYMM`,
  every UMBS, MBS, Mega and Super; and its REMIC Factor File,
  `FNM_REMIC_YYYYMM_DD`, one for each distribution day its deals pay on
  (the 25th, and the 2nd, 4th, 17th, 18th and 20th for its non-standard
  deals), the day the file's name states;
- **Freddie Mac**: its Monthly Security Core File, `fdYYMMDD`, named for the
  day it is published; and its REMIC tranche factor files, 55-day
  (`wjYYMM05`, paying on the 25th), Gold (`GTYYMM05`) and 75-day
  (`FTYYMM05`), each paying on the 15th.

A pool is named by its agency's pool number under the open scheme
`agency_pool` (ruling 677), the identifier's source the agency's code as
the platform's records state it (`FNMA`, `FHLMC`).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import days
from .agency import Days


@dataclass(frozen=True)
class ClassFile:
    """A REMIC factor file of a month, and the day of the month its classes
    pay on."""

    name: str
    payment_day: int


@dataclass(frozen=True)
class Agency:
    """One GSE: its dataset's key, its name, its code as a pool's identifier
    source, the issuer code its files state (S-11) and its `MortgageAgency`."""

    key: str
    name: str
    code: str
    issuer: str
    mortgage_agency: str

    async def pool_files(self, effective: str, calendar: Days) -> list[str]:
        """The security-level files stating the factors in effect from a month:
        Freddie Mac's named for its publication day, the fourth business day
        by the calendar -- none where the calendar does not answer."""
        if self.key == FANNIE_MAE.key:
            return [f"FNM_MF_{effective}"]
        year, month = days.month_of(effective)
        on = await calendar.nth_business_day(year, month, days.PUBLICATION_DAY)
        return [f"fd{on:%y%m%d}"] if on is not None else []

    def class_files(self, effective: str) -> list[ClassFile]:
        """The REMIC factor files stating the class factors of a month's
        distributions."""
        if self.key == FANNIE_MAE.key:
            return [
                ClassFile(f"FNM_REMIC_{effective}_{day:02d}", day) for day in (25, 2, 4, 17, 18, 20)
            ]
        yymm = effective[2:]
        return [
            ClassFile(f"wj{yymm}05", 25),
            ClassFile(f"GT{yymm}05", 15),
            ClassFile(f"FT{yymm}05", 15),
        ]


FANNIE_MAE = Agency("fannie_mae", "Fannie Mae", "FNMA", "FNM", "MORTGAGE_AGENCY_FNMA")
FREDDIE_MAC = Agency("freddie_mac", "Freddie Mac", "FHLMC", "FRE", "MORTGAGE_AGENCY_FHLMC")
AGENCIES = (FANNIE_MAE, FREDDIE_MAC)
BY_KEY = {agency.key: agency for agency in AGENCIES}
BY_ENUM = {agency.mortgage_agency: agency for agency in AGENCIES}
#: Each agency by the codes a pool's identifier source may give it.
BY_CODE = {
    "FNMA": FANNIE_MAE,
    "FNM": FANNIE_MAE,
    "FANNIE MAE": FANNIE_MAE,
    "FHLMC": FREDDIE_MAC,
    "FRE": FREDDIE_MAC,
    "FREDDIE MAC": FREDDIE_MAC,
}
