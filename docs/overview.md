# Overview

Fannie Mae and Freddie Mac publish each month, in one aligned format, the
factor of every pool and REMIC class they guarantee: the fraction of its
original face still outstanding. This plugin reads those monthly
disclosure files and puts the factors of the pools and classes your
deployment holds into its lake, one dataset per GSE, and offers the terms
the same files state to each security's record.

## What it brings in

- **Factors** (`fannie_mae`, `freddie_mac`): for each agency pool and REMIC
  class the deployment's records name, its factor for each month as the
  agency publishes it, exactly, with the month it reflects, its record date
  and payment date; a pool's weighted average coupon, remaining maturity
  and loan age where the file states them; a floating class's coupon for the
  period. A year of history when a pool is first asked for, then each new
  month's factor as it is published, and a corrected factor as the row's
  next version.
- **Terms**, offered to the record: a pool's agency, number, program,
  pass-through rate, issue and maturity dates, original face and payment
  delay; a class's agency, deal, class, original face and maturity. An offer
  is never in force until a person accepts it, and never replaces a value a
  person set.

## What it does not do

- It never records a pool or class nobody holds: it reads the files for the
  records your deployment names, never a whole file into the lake.
- It never creates an instrument record; a pool or class is brought into the
  deployment by the source that holds it.
- It records no prices, trades or quotes, and computes no paydown: the
  deployment's servicing work does that from the factors.
- It does not reach the agencies' sites itself: it reads the files from the
  location you name (see Setup).
- Ginnie Mae's pools and classes are another plugin's, `ginnie-mae`.
