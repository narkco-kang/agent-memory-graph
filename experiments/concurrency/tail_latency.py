#!/usr/bin/env python3
"""Lock tail latency on a seeded graph, on whatever OS this runs.

Why this exists: DECISIONS #15 concluded that the ~200 ms tail is starvation from
non-FIFO wake-ups, measured on macOS. The gap was never Windows: the documented
"not measured" line said so from v0.15.0 through v0.32.2. This script produces the same
measurement on every platform the CI matrix covers, so the claim stops being macOS-only.

It measures two things the plain burst numbers cannot separate:

  * **write cost** on a seeded graph (one write, nothing contending) — the queue length
    that a 5 s timeout covers is derived from this, not from a guess;
  * **wait in the lock** under a burst (`Store.lock_stats`): worst wait, how many polls it
    took, and how many waiters saw more than 100 ms.

Usage:
    PYTHONPATH=src python3 experiments/concurrency/tail_latency.py                 # 5,000 nodes, 8x10
    PYTHONPATH=src python3 experiments/concurrency/tail_latency.py --nodes 2000 --writers 8 --writes 5
    PYTHONPATH=src python3 experiments/concurrency/tail_latency.py --json
"""
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402

SHA = "0" * 64  # a well-formed declared digest; the gate checks shape, not truth (#31)


def seed(nodes):
    """A graph with `nodes` records, written in one batch (the cheap path, 0.2-0.5 ms/node)."""
    path = os.path.join(tempfile.mkdtemp(prefix="amg-tail-"), "mem")
    mem = Memory.init(path, "tail")
    payload = [{"id": f"task.seed{i:06d}", "type": "task", "label": "seed probe",
                "source": "tail-latency", "by": "experiment",
                "evidence": [{"locator": "path:README.md", "content_sha256": SHA,
                              "captured_at": "2026-10-20T10:00:00+08:00"}]}
               for i in range(nodes)]
    started = time.perf_counter()
    mem.add_many(payload)
    return path, time.perf_counter() - started


def single_write_ms(path):
    """One write with nothing else running: the cost a queued writer must wait for."""
    mem = Memory.open(path)
    samples = []
    for i in range(5):
        t0 = time.perf_counter()
        mem.add_node(id=f"task.probe{i}", type="task", label="probe", source="tail-latency",
                     by="experiment",
                     evidence=[{"locator": "path:README.md", "content_sha256": SHA,
                                "captured_at": "2026-10-20T10:00:00+08:00"}])
        samples.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(samples), 1)


def run_burst(path, writers, writes):
    script = os.path.join(HERE, "run_stress.py")
    cmd = [sys.executable, script, "--writers", str(writers), "--writes", str(writes),
           "--graph", path, "--json"]
    res = subprocess.run(cmd, capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")})
    if res.returncode != 0:
        raise SystemExit(f"burst failed ({res.returncode}):\n{res.stdout}\n{res.stderr}")
    # run_stress prints its report pretty-printed, so parse the whole stdout.
    start = res.stdout.find("{")
    return json.loads(res.stdout[start:])


def main(argv):
    nodes, writers, writes, as_json = 5000, 8, 10, "--json" in argv
    for i, arg in enumerate(argv):
        if arg == "--nodes":
            nodes = int(argv[i + 1])
        if arg == "--writers":
            writers = int(argv[i + 1])
        if arg == "--writes":
            writes = int(argv[i + 1])

    path, seed_s = seed(nodes)
    single = single_write_ms(path)
    report = run_burst(path, writers, writes)
    lock = report["lock"]
    contended = report["contended"]
    out = {
        "os": platform.system(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "nodes": nodes,
        "seed_seconds": round(seed_s, 2),
        "single_write_ms": single,
        "burst": {"writers": writers, "writes_per_writer": writes,
                  "expected": report["expected_writes"], "present": report["nodes_present"],
                  "missing": report["missing_writes"], "duplicates": report["duplicate_ids"],
                  "errors": report["errors"], "check_ok": report["check_ok"],
                  "changes_for_writes": report["changes_for_stress_writes"],
                  "p50_ms": contended["p50_ms"], "p95_ms": contended["p95_ms"],
                  "max_ms": contended["max_ms"], "writes_per_s": contended["writes_per_s"]},
        "lock": {"acquisitions": lock["acquisitions"], "timeouts": lock["timeouts"],
                 "worst_wait_ms": lock["worst_wait_ms"],
                 "worst_wait_polls": lock["worst_wait_polls"],
                 "waiters_over_100ms": lock["waits_over_100ms"]},
    }
    # A lost write is a failure on every platform; a slow wait is a finding, not a failure.
    if out["burst"]["missing"] or out["burst"]["duplicates"] or out["burst"]["errors"] \
            or not out["burst"]["check_ok"]:
        out["verdict"] = "FAILED"
    else:
        out["verdict"] = "ok"
    print(json.dumps(out, ensure_ascii=False) if as_json else
          f"{out['os']}: {nodes} nodes, single write {single} ms, burst p95 "
          f"{contended['p95_ms']} ms, worst lock wait {lock['worst_wait_ms']} ms "
          f"({lock['worst_wait_polls']} polls), {lock['waits_over_100ms']} waiter(s) > 100 ms, "
          f"{report['expected_writes']} writes intact, verdict {out['verdict']}")
    return 0 if out["verdict"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
