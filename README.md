# plugin-gse-disclosures

Fannie Mae's and Freddie Mac's monthly disclosures for
[Open Meridian](https://open-meridian.dev), as a `data` and `reference`
plugin: the factor of each agency pool and REMIC class a deployment holds,
read from the GSEs' aligned disclosure files into its lake, and the terms the
same files state offered to each security's record.

| Dataset | What it holds |
|---|---|
| `fannie_mae` | Fannie Mae's pool (UMBS, MBS, Mega, Super) and REMIC class factors |
| `freddie_mac` | Freddie Mac's pool and REMIC class factors |

Each row is a `Factor` (contract v29) under the pool's or class's record,
keyed by the agency, the pool (or deal and class) and the factor month --
`FNMA:MA5123:202610` -- the factor exactly as published, its factor month
(the month whose payments it reflects, the month before the agencies' factor
date), record date and payment date -- rolled to a business day by the
deployment's calendar, the record's payment calendar or else the platform's
US dollar calendar, and unset where it does not answer --; a pool's WAC, WAM
and WALA; a floating class's period coupon. A corrected file's factor is the row's next version.
Factors are recorded only for the records the deployment names (ruling
749), when a reader asks for them, and kept current daily.

## Using it

The GSEs publish their files to registered users (Fannie Mae's PoolTalk and
SFTP site, Freddie Mac's secured data site); neither offers an API. The
plugin reads the files, unchanged and under the agencies' own names, from a
location the deployment admin names in its settings (**Files location**,
HTTPS, with an optional token). See [docs/setup.md](docs/setup.md).

    meridian plugin upload
    meridian plugin launch gse-disclosures 0.1.0 --instance gse-disclosures

Then license `gse-disclosures:fannie_mae` and `:freddie_mac` on the
dashboard's **Data sources** page and entitle the plugins that read factors.
Its pages are under **Manage**: Connection and Datasets, each also a read
tool for agents (`read_connection`, `read_datasets`).

## Developing it

    make ci-remote                    # lint and tests, in containers
    make check                        # meridian plugin check --verified --run-tests
    make e2e                          # the plugin on the harness of the runtime it pins
    make preview SHOTS=/tmp/shots     # the pages in a browser, at 375, 582 and 1280 px

The tests run on disclosure files in the GSEs' published layouts, committed
under `src/gse_disclosures/samples/` and `tests/responses/` (Freddie Mac's
published REMIC factor sample); nothing in CI reaches an agency. Version
0.1.0 is built on `open-meridian==0.35.3`, contract v29.

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). This project is not
affiliated with or endorsed by Fannie Mae or Freddie Mac.
