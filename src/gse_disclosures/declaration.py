"""What this version declares beside its roles (W8.1, W4.1): from contract
v25 the whole of what it says about itself.

**The catalogue: a dataset per GSE** (ruling 686), `fannie_mae` and
`freddie_mac`, each the factors of its pools and REMIC classes
(`meridian.v1.Factor`, contract v29, with the optional `wac`, `wam`, `wala`
and `coupon_rate` it fills, ruling 995):

- `vendor` the GSE; no aggregator, since the plugin reads the agency's own
  files;
- `modes` `pull` (a pool's or a class's factors when the lake wants them)
  and `push` (each new month's and each republication, for the pools and
  classes kept current);
- `cadence` a day, in seconds: the files are checked daily, and each GSE
  publishes its month's on the fourth business day;
- `history` 396 days: a want is answered with thirteen months of factors;
- its day New York's, ending at midnight; no venue, no calendar.

No licence (rulings 1030 to 1032): the GSEs' terms are the deployment's,
accepted with its PoolTalk and secured-site registrations; each dataset
describes its agency's in words (`terms_and_pricing`, contract 30), as
docs/terms.md does. A gap is recovered by `backfill` (`gap_recovery`): the
files hold thirteen months, so the lake asks again through its want.

**Storage:** the files as read (files.py), archivable, ten years by default.

Built from the plugin's code and used twice: `__main__` registers with it,
and `meridian plugin upload` reads the same one from the built image. The
port is fixed here, never read from the environment.
"""

from __future__ import annotations

import meridian
from meridian.declaration import Declaration, RecordKind, Storage

from .agencies import AGENCIES, Agency
from .files import FILES
from .page import TITLE, pages
from .settings import Declared

#: The port its pages are served on, on loopback, where its sidecar forwards.
PORT = 8000
#: A day, in seconds: the files are checked daily.
CADENCE = 86_400
#: Thirteen months of factors, in days.
HISTORY_DAYS = 396
#: The files' window in storage by default, and at most.
WINDOW_DAYS = 3650
MOST_WINDOW_DAYS = 36500

#: Each agency's terms in plain words (contract 30, ruling 1032).
TERMS = {
    "Fannie Mae": (
        "Fannie Mae's own disclosures: its pools' and REMIC classes' monthly factor files, "
        "made available to users who register and accept its terms, through PoolTalk and its "
        "SFTP site. Fannie Mae has said that commercial redistribution of its disclosure data "
        "carries a fee. Fannie Mae's current terms on its site govern."
    ),
    "Freddie Mac": (
        "Freddie Mac's own disclosures: its pools' and REMIC classes' monthly factor files, "
        "made available to users who register and accept its terms, through its secured data "
        "site. Freddie Mac's current terms on its site govern."
    ),
}

DATA_TYPES = [
    "meridian.v1.Factor",
    "meridian.v1.Factor.wac",
    "meridian.v1.Factor.wam",
    "meridian.v1.Factor.wala",
    "meridian.v1.Factor.coupon_rate",
]


def declared(agency: Agency) -> meridian.DatasetDeclaration:
    return meridian.DatasetDeclaration(
        key=agency.key,
        vendor=agency.name,
        data_types=DATA_TYPES,
        modes=["pull", "push"],
        cadence=CADENCE,
        history=HISTORY_DAYS,
        day_time_zone="America/New_York",
        terms_and_pricing=TERMS[agency.name],
        gap_recovery="backfill",
    )


CATALOGUE = [declared(agency) for agency in AGENCIES]
FILES_KIND = RecordKind(FILES, "Disclosure files", window_days=WINDOW_DAYS)

DECLARATION = Declaration(
    settings=Declared,
    storage=Storage(retention_days=MOST_WINDOW_DAYS, kinds=[FILES_KIND]),
    catalogue=CATALOGUE,
    interface=meridian.Interface(port=PORT, title=TITLE, pages=pages),
    documentation="docs",
)
