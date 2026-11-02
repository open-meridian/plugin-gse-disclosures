"""The GSEs' aligned disclosures as an Open Meridian plugin
(`plugin-gse-disclosures`, ruling 686): `data`, each held pool's and REMIC
class's factor into the lake (feed.py), and `reference`, the terms the same
files state offered to their records (terms.py) -- the first `reference`
plugins with `plugin-ginnie-mae`.

`meridian.run` registers its two role classes on the sidecar it is launched
beside, with its declaration (declaration.py): it delivers the settings to
`on_settings` before anything is heard, hands the data role what the lake
wants of it, serves the two pages and sets the data role's figures. The
data role's `run` checks the latest two months' files daily (or at once
when the settings change), records what changed for the pools and classes
kept current, reports the feed delay, reads the datasets' licences every
minute and tends storage daily.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import meridian
from meridian.edge import storage_root
from meridian.roles import data

from .agency import Days
from .declaration import CATALOGUE, DECLARATION, PORT
from .feed import Disclosures
from .files import Store, source
from .library import Library
from .page import hold, pages
from .settings import Config, config_from
from .terms import Terms

log = logging.getLogger("gse_disclosures")

CHECK_SECONDS = 86_400
TEND_SECONDS = 86_400
LICENCES_SECONDS = 60


class Running(Disclosures):
    """The data role's class with its lifecycle (open-meridian 0.35)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.config = Config()
        self.settings: Any = None
        self.wake = asyncio.Event()

    async def on_settings(self, delivered: Any) -> None:
        """Each delivery of the settings: the source they name -- kept while
        it is the same one, so what it has read stays read -- and a check at
        once."""
        config = config_from(delivered)
        was = self.config
        moved = config.sample_data != was.sample_data or (
            not config.sample_data
            and (config.files_url, config.files_token) != (was.files_url, was.files_token)
        )
        if moved or self.settings is None:
            self.library.source = source(config.sample_data, config.files_url, config.files_token)
            self.library.months.clear()
        if config.payment_calendar != self.calendar.default:
            self.calendar = Days(self, config.payment_calendar)
        self.config, self.settings = config, delivered
        # The payment calendar asked for at once, so the deployment holds it
        # before a want's dates are rolled by it.
        await self.calendar.open(self.today())
        self.wake.set()

    async def run(self) -> None:
        await asyncio.gather(self._check(), self._tend(), self._licences(), self.latency.run())

    async def _check(self) -> None:
        while True:
            self.wake.clear()
            try:
                await self.check()
            except (OSError, meridian.MeridianError) as failed:
                log.warning("this check stopped: %s", failed)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.wake.wait(), timeout=CHECK_SECONDS)

    async def _tend(self) -> None:
        while True:
            if self.settings is not None:
                try:
                    await self.library.store.raw.tend(self.plugin, settings=self.settings)
                except (OSError, ValueError, meridian.MeridianError) as failed:
                    log.warning("storage not tended this time: %s", failed)
            await asyncio.sleep(TEND_SECONDS)

    async def _licences(self) -> None:
        while True:
            try:
                await self.wants.read_licences()
            except meridian.MeridianError as failed:
                log.warning("the datasets' licences were not read this time: %s", failed)
            await asyncio.sleep(LICENCES_SECONDS)


def figures(feed: Running) -> list[meridian.Figure]:
    source = feed.library.source
    connection: str | meridian.Figure
    if source.mode == "sample":
        connection = "Sample data"
    elif feed.error or source.failed:
        connection = meridian.Figure(
            "", "Not answering", state="error", why=feed.error or source.failed
        )
    elif feed.calendar.error:
        connection = meridian.Figure(
            "", "Answering", state="warn", why=f"dates not set: {feed.calendar.error}"
        )
    elif not feed.config.files_url:
        connection = meridian.Figure(
            "", "No files location", state="warn", why="set Files location in Settings"
        )
    else:
        connection = "Answering"
    last = max(feed.wants.sent_to(d.key).last_ns for d in CATALOGUE)
    return data.figures(
        connection=connection,
        entitled_at_vendor=f"{len(CATALOGUE)} of {len(CATALOGUE)} datasets",
        stream="Does not stream",
        last_recorded=datetime.fromtimestamp(last / 1e9, UTC) if last else "Not yet",
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    root: Path = storage_root(prefix="gse-disclosures-")
    terms = Terms()
    feed = Running(Library(source(False, "", ""), Store(root)), terms=terms)
    hold(feed, terms)
    meridian.run(
        declaration=DECLARATION,
        roles=[feed, terms],
        pages=pages,
        port=PORT,
        on_settings=feed.on_settings,
        figures=lambda: figures(feed),
    )


if __name__ == "__main__":
    main()
