#!/usr/bin/env python3
"""Benchmark read and write paths at 1k / 5k / 10k nodes.

Builds schema-valid graphs directly on disk (no library writes, so the data set
is reproducible), then times the read paths. The write path is measured on small
graphs because every write rewrites the whole file — see the conclusion in
docs/BENCHMARKS.md.
"""
import json
import os
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from amg import Memory  # noqa: E402
from amg.const import now  # noqa: E402

SHA = "a" * 64


def make_node(i, with_evidence=True):
    stamp = "2026-10-20T10:00:00+08:00"
    node = {
        "id": f"task.n{i:06d}", "type": "task", "label": f"task number {i} parser queue",
        "status": "open", "owner": None, "source": "bench", "note": f"synthetic node {i}",
        "evidence": ([{"locator": "path:README.md", "content_sha256": SHA,
                      "captured_at": stamp, "graph_rev": 1}] if with_evidence else []),
        "conclusion": False, "evidence_grade": 1 if with_evidence else None,
        "valid_from": None, "valid_until": None, "valid_time_known": False,
        "recorded_at": stamp, "superseded_at": None, "updatedAt": stamp,
    }
    return node


def build(path, n, edges_per_node=0):
    os.makedirs(path, exist_ok=True)
    # 2 change records per node, matching the ratio of the real graph we migrated
    changes = []
    for i in range(n):
        for k in range(2):
            changes.append({"at": "2026-10-20T10:00:00+08:00", "by": "bench",
                            "op": "add-node" if k == 0 else "set-status",
                            "target": f"task.n{i:06d}", "rev": 2 * i + k + 1,
                            "note": f"synthetic change {i}.{k}"})
    doc = {"schema": "amg/v1", "group": "bench", "session": "", "goal": "bench",
           "updatedAt": now(), "rev": 2 * n, "nodes": [make_node(i) for i in range(n)],
           "edges": [{"from": f"task.n{i:06d}", "to": f"task.n{(i * 7 + 3) % n:06d}",
                      "kind": "relates_to"}
                     for i in range(n) for _ in range(edges_per_node)],
           "changes": changes}
    with open(os.path.join(path, "graph.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    return path


def timed(fn, repeat=3):
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples)


def main():
    rows = []
    for n, epn in ((1000, 0), (1000, 1), (5000, 1), (10000, 0), (10000, 1)):
        path = build(os.path.join(tempfile.mkdtemp(prefix="amg-bench-"), "mem"), n, epn)
        t_check = timed(lambda: Memory.open(path).check())
        t_audit = timed(lambda: Memory.open(path).audit())
        t_search = timed(lambda: Memory.open(path).search("parser queue", k=10))
        t_digest = timed(lambda: Memory.open(path).digest(max_bytes=65536))
        size = os.path.getsize(os.path.join(path, "graph.json"))
        rows.append({"nodes": n, "edges": n * epn, "file_bytes": size, "check_ms": round(t_check, 1),
                     "audit_ms": round(t_audit, 1), "search_ms": round(t_search, 1),
                     "digest_ms": round(t_digest, 1)})
        print(rows[-1])

    # write path: one add_node at n=1000 (full-graph rewrite per write)
    write_rows = []
    for n in (100, 1000, 5000):
        path = build(os.path.join(tempfile.mkdtemp(prefix="amg-bench-w-"), "mem"), n)
        m = Memory.open(path)
        t0 = time.perf_counter()
        m.add_node("task.probe", "task", "probe", source="bench")
        single = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        for i in range(20):
            m.add_node(f"task.w{i}", "task", "write probe", source="bench")
        twenty = ((time.perf_counter() - t0) * 1000) / 20
        write_rows.append({"nodes": n, "first_add_ms": round(single, 1),
                           "mean_add_ms": round(twenty, 1)})
        print(write_rows[-1])

    out = {"read": rows, "write": write_rows,
           "note": "single host, local disk, median of 3; synthetic schema-valid nodes"}
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "result.json"), "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    return out


if __name__ == "__main__":
    main()
