"""The plugin's settings, in the data role's order
(spec/plugin-pages-follow-their-role), each the data role's, which reads the
files (the reference role offers what the data role read): no environment, since each GSE
publishes one set of files; the location of the files and, where it asks
for one, its token; then the role's sample data, a developer's setting.

- `files_url`: where the GSEs' files are read from -- the firm's own copy
  of the disclosure files it downloads from Fannie Mae's PoolTalk or SFTP
  site and Freddie Mac's secured data site, under the terms it accepted
  there, served over HTTPS under the agencies' own file names (files.py).
- `files_token`: a bearer token the location asks for, secret, never shown.
- `sample_data`: the files committed with the plugin, in place of the
  location (files.py's `Samples`).

The SDK declares the storage's two settings from the declaration's kind
(declaration.py): `files_window_days` and `files_past_window`, read here
only through `RawStore.tend(settings=...)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import meridian


@meridian.settings
class Declared:
    """The settings as declared: one typed class, the SDK's form."""

    files_url: str = meridian.setting(
        "Files location",
        roles=["data"],
        description=(
            "The HTTPS address of the folder holding Fannie Mae's and Freddie Mac's monthly "
            "disclosure files, under the agencies' own file names (FNM_MF_202611.zip, "
            "fd261105.zip, FNM_REMIC_202611_25.zip, wj261105.zip): the firm's copy of what it "
            "downloads from PoolTalk and Freddie Mac's secured data site under its agreements."
        ),
    )
    files_token: str = meridian.setting(
        "Files location token",
        secret=True,
        roles=["data"],
        description="A bearer token the files location asks for; empty where it asks none.",
    )
    sample_data: bool = meridian.sample_data(
        roles=["data"],
        description=(
            "Read the disclosure files committed with the plugin instead of the files location: "
            "a Fannie Mae pool and a Freddie Mac pool and REMIC class, September and October "
            "2026's factors, October's republished. Development deployments only."
        ),
    )


@dataclass(frozen=True)
class Config:
    files_url: str = ""
    files_token: str = ""
    sample_data: bool = False


def config_from(delivered: Any) -> Config:
    """The configuration a delivery of the settings says."""
    values = getattr(delivered, "values", delivered) or {}
    url = values.get("files_url")
    token = values.get("files_token")
    return Config(
        files_url=url if isinstance(url, str) else "",
        files_token=token if isinstance(token, str) else "",
        sample_data=values.get("sample_data") is True,
    )
