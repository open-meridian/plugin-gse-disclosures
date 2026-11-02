"""Where the GSEs' files are read from, and how what was read is kept.

**The location.** Fannie Mae publishes its disclosure files to registered
users of PoolTalk and its SFTP site, and Freddie Mac to users of its secured
data site, each under the terms the user accepts there; neither documents
an API for reading them. So the plugin reads each file, exactly as the
agency published it -- zipped or not, under the agency's own file name --
from the location a deployment admin names (`files_url`): the firm's own
copy of the files it downloads under its agreements, served over HTTPS, a
bearer token beside it where the location asks for one (`files_token`). It
asks for `<name>.zip`, then `<name>.txt`, then `<name>`; a file the location
does not hold is not published yet, never an error. One request at a time,
at most two a second.

With sample data (a developer's setting) it reads the files committed with
it instead (`samples/`), which name a pool and a class of each GSE the
plugin's tests and e2e use; a sample marked `republished` is served in its
second form from the second read of it on, as an agency's corrected file
would be.

**What was read is kept** (decisions/028): each file, the first time its
bytes are seen, in the plugin's storage, its bytes beside a record of where
and when it was read (`Kept`); each row recorded names it by that record's
key and the row's line (`<key>#<line>`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

from meridian.edge import RawStore

log = logging.getLogger("gse_disclosures")

#: The kind of raw record: each file as read.
FILES = "files"
#: The suffixes asked for, in order.
SUFFIXES = (".zip", ".txt", "")
#: The fewest seconds between two requests.
PACE_SECONDS = 0.5
TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class Fetched:
    """One file as read: its name, where from, when, and its bytes."""

    name: str
    url: str
    body: bytes
    received: datetime


class Source(Protocol):
    """Where the files are read from."""

    mode: str
    calls: int
    failed: str

    async def get(self, name: str) -> Fetched | None: ...


@dataclass
class Location:
    """The deployment's location of the GSEs' files, over HTTPS."""

    base: str
    token: str = ""
    mode: str = "live"
    calls: int = 0
    failed: str = ""
    last_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get(self, name: str) -> Fetched | None:
        async with self.lock:
            for suffix in SUFFIXES:
                url = f"{self.base.rstrip('/')}/{name}{suffix}"
                wait = PACE_SECONDS - (time.monotonic() - self.last_at)
                if wait > 0:
                    await asyncio.sleep(wait)
                self.last_at = time.monotonic()
                self.calls += 1
                try:
                    body = await asyncio.to_thread(self._read, url)
                except urllib.error.HTTPError as refused:
                    if refused.code == 404:
                        continue
                    self.failed = f"{url}: HTTP {refused.code}"
                    raise
                except (urllib.error.URLError, OSError) as failed:
                    self.failed = f"{url}: {failed}"
                    raise
                self.failed = ""
                return Fetched(name, url, body, datetime.now(UTC))
            self.failed = ""
            return None

    def _read(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "open-meridian"})
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:  # noqa: S310
            body: bytes = answer.read()
        return body


#: The day the samples are read as of: after October 2026's factors and
#: November's publication of them.
SAMPLES_AS_OF = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)


@dataclass
class Samples:
    """The files committed with the plugin (`samples/index.json`), read as of
    `SAMPLES_AS_OF` whatever the day."""

    mode: str = "sample"
    calls: int = 0
    failed: str = ""
    reads: dict[str, int] = field(default_factory=dict)
    now: Any = None

    def today(self) -> datetime:
        return SAMPLES_AS_OF

    def _index(self) -> dict[str, Any]:
        index: dict[str, Any] = json.loads(
            resources.files(__package__).joinpath("samples/index.json").read_text("utf-8")
        )
        return index

    async def get(self, name: str) -> Fetched | None:
        self.calls += 1
        entry = self._index()["files"].get(name)
        if entry is None:
            return None
        self.reads[name] = self.reads.get(name, 0) + 1
        file = entry["file"]
        if entry.get("republished") and self.reads[name] > 1:
            file = entry["republished"]
        body = resources.files(__package__).joinpath(f"samples/{file}").read_bytes()
        received = self.now() if self.now is not None else datetime.now(UTC)
        return Fetched(name, f"samples/{file}", body, received)


@dataclass
class Unset:
    """No files location set yet: nothing is read, and Connection says so."""

    mode: str = "live"
    calls: int = 0
    failed: str = ""
    token: str = ""

    async def get(self, name: str) -> Fetched | None:
        return None


def source(sample_data: bool, base: str, token: str) -> Source:
    """The source the settings say: the samples, the location, or none yet."""
    if sample_data:
        return Samples()
    if base:
        return Location(base, token)
    return Unset()


@dataclass(frozen=True)
class Kept:
    """A file kept: the key of its record, its digest, and where its bytes
    are, read again only when a row is looked for."""

    key: str
    digest: str
    path: Path

    def body(self) -> bytes:
        return self.path.read_bytes()


class Store:
    """The files read, kept in the plugin's storage (or a directory of the
    store's own where none is granted), each new content once."""

    def __init__(self, root: Path) -> None:
        self.raw = RawStore(root, kind=FILES)
        self.root = root
        #: The latest content kept of each file, by name.
        self.latest: dict[str, Kept] = {}

    def kept(self, name: str, digest: str) -> Kept | None:
        """The record of a file's content already in storage -- kept by an
        earlier process, before a restart -- or None. A row read again from
        it names the same raw record, so the lake answers it unchanged rather
        than as its next version."""
        base = self.root / FILES
        if not base.is_dir():
            return None
        for record in sorted(base.glob("*/file/*.json")):
            try:
                held = json.loads(record.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if held.get("name") == name and held.get("sha256") == digest:
                path = record.with_suffix(".bin")
                if path.is_file():
                    return Kept(str(record.relative_to(self.root)), digest, path)
        return None

    def keep(self, fetched: Fetched) -> tuple[Kept, bool]:
        """Keep a file read, unless its content is kept already; what is
        kept, and whether it is new."""
        digest = hashlib.sha256(fetched.body).hexdigest()
        held = self.latest.get(fetched.name)
        if held is not None and held.digest == digest:
            return held, False
        found = self.kept(fetched.name, digest)
        if found is not None:
            self.latest[fetched.name] = found
            return found, False
        received_ns = int(fetched.received.timestamp() * 1_000_000) * 1000
        key = self.raw.keep(
            "file",
            fetched.name,
            {
                "received_at_ns": received_ns,
                "name": fetched.name,
                "url": fetched.url,
                "sha256": digest,
                "bytes": len(fetched.body),
            },
        )
        path = (self.root / key).with_suffix(".bin")
        path.write_bytes(fetched.body)
        kept = Kept(key, digest, path)
        self.latest[fetched.name] = kept
        return kept, True
