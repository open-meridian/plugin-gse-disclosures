"""The GSEs' files of a month, read and kept, and the rows a want names
found in them.

A month here is the month an agency's factors are in effect from, the month
it publishes them in (days.py); the factor month the lake keys a row by is
the month before. Reading a month asks the source for each file the agency
publishes then (agencies.py), keeps each new content (files.py), and leaves
the rows in the kept bytes: a disclosure file states every pool of the
agency, and the plugin records the factors of the pools and classes the
deployment's records name only (ruling 749), so a row is looked for when a
want names its pool or class, never read out of a whole file into the lake.

A file read again whose content changed -- an agency's correction, a
preliminary factor made final -- is kept again, and the rows found in it
are recorded as their rows' next versions.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from .agencies import Agency
from .files import Kept, Source, Store
from .layouts import ClassRow, PoolRow, Unread, class_row, lines, pool_row, same_deal, text_of

log = logging.getLogger("gse_disclosures")


@dataclass(frozen=True)
class Found:
    """A row found, the file it was read from and that file's kept record."""

    row: PoolRow | ClassRow
    file: str
    kept: Kept
    payment_day: int = 0


@dataclass
class Month:
    """One agency's files of one month, as last read: each file's kept
    content by name, and the class files' payment days."""

    agency: Agency
    effective: str
    pools: dict[str, Kept] = field(default_factory=dict)
    classes: dict[str, tuple[Kept, int]] = field(default_factory=dict)


@dataclass
class Library:
    """The months read, by agency and month."""

    source: Source
    store: Store
    months: dict[tuple[str, str], Month] = field(default_factory=dict)
    #: Rows that did not read, by file, the latest read's.
    unread: dict[str, list[Unread]] = field(default_factory=dict)
    #: The files newly kept by the latest read, by name.
    changed: set[str] = field(default_factory=set)

    async def read(self, agency: Agency, effective: str, again: bool = False) -> Month:
        """An agency's files of a month: read once, or again (`again`) to
        find a later or corrected publication."""
        held = self.months.get((agency.key, effective))
        if held is not None and not again:
            return held
        month = held or Month(agency, effective)
        for name in agency.pool_files(effective):
            kept = await self._fetch(name)
            if kept is not None:
                month.pools[name] = kept
        for file in agency.class_files(effective):
            kept = await self._fetch(file.name)
            if kept is not None:
                month.classes[file.name] = (kept, file.payment_day)
        self.months[(agency.key, effective)] = month
        return month

    async def _fetch(self, name: str) -> Kept | None:
        fetched = await self.source.get(name)
        if fetched is None:
            return None
        kept, new = self.store.keep(fetched)
        if new:
            self.changed.add(name)
            log.info("%s read and kept (%d bytes)", name, len(fetched.body))
        return kept

    def pools(self, month: Month, wanted: Iterable[str]) -> dict[str, Found]:
        """The rows of the pools named, by pool number, as the month's files
        state them."""
        named = {p.upper() for p in wanted}
        found: dict[str, Found] = {}
        for name, kept in month.pools.items():
            for number, fields in self._rows(name, kept):
                if not fields or len(fields) < 2 or fields[1].upper() not in named:
                    continue
                row = pool_row(number, fields)
                if isinstance(row, Unread):
                    self.unread.setdefault(name, []).append(row)
                    continue
                found[row.pool.upper()] = Found(row, name, kept)
        return found

    def classes(
        self, month: Month, wanted: Iterable[tuple[str, str]]
    ) -> dict[tuple[str, str], Found]:
        """The rows of the classes named, by (trust, class) as named, as the
        month's REMIC factor files state them."""
        named = list(wanted)
        found: dict[tuple[str, str], Found] = {}
        for name, (kept, day) in month.classes.items():
            for number, fields in self._rows(name, kept):
                hits = [
                    (trust, klass)
                    for trust, klass in named
                    if len(fields) > 1
                    and same_deal(fields[0], trust)
                    and fields[1].upper() == klass.upper()
                ]
                if not hits:
                    continue
                row = class_row(number, fields)
                if row is None:
                    continue
                if isinstance(row, Unread):
                    self.unread.setdefault(name, []).append(row)
                    continue
                for hit in hits:
                    found[hit] = Found(row, name, kept, day)
        return found

    def _rows(self, name: str, kept: Kept) -> Iterable[tuple[int, list[str]]]:
        try:
            body = kept.body()
        except FileNotFoundError:
            # Moved past its window: read again at the next check.
            self.store.latest.pop(name, None)
            return []
        return lines(text_of(body))
