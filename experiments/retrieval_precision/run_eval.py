#!/usr/bin/env python3
"""Measure the precision of the lexical matcher itself (see PREREGISTRATION.md).

    PYTHONPATH=src python3 experiments/retrieval_precision/run_eval.py
    PYTHONPATH=src python3 experiments/retrieval_precision/run_eval.py --graph /path/to/legacy.json

Without `--graph` it uses the frozen corpus from `retrieval_eval/`; with it, a legacy
`group-kg/v1` graph is adopted into a temporary directory and measured. Aggregates
only — no ids, labels or notes are printed for a real graph (the source is private).

Criteria, fixed before the implementation:
  C1  a one-character ASCII query returns 0 hits
  C2  an identifier query naming an existing node returns that node first
  C3  an identifier query naming no node returns 0 hits
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402
from amg.const import not_yet_valid  # noqa: E402
from amg.adopt import adopt as adopt_graph  # noqa: E402

EVAL_DIR = os.path.join(ROOT, "experiments", "retrieval_eval")
SINGLE_CHARS = ("a", "e", "i", "x", "q")
MISSING_IDENTIFIERS = ("task.a", "issue.zzz", "missing.node")
SAMPLE_SIZE = 20


def golden_ids(ids, sample=SAMPLE_SIZE):
    """Deterministic sample: every n-th id, so the run is reproducible without a seed."""
    ordered = sorted(ids)
    step = max(1, len(ordered) // sample)
    return ordered[::step][:sample]


def run(doc):
    memory = Memory(None, doc)  # read-only use: search() does not write
    report = {"single_char": {}, "identifiers": {"n": 0, "top1": 0, "misses": 0},
              "missing_identifiers": {}}

    for ch in SINGLE_CHARS:
        report["single_char"][ch] = {
            "L3": len(memory.search(ch, layer="L3", k=10)),
            "L2": len(memory.search(ch, layer="L2", k=10)),
        }

    # L3 deliberately never returns a superseded node (expiry is first-class), so an
    # identifier pointing at one has no answer at this layer by design — sampling it
    # would test the filter, not the matcher. See the amendment in PREREGISTRATION.md.
    ids = [n["id"] for n in doc.get("nodes") or []
           if n.get("status") != "superseded" and not not_yet_valid(n)]
    sample = golden_ids(ids)
    found = 0
    for node_id in sample:
        hits = memory.search(node_id, layer="L3", k=10)
        if hits and hits[0]["id"] == node_id:
            found += 1
    report["identifiers"] = {"n": len(sample), "top1": found,
                             "rate": round(found / len(sample), 3) if sample else None}

    for query in MISSING_IDENTIFIERS:
        report["missing_identifiers"][query] = len(memory.search(query, layer="L3", k=10))

    report["ok"] = (
        all(not v for counts in report["single_char"].values() for v in counts.values())
        and report["identifiers"]["top1"] == report["identifiers"]["n"]
        and all(v == 0 for v in report["missing_identifiers"].values())
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", help="legacy group-kg/v1 graph.json to adopt and measure")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    temp = None
    try:
        if args.graph:
            temp = tempfile.mkdtemp(prefix="amg-precision-")
            dest = os.path.join(temp, "graph")
            adopt_graph(args.graph, dest, pin_out=os.path.join(temp, "pin.json"))
            result = run(Memory.open(dest).doc)
            result["source"] = {"real_graph": True, "nodes": len(Memory.open(dest).doc["nodes"])}
        else:
            with open(os.path.join(EVAL_DIR, "corpus.json"), encoding="utf-8") as fh:
                doc = json.load(fh)
            result = run(doc)
            result["source"] = {"real_graph": False, "nodes": len(doc["nodes"])}

        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "result.json")
        if not args.graph:
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
                fh.write("\n")
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"source: {'real graph' if args.graph else 'frozen corpus'} "
                  f"({result['source']['nodes']} nodes)")
            for ch, counts in result["single_char"].items():
                print(f"  C1 single char {ch!r}: L3={counts['L3']} L2={counts['L2']}")
            ident = result["identifiers"]
            print(f"  C2 identifier lookups: top-1 in {ident['top1']}/{ident['n']} "
                  f"(rate {ident['rate']})")
            for query, hits in result["missing_identifiers"].items():
                print(f"  C3 missing identifier {query!r}: {hits} hit(s)")
            print("criteria:", "all hold" if result["ok"] else "NOT met")
        return 0 if result["ok"] else 1
    finally:
        if temp:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
