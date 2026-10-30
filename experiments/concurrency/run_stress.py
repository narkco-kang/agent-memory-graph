#!/usr/bin/env python3
"""Concurrency stress: N writer processes × M writes each against one graph.

What it is for: the lock's unit tests prove exclusivity between two processes, but
they do not prove that a burst of concurrent writers loses nothing. This does:

1. every write must appear exactly once (no lost update, no duplicate);
2. every write must produce exactly one change record — the ledger must agree with
   the state;
3. latency under contention is measured, not assumed, alongside a serial baseline.

Usage:
    PYTHONPATH=src python3 experiments/concurrency/run_stress.py                    # 8 × 25
    PYTHONPATH=src python3 experiments/concurrency/run_stress.py --writers 4 --writes 10 --json
"""
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402

WRITER = r"""
import json, sys, time
sys.path.insert(0, sys.argv[1])
from amg import Memory
mem_dir, tag, count = sys.argv[2], sys.argv[3], int(sys.argv[4])
latencies, errors = [], []
m = Memory.open(mem_dir)
started = time.time()
for i in range(count):
    node_id = "stress.%s.n%03d" % (tag, i)
    t0 = time.perf_counter()
    try:
        m.add_node(id=node_id, type="task", label="writer %s item %d" % (tag, i),
                   source="concurrency stress", note="probe", by="stress-" + tag)
        latencies.append(round((time.perf_counter() - t0) * 1000, 2))
    except Exception as exc:
        errors.append("%s: %s" % (type(exc).__name__, exc))
print(json.dumps({"tag": tag, "latencies": latencies, "errors": errors,
                  "lock_stats": m.store.lock_stats,
                  "started": started, "finished": time.time()}))
"""


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(pct / 100 * (len(ordered) - 1)))))
    return ordered[index]


def run(writers, writes, mem_dir):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    started = time.perf_counter()
    procs = []
    for i in range(writers):
        procs.append(subprocess.Popen(
            [sys.executable, "-c", WRITER, os.path.join(ROOT, "src"), mem_dir, str(i), str(writes)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env))
    results = []
    for proc in procs:
        out, err = proc.communicate(timeout=300)
        if proc.returncode != 0:
            raise SystemExit(f"writer failed ({proc.returncode}): {err[-800:]}")
        results.append(json.loads(out.strip().splitlines()[-1]))
    wall_ms = round((time.perf_counter() - started) * 1000, 1)

    latencies = [value for item in results for value in item["latencies"]]
    errors = [msg for item in results for msg in item["errors"]]
    # The burst window excludes interpreter startup, which would otherwise flatter
    # throughput (the 25-write serial run pays startup once, the 200-write burst
    # pays it in parallel).
    burst_window_ms = round((max(i["finished"] for i in results)
                             - min(i["started"] for i in results)) * 1000, 1)
    return results, latencies, errors, wall_ms, burst_window_ms


def serial_baseline(writes, mem_dir):
    """Same number of writes from one process, for a contention-free reference."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    started = time.perf_counter()
    proc = subprocess.run([sys.executable, "-c", WRITER, os.path.join(ROOT, "src"),
                           mem_dir, "serial", str(writes)],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
    wall_ms = round((time.perf_counter() - started) * 1000, 1)
    item = json.loads(proc.stdout.strip().splitlines()[-1])
    span_ms = round((item["finished"] - item["started"]) * 1000, 1)
    return item["latencies"], wall_ms, span_ms


def main(argv):
    writers, writes, as_json = 8, 25, "--json" in argv
    for index, arg in enumerate(argv):
        if arg == "--writers":
            writers = int(argv[index + 1])
        if arg == "--writes":
            writes = int(argv[index + 1])

    graph_dir = os.path.join(tempfile.mkdtemp(prefix="amg-stress-"), "mem")
    Memory.init(graph_dir, group="stress")
    Memory.open(graph_dir).add_node(id="task.baseline", type="task", label="baseline",
                                    source="stress setup", note="n", by="stress")

    results, latencies, errors, wall_ms, burst_window_ms = run(writers, writes, graph_dir)
    serial_latencies, serial_wall_ms, serial_span_ms = serial_baseline(writes, graph_dir)

    m = Memory.open(graph_dir)
    check = m.check()
    ids = [n["id"] for n in m.doc["nodes"]]
    # exclude the serial-baseline probe: it shares the "stress." prefix but is not
    # part of the concurrent burst being verified
    stress_ids = [i for i in ids if i.startswith("stress.") and not i.startswith("stress.serial.")]
    expected = writers * writes
    changes = m.doc["changes"]
    per_target = {}
    for change in changes:
        target = change.get("target")
        per_target[target] = per_target.get(target, 0) + 1
    write_changes = {t: c for t, c in per_target.items()
                     if t and t.startswith("stress.") and not t.startswith("stress.serial.")}
    lock_stats = [item.get("lock_stats") or {} for item in results]
    worst = max(lock_stats, key=lambda s: s.get("wait_max_ms", 0)) if lock_stats else {}
    report = {
        "lock": {
            "acquisitions": sum(s.get("acquisitions", 0) for s in lock_stats),
            "polls_total": sum(s.get("polls", 0) for s in lock_stats),
            "worst_wait_ms": worst.get("wait_max_ms", 0),
            "worst_wait_polls": worst.get("polls_max", 0),
            "timeouts": sum(s.get("timeouts", 0) for s in lock_stats),
            "waits_over_100ms": sum(1 for s in lock_stats if s.get("wait_max_ms", 0) > 100),
        },
        "writers": writers,
        "writes_per_writer": writes,
        "expected_writes": expected,
        "nodes_present": len(stress_ids),
        "duplicate_ids": len(stress_ids) - len(set(stress_ids)),
        "missing_writes": expected - len(stress_ids),
        "errors": errors,
        "check_ok": check["ok"],
        "check_errors": len(check["errors"]),
        "changes_for_stress_writes": len(write_changes),
        "targets_with_wrong_change_count": sum(1 for c in write_changes.values() if c != 1),
        "rev": m.doc.get("rev"),
        "contended": {
            "wall_ms": wall_ms,
            "burst_window_ms": burst_window_ms,
            "writes_per_s": round(expected / (burst_window_ms / 1000), 1),
            "p50_ms": percentile(latencies, 50),
            "p95_ms": percentile(latencies, 95),
            "max_ms": max(latencies) if latencies else 0,
            "total_writes": len(latencies),
        },
        "serial": {
            "wall_ms": serial_wall_ms,
            "burst_window_ms": serial_span_ms,
            "writes_per_s": round(writes / (serial_span_ms / 1000), 1),
            "p50_ms": percentile(serial_latencies, 50),
            "p95_ms": percentile(serial_latencies, 95),
            "max_ms": max(serial_latencies) if serial_latencies else 0,
            "total_writes": len(serial_latencies),
        },
    }
    report["passed"] = (report["nodes_present"] == expected
                        and report["duplicate_ids"] == 0
                        and report["missing_writes"] == 0
                        and not errors
                        and report["check_ok"]
                        and report["targets_with_wrong_change_count"] == 0
                        and report["changes_for_stress_writes"] == expected)

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{writers} writers x {writes} writes = {expected} concurrent writes")
        print(f"  nodes present        {report['nodes_present']}  duplicates {report['duplicate_ids']}  "
              f"missing {report['missing_writes']}")
        print(f"  change records        {report['changes_for_stress_writes']} "
              f"(wrong per-target counts: {report['targets_with_wrong_change_count']})")
        print(f"  check                {'ok' if report['check_ok'] else 'FAILED'} "
              f"({report['check_errors']} errors)")
        print(f"  errors               {len(errors)}")
        print(f"  contended            {report['contended']['p50_ms']} / "
              f"{report['contended']['p95_ms']} / {report['contended']['max_ms']} ms "
              f"(p50/p95/max), {report['contended']['writes_per_s']} writes/s in the "
              f"burst window ({burst_window_ms} ms)")
        print(f"  serial baseline      {report['serial']['p50_ms']} / "
              f"{report['serial']['p95_ms']} / {report['serial']['max_ms']} ms, "
              f"{report['serial']['writes_per_s']} writes/s over {serial_span_ms} ms")
        lock = report["lock"]
        print(f"  lock                   worst wait {lock['worst_wait_ms']} ms after "
              f"{lock['worst_wait_polls']} failed polls; {lock['polls_total']} polls total, "
              f"{lock['timeouts']} timeouts")
        print(f"  => {'PASSED' if report['passed'] else 'FAILED'}")

    out_path = os.path.join(HERE, "result.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
