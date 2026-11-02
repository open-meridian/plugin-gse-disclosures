# Changelog

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
