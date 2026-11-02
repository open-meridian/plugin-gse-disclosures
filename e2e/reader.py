"""A reading plugin for the e2e, on the Python SDK: the deployment's view of
the factors this plugin recorded, as a `reporting` plugin entitled to its
datasets reads them (W10.6). Not the plugin, and never shipped: the e2e runs
it from this directory in the plugin's own image, which carries the SDK.

It answers its page as JSON, so the harness's runner can read it
(`page --instance reader --level read PATH`):

  /resolve?scheme=S&value=V&source=O
      the record an identifier names (ResolveIdentifier);
  /factors?subject=ID[&from=D][&to=D][&after=N]
      a pool's factors by payment date, or caught up after a sequence of the
      Fannie Mae dataset (ListFactors): each row's key, month, factor as
      text, version, record and payment dates, business date, WAC, WAM,
      WALA and published time; what the lake left unanswered, with why; and
      the watermark's sequences.

Standard library and the SDK only; every value stays text, never a float.
"""

import asyncio
import http.server
import json
import threading
import urllib.parse

import meridian
from meridian import Interface, Page
from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import reporting

PORT = 8088
LOOP = asyncio.new_event_loop()
DATASET = "gse-disclosures:fannie_mae"


def text(row, name):
    return str(as_decimal(getattr(row, name))) if row.HasField(name) else ""


def factor_json(row):
    meta = row.meta
    return {
        "row_key": meta.row_key,
        "dataset": meta.source.dataset,
        "subject": meta.subjects[0].entity_id if meta.subjects else "",
        "month": row.factor_month,
        "factor": text(row, "factor"),
        "version": meta.version,
        "record_date": row.record_date,
        "payment_date": row.payment_date,
        "business_date": meta.business_date,
        "wac": text(row, "wac"),
        "wam": row.wam if row.HasField("wam") else None,
        "wala": row.wala if row.HasField("wala") else None,
        "published": [t.at_ns for t in meta.source_times
                      if t.kind == ops.SOURCE_TIME_KIND_PUBLISHED],
        "raw": meta.raw.key,
    }


class Reader(reporting.Role):
    """The stand-in's `reporting` role class (SDK 0.35)."""

    async def resolve(self, query):
        one = lambda name: query.get(name, [""])[0]  # noqa: E731
        found = await self.resolve_identifier(identifiers=[meridian.Identifier(
            scheme=one("scheme"), value=one("value"), source=one("source"))])
        return {"found": found.found, "instrument_id": found.instrument_id,
                "reason": ops.MissReason.Name(found.miss_reason)}

    async def factors(self, query):
        one = lambda name: query.get(name, [""])[0]  # noqa: E731
        after = one("after")
        watermark = (ops.Watermark(partitions=[ops.PartitionSequence(
            partition=DATASET, sequence=int(after))]) if after else None)
        answer = await self.list_factors(
            subjects=[meridian.SubjectRef(entity_id=one("subject"))],
            from_date=one("from"), to_date=one("to"), after_watermark=watermark)
        return {
            "factors": [factor_json(f) for f in answer.factors],
            "unanswered": [{"dataset": u.dataset, "reason": ops.UnansweredReason.Name(u.reason)}
                           for u in answer.unanswered],
            "watermark": {p.partition: p.sequence for p in answer.watermark.partitions},
        }

    async def record(self, query):
        found = await self.resolve_instrument(instrument_id=query.get("id", [""])[0])
        held = found.instrument
        return {"found": found.found, "instrument_type": ops.InstrumentType.Name(held.instrument_type),
                "template": f"{held.template_id} {held.template_version}",
                "provisional": held.provisional,
                "identifiers": [f"{i.scheme}:{i.value}:{i.source}" for i in held.identifiers]}

    async def answer(self, path, query):
        if path == "/record":
            return await self.record(query)
        if path == "/resolve":
            return await self.resolve(query)
        if path == "/factors":
            return await self.factors(query)
        return {"page": "the e2e's reader"}


def serve(reader):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            future = asyncio.run_coroutine_threadsafe(
                reader.answer(parsed.path, urllib.parse.parse_qs(parsed.query)), LOOP)
            try:
                body, status = json.dumps(future.result(timeout=60), sort_keys=True), 200
            except Exception as failed:  # said on the page, for the run to quote
                body, status = json.dumps({"failed": f"{type(failed).__name__}: {failed}"}), 500
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            pass

    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


#: What the stand-in registers, its whole declaration (contract v25).
DECLARATION = meridian.Declaration(
    interface=Interface(PORT, "The e2e's reader", pages=[Page("/", "Factors", levels=["read"])])
)


def main():
    reader = Reader()
    threading.Thread(target=serve, args=(reader,), daemon=True).start()
    LOOP.run_until_complete(meridian.run_async(declaration=DECLARATION, roles=[reader]))


if __name__ == "__main__":
    asyncio.set_event_loop(LOOP)
    main()
