"""`make e2e`: the plugin on the plugin harness of the runtime it pins
(contract v29), beside `reader`, a reporting plugin (e2e/reader.py) entitled
to its Fannie Mae dataset, and the harness's admin. Run from the repository's
root by the Makefile, which builds the image and writes the harness's
plugins first; standard library only. The harness's stand-in for the
platform holds a Fannie Mae UMBS pool, MA5123, matched by its pool number
under `agency_pool` (core's e2e-lake step 17 reads the same pool).

1. Started with no files location: Connection says so, and nothing is
   recorded.
2. Sample data on (a developer's setting, accepted on the harness).
3. The reader resolves the pool by its number to the platform's `INS-`
   record, is entitled to `gse-disclosures:fannie_mae`, and asks for its
   factors by payment date: the lake asks the plugin, standing, and the
   plugin records September's and October's factors from the samples, as
   the contract's fixtures key them (`FNMA:MA5123:202610`, factor month
   202610, record date 2026-10-31, paid 2026-11-25, published 2026-11-05)
   with the pool's WAC, WAM and WALA.
4. Republished: a setting changed wakes the plugin's check, which
   reads the samples' October file in its corrected form -- 0.83102211 --
   recorded as the row's version 2; read by payment date the pool's October
   factor is the republication.
5. Caught up: a read after the sequence the reader last saw answers the
   republication alone.
6. Its terms offered to the pool's record (OfferTemplateFields, accepted),
   as the plugin's log says, and nothing refused.
7. Its two pages answer, through the deployment's MCP as tools too.
"""

import json
import os
import subprocess
import sys
import time

PROJECT = "gse-disclosures-e2e"
LOG = ".e2e/runner.log"
COMPONENTS = ".e2e/components.log"
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", ".e2e/harness/compose.yaml",
           "-f", ".e2e/harness/plugins.yaml", "-f", "e2e/plugin.yaml"]
INSTANCE = "gse-disclosures"
DATASET = f"{INSTANCE}:fannie_mae"


class Failed(Exception):
    pass


def log(text):
    with open(LOG, "a", encoding="utf-8") as kept:
        kept.write(text + "\n")


def compose(*args, check=True, timeout=600):
    done = subprocess.run(COMPOSE + list(args), capture_output=True, text=True, timeout=timeout)
    log(f"$ compose {' '.join(args)[:300]}\n{done.stdout[-4000:]}{done.stderr[-2000:]}")
    if check and done.returncode != 0:
        raise Failed(f"compose {' '.join(args)[:200]}: {(done.stdout + done.stderr).strip()[-600:]}")
    return done


def runner(*args, check=True):
    done = compose("run", "--rm", "-T", "runner", *args, check=check)
    return done.stdout if check else done


def must(condition, why):
    if not condition:
        raise Failed(why)


def until(seconds, attempt, what):
    deadline = time.monotonic() + seconds
    last = None
    while True:
        try:
            answer = attempt()
        except Failed as failed:
            answer, last = None, failed
        if answer:
            return answer
        if time.monotonic() > deadline:
            raise Failed(f"{what}, in {seconds} seconds" + (f": {last}" if last else ""))
        time.sleep(2)


def page(instance, level, path):
    said = runner("page", "--instance", instance, "--level", level, path)
    status, _, body = said.partition("\n")
    must(status.strip() == "200", f"{instance} {path} answered {said[-600:]}")
    return body


def read(path):
    return json.loads(page("reader", "read", path))


def call(tool, arguments=None):
    done = runner("mcp", "call", tool, json.dumps(arguments or {}), check=False)
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        raise Failed(f"{tool}: no answer: {(done.stdout + done.stderr)[-400:]}")
    must(answer.get("outcome") in ("read", "unchanged"), f"{tool} answered {done.stdout[-700:]}")
    return answer["data"]


def months(said):
    return sorted((f["month"], f["factor"], f["version"]) for f in said["factors"])


def run():
    started = time.time()
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    compose("up", "-d")
    runner("ready")
    runner("ready", "--instance", "reader")

    # 1. No files location yet.
    runner("page", "--level", "admin", "/", "--until", "Live", "--seconds", "90")
    must("row|" not in compose("run", "--rm", "-T", "store", "lake").stdout,
         "step 1, nothing recorded with no files location")

    # 2. Sample data.
    runner("settings", "sample_data=true")
    runner("page", "--level", "admin", "/", "--until", "Sample data", "--seconds", "90")

    # 3. The pool resolved, its factors asked for and recorded.
    runner("grant", "--instance", "reader", "--level", "read")
    pool = until(60, lambda: (lambda r: r["instrument_id"] if r["found"] else None)(
        read("/resolve?scheme=agency_pool&value=MA5123&source=FNMA")),
        "step 3, the reader did not resolve the pool MA5123")
    must(pool.startswith("INS-"), f"step 3, the pool is the platform's record: {pool}")
    runner("licence", DATASET, "kept=true", "retention_days=0", "derived_use=true", "display=true",
           "personal_use=false", "note=Fannie Mae's disclosures, under the firm's PoolTalk terms.")
    runner("entitle", "--instance", "reader", DATASET, "note=The e2e's reader reads factors.")
    asked = f"/factors?subject={pool}&from=2025-11-01&to=2026-11-30"
    year = until(120, lambda: (lambda r: r if len(r["factors"]) == 2 else None)(read(asked)),
                 "step 3, the pool's two factors were not read")
    must(months(year) == [("202609", "0.84017733", 1), ("202610", "0.83102210", 1)],
         f"step 3, September's and October's factors as published: {year}")
    by_month = {f["month"]: f for f in year["factors"]}
    october = by_month["202610"]
    must(october["row_key"] == "FNMA:MA5123:202610" and october["dataset"] == DATASET
         and october["subject"] == pool and october["record_date"] == "2026-10-31"
         and october["payment_date"] == "2026-11-25" and october["business_date"] == "2026-11-05"
         and (october["wac"], october["wam"], october["wala"]) == ("6.512", 331, 27)
         and october["published"] and october["raw"].endswith("#1"),
         f"step 3, October's row as the fixtures key it: {october}")
    must(by_month["202609"]["payment_date"] == "2026-10-26",
         f"step 3, September's paid the next business day after Sunday the 25th: {year}")
    seen = year["watermark"].get(DATASET, 0)
    must(seen >= 2, f"step 3, the reader's watermark: {year['watermark']}")

    # 4. Republished: the check woken reads the corrected October file.
    runner("settings", "sample_data=true", "files_url=https://files.invalid/gse-disclosures")
    again = until(120, lambda: (lambda r: r if months(r)[-1:] == [("202610", "0.83102211", 2)]
                                else None)(read(asked)),
                  "step 4, October's republication was not read as version 2")
    must(months(again) == [("202609", "0.84017733", 1), ("202610", "0.83102211", 2)],
         f"step 4, by payment date the republication: {again}")

    # 5. Caught up after the sequence last seen.
    caught = read(f"/factors?subject={pool}&after={seen}")
    must([(f["month"], f["version"]) for f in caught["factors"]] == [("202610", 2)],
         f"step 5, the republication caught up after {seen}: {caught}")

    # 6. Terms offered, nothing refused.
    logs = compose("logs", "--no-color", INSTANCE).stdout
    must(f"terms of {pool} offered to TPL-mbs-pool 1" in logs and "not offered" not in logs,
         f"step 6, the pool's terms offered: {logs[-1500:]}")

    # 7. The pages, and their tools.
    runner("grant", "--level", "admin", "--role", "data")
    runner("mcp", "connect", "--covers", "deployment_admin", "--covers", f"{INSTANCE}:data:admin")
    tools = runner("mcp", "list").split()
    read_connection = next((t for t in tools if t.endswith("read_connection")), "")
    read_datasets = next((t for t in tools if t.endswith("read_datasets")), "")
    must(read_connection and read_datasets, f"step 7, the plugin's two tools are listed: {tools}")
    connection = call(read_connection)
    must(connection["mode"] == "Sample data", f"step 7, read_connection: {connection}")
    datasets = call(read_datasets)
    served = {s["dataset"]: s for s in datasets["served"]}
    must(sorted(served) == [DATASET, f"{INSTANCE}:freddie_mac"]
         and served[DATASET]["recorded"] >= 2 and served[DATASET]["licensed"],
         f"step 7, read_datasets: {datasets}")
    must(DATASET in page(INSTANCE, "admin", "/datasets"), "step 7, Datasets shows the dataset")

    print(f"e2e OK in {int(time.time() - started)}s on the plugin harness: nothing recorded with no "
          f"files location; on sample data the harness platform's pool MA5123 ({pool}) resolved, "
          f"its factors recorded when the reader asked -- September's 0.84017733 and October's "
          f"0.83102210 as the fixtures key them, paid 2026-10-26 and 2026-11-25 -- October "
          f"republished as version 2, read by payment date and caught up after the watermark; its "
          f"terms offered to its record; read_connection and read_datasets answering")


def main():
    os.makedirs(".e2e", exist_ok=True)
    open(LOG, "w").close()
    try:
        run()
    except (Failed, subprocess.TimeoutExpired, KeyError, ValueError, IndexError, TypeError) as failed:
        with open(COMPONENTS, "a", encoding="utf-8") as kept:
            kept.write(compose("logs", "--no-color", check=False).stdout)
            kept.write(compose("run", "--rm", "-T", "store", "lake", check=False).stdout)
        compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
        print(f"e2e FAILED: {failed}; the runner's log is in {LOG}, the components' in {COMPONENTS}",
              file=sys.stderr)
        return 1
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
