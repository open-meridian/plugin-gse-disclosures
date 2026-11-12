# Changelog

## 0.2.0

On open-meridian 0.36.0, contract 30, on core aae501d's harness (chart
0.1.538); `meridian` 0.1.60 in the check. What the plugin records is
unchanged.

- **Each agency's terms in words** (ruling 1032): `fannie_mae` and
  `freddie_mac` each describe the agency's disclosures and how they are
  reached (PoolTalk and SFTP; the secured data site), Fannie Mae's fee for
  commercial redistribution among them, shown on Data sources and in the
  Datasets page's row details. The plugin still declares no licence.
- **A gap recovered by backfill** (`gap_recovery`): the files hold thirteen
  months, read again on a want. No `sessions_calendar_id`: factors are
  published monthly, in no session.
- **Row keys checked against the lake's rule 5** (ruled 2026-11-12): a
  factor is keyed by the agency, the pool or the REMIC trust and class, and
  its month (`FNMA:<trust>:<class>:<YYYYMM>`), its valid time the month's; a
  republication restates the same key over the same month and the same
  record. The key names the pool or class, not its record, so one resolved
  again to another record would restate under another first subject:
  listed for step 3d, unchanged.
- `meridian plugin migrate --to 0.36.0` moved the pins (the base by
  digest, `meridian` 0.1.60); the tests' pin and absent-licence checks read
  0.36.0 and the words.
- Core's runtime and harness images at `aae501d`, by digest.

## 0.1.0

The first version (ruling 686, the plan's Q13 and G'), on open-meridian
0.35.3, contract v29.

- **`data`**: a dataset per GSE, `fannie_mae` and `freddie_mac`, of
  `Factor` rows (with `wac`, `wam`, `wala` and `coupon_rate`, ruling 995),
  pulled when the lake wants a held pool's or class's factors and pushed as
  each month's are published or republished. Read from Fannie Mae's monthly
  security factor file and REMIC factor files and Freddie Mac's monthly
  security core file and REMIC tranche factor files, in the GSEs' aligned
  layouts; a pool found by its agency and pool number, a class by its deal
  and class; a pool number meeting two records reported ambiguous.
- **`reference`**: the terms the same rows state offered to the pool's or
  class's record at its template (`TPL-mbs-pool`, `TPL-cmo-tranche`), each
  with its provenance.
- Factor months and payment dates as the contract's fixtures key them: the
  agencies' factor date less a month, the record date its last day, the
  payment date by the security's delay, rolled to the next business day by
  the deployment's calendar -- the record's payment calendar, else the
  `payment_calendar` setting, by default the platform's US dollar calendar
  (the Federal Reserve Banks', `CAL-01M4VF0F3HJ73RFTB0XWVK1B73`) through
  the SDK's `MarketDays` -- and left unset where the calendar does not
  answer or does not cover the day.
- `agency.py`: the logic this plugin and `plugin-ginnie-mae` hold the same
  (business days on the calendar, a pool's number confirmed, a factor want
  answered, terms offered), one module, proposed for an SDK helper.
- The files read from a location the deployment admin names, with sample
  data for development; the data role's Connection and Datasets pages.
