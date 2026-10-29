#!/usr/bin/env python3
"""Measure how far `changes[].at` is from the true fact time.

Question
--------
A graph does not record *when a fact became true*; it records *when it was
written*. The cheap alternative to asking writers for a fact time is to pretend
transaction time is validity time: derive `valid_from` from `changes[].at`.

This experiment quantifies how wrong that proxy is, using facts whose true
times we know. It is the measurement behind DECISIONS #5 ("never back-fill
`valid_from` from the change log") and behind the v0.2 question: *do we need an
explicit fact-time input?*

Pre-registered decision rule (fixed before running, per project policy)
----------------------------------------------------------------------
Fixture: 20 facts whose true time precedes their write time by 3 / 10 / 30 days
(7 / 7 / 6). For each fact compare the `changes[].at`-derived `valid_from` with
the true fact time.
    deviation = |derived_valid_from − fact_time_true| in days
If **≥ 30%** of the 20 facts deviate by **> 1 day**, then v0.2 MUST introduce an
explicit fact-time input. Otherwise the current behaviour stays, but the limit
must be documented.

What is actually measured, given the current implementation
-----------------------------------------------------------
`amg adopt` refuses to invent `valid_from` (it stays `null`, the node carries
`valid_time_known: false`). So the experiment does not read `valid_from` from the
adopted graph: it reads the transaction time that a naive back-fill *would* have
used, and compares it with the truth. That keeps the measurement independent of
the safety feature it is supposed to justify.

Usage
-----
    python3 experiments/valid_from_bias/run_experiment.py
    # writes fixture_legacy.json, truth.json, result.json next to this file
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402

# (bucket label, lag in days, how many facts)
LAGGED_BUCKETS = [("3d", 3, 7), ("10d", 10, 7), ("30d", 30, 6)]
CONTROL_COUNT = 10
WRITE_EPOCH = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone.utc)
DEVIATION_LIMIT_DAYS = 1.0
DECISION_THRESHOLD = 0.30


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def build_fixture():
    """Build a legacy-shaped graph plus the ground truth sidecar."""
    nodes, changes, truth = [], [], {}
    rev = 0
    index = 0

    def add_fact(node_id, fact_time, write_time, bucket, lag_days):
        nonlocal rev
        rev += 1
        nodes.append({
            "id": node_id,
            "type": "task",
            "label": f"fact recorded {lag_days}d late" if lag_days else "fact recorded on time",
            "status": "open",
            # Deliberately no valid_from / valid_until: legacy format has none.
            "source": f"experiment:valid_from_bias:{bucket}",
            "note": "ground truth lives in truth.json, not in the graph",
            "updatedAt": _iso(write_time),
        })
        changes.append({
            "at": _iso(write_time), "by": "fixture", "op": "add-node",
            "target": node_id, "rev": rev, "note": "",
        })
        truth[node_id] = {
            "bucket": bucket,
            "lag_days": lag_days,
            "fact_time_true": _iso(fact_time),
            "write_time": _iso(write_time),
        }

    for bucket, lag, count in LAGGED_BUCKETS:
        for i in range(count):
            index += 1
            write_time = WRITE_EPOCH + timedelta(days=index)
            add_fact(f"fact.{bucket}-{i + 1:02d}", write_time - timedelta(days=lag),
                     write_time, bucket, lag)

    for i in range(CONTROL_COUNT):
        index += 1
        write_time = WRITE_EPOCH + timedelta(days=index)
        add_fact(f"fact.control-{i + 1:02d}", write_time, write_time, "control", 0)

    doc = {
        "schema": "group-kg/v1",  # legacy shape that `amg adopt` reads
        "group": "valid-from-bias-fixture",
        "session": "",
        "goal": "measure changes[].at vs true fact time",
        "updatedAt": _iso(WRITE_EPOCH + timedelta(days=index)),
        "rev": rev,
        "nodes": nodes,
        "edges": [],
        "changes": changes,
    }
    return doc, truth


def derive_valid_from(doc):
    """The naive back-fill: first add-node change per target, as transaction time."""
    derived = {}
    for change in doc.get("changes") or []:
        target = change.get("target")
        if target and change.get("op") == "add-node" and target not in derived:
            derived[target] = change.get("at")
    return derived


def measure(adopted_doc, truth):
    derived = derive_valid_from(adopted_doc)
    rows = []
    for node_id, meta in sorted(truth.items()):
        node = next(n for n in adopted_doc["nodes"] if n["id"] == node_id)
        proxy = derived.get(node_id)
        fact_time = datetime.fromisoformat(meta["fact_time_true"])
        proxy_time = datetime.fromisoformat(proxy) if proxy else None
        deviation = (abs((proxy_time - fact_time).total_seconds()) / 86400.0
                     if proxy_time else None)
        rows.append({
            "id": node_id,
            "bucket": meta["bucket"],
            "lag_days": meta["lag_days"],
            "fact_time_true": meta["fact_time_true"],
            "proxy_valid_from": proxy,
            "deviation_days": None if deviation is None else round(deviation, 3),
            "exceeds_limit": None if deviation is None else deviation > DEVIATION_LIMIT_DAYS,
            # what the adopted graph actually stores: the safety feature under test
            "adopted_valid_from": node.get("valid_from"),
            "adopted_valid_time_known": node.get("valid_time_known"),
        })
    return rows


def summarize(rows):
    def ratio(subset):
        if not subset:
            return None
        bad = sum(1 for r in subset if r["exceeds_limit"])
        return {"n": len(subset), "exceeding": bad, "ratio": round(bad / len(subset), 3)}

    lagged = [r for r in rows if r["bucket"] != "control"]
    control = [r for r in rows if r["bucket"] == "control"]
    buckets = {}
    for bucket, _, _ in LAGGED_BUCKETS:
        subset = [r for r in rows if r["bucket"] == bucket]
        devs = [r["deviation_days"] for r in subset]
        buckets[bucket] = {
            "n": len(subset),
            "mean_deviation_days": round(sum(devs) / len(devs), 3),
            "min_deviation_days": min(devs),
            "max_deviation_days": max(devs),
            "ratio_exceeding": ratio(subset)["ratio"],
        }
    return {
        "lagged": ratio(lagged),
        "control": ratio(control),
        "all_facts": ratio(rows),
        "by_bucket": buckets,
        "decision_threshold": DECISION_THRESHOLD,
        "limit_days": DEVIATION_LIMIT_DAYS,
        "verdict": ("v0.2 MUST add an explicit fact-time input"
                    if ratio(lagged)["ratio"] >= DECISION_THRESHOLD
                    else "proxy is adequate; keep behaviour and document the limit"),
        "adopted_valid_from_is_null": all(r["adopted_valid_from"] is None for r in rows),
        "adopted_valid_time_known_false": all(r["adopted_valid_time_known"] is False for r in rows),
    }


def main() -> int:
    doc, truth = build_fixture()
    with open(os.path.join(HERE, "fixture_legacy.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(os.path.join(HERE, "truth.json"), "w", encoding="utf-8") as fh:
        json.dump(truth, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    workdir = tempfile.mkdtemp(prefix="valid-from-bias-")
    adopted_dir = os.path.join(workdir, "adopted")
    report = Memory.adopt(os.path.join(HERE, "fixture_legacy.json"), adopted_dir,
                          group="valid-from-bias-fixture")
    adopted = Memory.open(adopted_dir).doc

    rows = measure(adopted, truth)
    summary = summarize(rows)
    result = {
        "fixture": {
            "facts": len(rows),
            "lagged_buckets": {b: n for b, _, n in LAGGED_BUCKETS},
            "control": CONTROL_COUNT,
            "note": "transaction times are synthetic fixtures; no real graph data",
        },
        "adopt_check_ok": report["check"]["ok"],
        "adopt_check_errors": report["check"]["errors"],
        "summary": summary,
        "rows": rows,
    }
    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"facts={len(rows)}  adopt check ok={report['check']['ok']}")
    print(f"{'bucket':8s} {'n':>3s} {'mean':>8s} {'min':>8s} {'max':>8s} {'>1d':>6s}")
    for bucket, info in summary["by_bucket"].items():
        print(f"{bucket:8s} {info['n']:3d} {info['mean_deviation_days']:8.2f} "
              f"{info['min_deviation_days']:8.2f} {info['max_deviation_days']:8.2f} "
              f"{info['ratio_exceeding']:6.2f}")
    print(f"lagged >1d ratio : {summary['lagged']['exceeding']}/{summary['lagged']['n']} "
          f"= {summary['lagged']['ratio']:.1%}  (threshold {DECISION_THRESHOLD:.0%})")
    print(f"control >1d ratio: {summary['control']['exceeding']}/{summary['control']['n']} "
          f"= {summary['control']['ratio']:.1%}")
    print(f"all facts        : {summary['all_facts']['exceeding']}/{summary['all_facts']['n']} "
          f"= {summary['all_facts']['ratio']:.1%}")
    print(f"adopted valid_from all null: {summary['adopted_valid_from_is_null']}")
    print(f"adopted valid_time_known all false: {summary['adopted_valid_time_known_false']}")
    print(f"VERDICT: {summary['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
