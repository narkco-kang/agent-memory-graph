#!/usr/bin/env python3
"""Measure `amg` against any live `group-kg/v1` graph, and print aggregates only.

The first real-world run (docs/REAL-WORLD.md) was done by hand. A measurement that
cannot be re-run on another graph is an anecdote, so this script turns that method
into code:

    python3 benchmarks/real_graph.py /path/to/graph.json [--label NAME]

Method matches the published run: **in-process** calls through the library, timed
with `perf_counter`. It does not use the CLI for timings, because a CLI invocation
also pays tens of milliseconds of interpreter startup — that number is measured
separately and reported as such, so the two cannot be confused.

Guarantees:
  * the source graph is read once and its `sha256` is verified before and after;
  * no node ids, labels, notes or query strings are printed — `related` picks an id
    internally and reports only the neighbour count; treat the output as
    publishable and the source as private.
"""
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from amg import Memory  # noqa: E402
from amg.adopt import adopt as adopt_graph  # noqa: E402

SEARCH_QUERIES = ("task", "decision", "status")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def timed(call, repeats=1):
    """Run call() `repeats` times; return (last result, median milliseconds)."""
    values = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = call()
        values.append((time.perf_counter() - started) * 1000)
    return result, statistics.median(values)


def cli_startup_ms():
    """What a CLI invocation costs before it does any work (for honest labelling)."""
    values = []
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC
    for _ in range(3):
        started = time.perf_counter()
        subprocess.run([sys.executable, "-m", "amg.cli", "version"],
                       capture_output=True, env=env, check=True)
        values.append((time.perf_counter() - started) * 1000)
    return statistics.median(values)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="path to a group-kg/v1 graph.json (read-only)")
    parser.add_argument("--label", default=None, help="name to print in the heading")
    parser.add_argument("--repeat", type=int, default=3, help="repeats for read timings")
    args = parser.parse_args(argv[1:])

    source_file = args.source
    if os.path.isdir(source_file):
        source_file = os.path.join(source_file, "graph.json")
    if not os.path.isfile(source_file):
        raise SystemExit(f"no such graph: {args.source}")
    label = args.label or os.path.basename(os.path.dirname(os.path.abspath(source_file)))

    source_bytes = os.path.getsize(source_file)
    before = sha256(source_file)
    with open(source_file, encoding="utf-8") as fh:
        source_doc = json.load(fh)

    workdir = tempfile.mkdtemp(prefix="amg-real-graph-")
    dest = os.path.join(workdir, "adopted")
    pin_path = os.path.join(workdir, "pin.json")

    report, adopt_ms = timed(lambda: adopt_graph(source_file, dest, pin_out=pin_path))
    after = sha256(source_file)
    with open(pin_path, encoding="utf-8") as fh:
        pin = json.load(fh)

    memory = Memory.open(dest)
    check_rep, check_ms = timed(memory.check, args.repeat)
    audit_rep, audit_ms = timed(memory.audit, args.repeat)
    pinned_rep, pinned_ms = timed(lambda: memory.audit(pin=pin), args.repeat)
    expire_rep, expire_ms = timed(lambda: memory.expire(apply=False), args.repeat)
    fingerprint_rep, fingerprint_ms = timed(memory.fingerprint, args.repeat)
    findings_rep, doctor_ms = timed(memory.security_findings, args.repeat)
    digest_text, digest_ms = timed(memory.digest, args.repeat)
    hits_rep, search_ms = timed(lambda: memory.search(SEARCH_QUERIES[0], k=10), args.repeat)
    _, search_wide_ms = timed(lambda: memory.search(SEARCH_QUERIES[1], k=50), args.repeat)

    degree = {}
    for edge in memory.doc["edges"]:
        for endpoint in (edge.get("from"), edge.get("to")):
            degree[endpoint] = degree.get(endpoint, 0) + 1
    related_count = 0
    related_ms = 0.0
    if degree:
        node_id = max(degree, key=degree.get)
        related_rep, related_ms = timed(lambda: memory.related(node_id), args.repeat)
        related_count = len(related_rep["neighbors"])

    # Counts before the write probe, so the heading describes what adoption produced.
    nodes = len(memory.doc["nodes"])
    edges = len(memory.doc["edges"])
    changes = len(memory.doc["changes"])

    probe = "bench.write.probe"
    _, add_ms = timed(lambda: memory.add_node(
        id=probe, type="task", label="timing probe", source="benchmarks/real_graph.py"))
    startup_ms = cli_startup_ms()

    print(f"## {label}\n")
    print(f"source: {source_bytes:,} bytes, rev {source_doc.get('rev')}, "
          f"{len(source_doc['nodes'])} nodes / {len(source_doc['edges'])} edges / "
          f"{len(source_doc['changes'])} changes")
    print(f"adopted: {nodes} nodes / {edges} edges / {changes} changes")
    print(f"timings: in-process, median of {args.repeat}; "
          f"a CLI invocation costs {startup_ms:.0f} ms of startup before any work\n")
    print("| step | result | time |")
    print("|---|---|---|")
    print(f"| `adopt` | {len(source_doc['nodes'])} → {nodes} nodes, "
          f"{len(source_doc['edges'])} → {edges} edges, "
          f"source `sha256` {'unchanged' if before == after else 'CHANGED (!!)'} | **{adopt_ms:.0f} ms** |")
    print(f"| `check` | {len(check_rep['errors'])} errors | {check_ms:.1f} ms |")
    print(f"| `audit` (no pin) | {len(audit_rep['conflicts'])} conflicts | {audit_ms:.1f} ms |")
    pin_info = pinned_rep.get("pin") or {}
    print(f"| `audit --pin` | {len(pinned_rep['conflicts'])} conflicts, "
          f"pin match {str(pin_info.get('match')).lower()} | {pinned_ms:.1f} ms |")
    eligible = expire_rep.get("eligible") or []
    print(f"| `expire` (dry-run) | {len(eligible)} eligible | {expire_ms:.1f} ms |")
    print(f"| `fingerprint` | rev {fingerprint_rep.get('rev')} | {fingerprint_ms:.1f} ms |")
    print(f"| `doctor` (security findings) | {len(findings_rep)} filesystem findings | {doctor_ms:.1f} ms |")
    print(f"| `search` k=10 | {len(hits_rep)} hits | {search_ms:.1f} ms |")
    print(f"| `search` k=50 | — | {search_wide_ms:.1f} ms |")
    print(f"| `digest` (65,536 B) | {len(digest_text.encode('utf-8')):,} bytes | {digest_ms:.1f} ms |")
    print(f"| `related` depth 1 | {related_count} neighbours | {related_ms:.1f} ms |")
    print(f"| one `add` | atomic rewrite | **{add_ms:.0f} ms** |")
    print(f"\nscratch graph kept at: {dest}")

    if before != after:
        print("\n✗ the source graph changed during adoption — do not publish these numbers")
        return 1
    if report.get("dry_run"):
        print("\n✗ adopt reported a dry run; nothing was measured")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(130)
