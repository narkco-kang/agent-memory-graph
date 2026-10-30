#!/usr/bin/env python3
"""Price `amg archive` on a real graph: what the ledger costs, and what moving it buys.

The published write-cost numbers (docs/WRITE-COST.md) are medians on two real graphs.
A new capability needs the same treatment, so this script measures one graph end to
end and prints aggregates only — no node ids, labels or notes (the source is private).

    python3 benchmarks/archive_cost.py /path/to/legacy-graph.json [--days N]
    python3 benchmarks/archive_cost.py --amg-dir /path/to/amg-graph

Method: in-process library calls, `perf_counter`, median of `--repeat` runs (default 5).
A CLI invocation is not used for timings because it also pays interpreter startup.
The source file is read only; a legacy source is adopted into a temporary directory
that is removed afterwards.
"""
import argparse
import hashlib
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402
from amg.adopt import adopt as adopt_graph  # noqa: E402
from amg.store import dumps  # noqa: E402


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def median_ms(call, repeats):
    values = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = call()
        values.append((time.perf_counter() - started) * 1000)
    return result, statistics.median(values)


def ledger_share(doc):
    """Fraction of the serialized file that is change records.

    Computed as two serializations of the same document: one with an empty ledger,
    one as it is. This is the honest denominator — not `len(json.dumps(changes))`,
    which would omit the field's own framing.
    """
    full = len(dumps(doc).encode("utf-8"))
    without = len(dumps({**doc, "changes": []}).encode("utf-8"))
    return (full - without) / full if full else 0.0


def write_probe(memory, repeats, by):
    """A real write: flip a node's status back and forth, one transaction each."""
    nodes = [n for n in memory.doc["nodes"] if n.get("status") in ("open", "done")]
    if not nodes:
        return None
    node = nodes[0]
    state = {"status": node.get("status")}

    def one_write():
        nxt = "done" if state["status"] != "done" else "open"
        refreshed = Memory.open(memory.store.dir)
        refreshed.set_status(node["id"], nxt, note="archive benchmark", by=by)
        state["status"] = nxt

    _, ms = median_ms(one_write, repeats)
    return ms


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", help="legacy group-kg/v1 graph.json to adopt")
    parser.add_argument("--amg-dir", help="an already-adopted amg graph directory")
    parser.add_argument("--days", type=int, default=30, help="archive cutoff in days (default 30)")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    temp = None
    try:
        if args.amg_dir:
            graph_dir = os.path.abspath(args.amg_dir)
            source_sha = None
            adopt_ms = None
        else:
            if not args.source:
                parser.error("give a legacy graph path or --amg-dir")
            source_sha = sha256(args.source)
            temp = tempfile.mkdtemp(prefix="amg-archive-cost-")
            graph_dir = os.path.join(temp, "graph")
            started = time.perf_counter()
            adopt_graph(args.source, graph_dir, pin_out=os.path.join(temp, "pin.json"))
            adopt_ms = (time.perf_counter() - started) * 1000
            if sha256(args.source) != source_sha:
                raise SystemExit("source graph changed during the run; refusing the numbers")

        memory = Memory.open(graph_dir)
        doc = memory.doc
        sizes = {"bytes": os.path.getsize(memory.store.file), "changes": len(doc["changes"]),
                 "nodes": len(doc["nodes"]), "edges": len(doc["edges"])}
        share = ledger_share(doc)
        write_before = write_probe(memory, args.repeat, "benchmark-before")

        dry = Memory.open(graph_dir).archive(days=args.days, apply=False)
        report, verify_ms = median_ms(
            lambda: Memory.open(graph_dir).archive_verify(), max(3, args.repeat // 2))
        applied = Memory.open(graph_dir).archive(days=args.days, apply=True)
        after = Memory.open(graph_dir)
        write_after = write_probe(after, args.repeat, "benchmark-after")
        bytes_after = os.path.getsize(after.store.file)

        out = {
            "source": {"path": os.path.basename(args.source) if args.source else None,
                       "sha256": source_sha, "adopt_ms": adopt_ms},
            "graph": sizes,
            "ledger_share_of_file": round(share, 4),
            "archive": {"days": args.days, "eligible": dry["eligible"],
                        "deferred_behind_newer": dry["deferred_behind_newer"],
                        "undated_after_prefix": dry["unknown_time_after_prefix"],
                        "archived": applied["archived"],
                        "bytes_before": applied.get("bytes_before"),
                        "bytes_after": bytes_after,
                        "snapshot_bytes": applied["snapshot"]["bytes"] if applied.get("snapshot") else 0,
                        "verify": applied.get("verify")},
            "verify_ms": round(verify_ms, 1),
            "write_ms": {"before": round(write_before, 1) if write_before else None,
                         "after": round(write_after, 1) if write_after else None},
        }
        try:
            out["loadavg"] = round(os.getloadavg()[0], 2)
        except (AttributeError, OSError):
            out["loadavg"] = None
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"graph {sizes['bytes']} B / {sizes['nodes']} nodes / "
                  f"{sizes['edges']} edges / {sizes['changes']} change records")
            print(f"ledger share of file: {share:.1%}")
            print(f"archive @{args.days} d: eligible {dry['eligible']} of {sizes['changes']}"
                  f" (deferred {dry['deferred_behind_newer']}, undated {dry['unknown_time_after_prefix']})")
            print(f"  file {applied.get('bytes_before')} -> {bytes_after} B"
                  f" ({bytes_after - (applied.get('bytes_before') or 0):+d})")
            v = applied.get("verify") or {}
            print(f"  proof ok={v.get('ok')} state_unchanged={v.get('state_unchanged')} "
                  f"rev_contiguous={v.get('rev_contiguous')}")
            print(f"single write: {write_before:.1f} ms -> {write_after:.1f} ms"
                  if write_before and write_after else "single write: n/a")
            print(f"archive --verify: {verify_ms:.1f} ms, loadavg {out['loadavg']}")
        return 0
    finally:
        if temp:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
