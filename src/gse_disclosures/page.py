"""The plugin's pages, under Manage alone: the data role's common pages
(spec/plugin-pages-follow-their-role), Connection and Datasets, each also a
read tool for agents on the deployment's MCP (`read_connection`,
`read_datasets`). Each record is the role's (`meridian.roles.data`); each
template the role's, the GSEs' nuance at its blocks only.

- **Connection** (`/`): "Key" -- Live or Sample data, the files location's
  token set or not --, "Limits and use" -- the requests made, the last
  check and its error --, and "Stream": it does not stream.
- **Datasets** (`/datasets`): "Served", a row per GSE; "Wants", the pools
  and classes asked of it and those kept current; and "Subjects".

Neither shows a factor: factors are the reading roles' to show.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import meridian
from meridian.roles import data

TITLE = "GSE disclosures"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates")

#: The running plugin's two role classes, which __main__.py gives the pages.
running: dict[str, Any] = {}


def hold(feed: Any, terms: Any) -> None:
    running.update(feed=feed, terms=terms)


def connection_read(feed: Any) -> data.ConnectionRead:
    """Connection's record: the role's common fields."""
    if feed is None:
        return data.ConnectionRead(mode="Live", sessions=None)
    source = feed.library.source
    sample = source.mode == "sample"
    token = bool(getattr(source, "token", ""))
    return data.ConnectionRead(
        mode="Sample data" if sample else "Live",
        credentials=[] if sample else [data.Credential("Files location token", token)],
        entitled_at_vendor="2 of 2 datasets",
        limit="2 requests a second, at most",
        calls=source.calls,
        last_call_at=feed.last_check.isoformat(timespec="seconds") if feed.last_check else "",
        last_error=feed.error or source.failed or feed.calendar.error,
        sessions=None,
    )


def datasets_read(feed: Any) -> data.DatasetsRead:
    """Datasets' record: the role's common fields."""
    from .declaration import CATALOGUE

    if feed is None:
        return data.DatasetsRead()
    instance = feed.plugin.identity.instance_id
    return data.DatasetsRead(
        served=data.served(CATALOGUE, instance, feed.wants, "2 of 2 datasets"),
        wants=list(data.want_rows(feed.wants)),
    )


@pages.page(
    "/",
    "Connection",
    levels="admin",
    roles=["data"],
    answers=data.ConnectionRead,
    name="read_connection",
)
async def connection(request: meridian.Request) -> meridian.Response:
    """Whether the files location answers, and what the plugin asked of it."""
    return pages.answer("connection.html", connection_read(running.get("feed")))


@pages.page(
    "/datasets",
    "Datasets",
    levels="admin",
    roles=["data"],
    answers=data.DatasetsRead,
    name="read_datasets",
)
async def datasets(request: meridian.Request) -> meridian.Response:
    """Each GSE's dataset, whether it is licensed, and the wants kept current."""
    return pages.answer("datasets.html", datasets_read(running.get("feed")))
