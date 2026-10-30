#!/usr/bin/env python3
"""Field-specific IDF vs the frozen v0.18.0 scorer — see PREREGISTRATION.md.

    PYTHONPATH=src python3 experiments/retrieval_field_df/run_eval.py
    PYTHONPATH=src python3 experiments/retrieval_field_df/run_eval.py --json

Same four corpora and metric functions as `experiments/retrieval_idf/`, so N1–N3 stay
comparable across rounds. Both scorers run in one process; the per-query id sets are
compared as well, because criterion C6 says only the order may change.

Writes `result.json` next to this file.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import retrieval  # noqa: E402

EVAL_DIR = os.path.join(ROOT, "experiments", "retrieval_eval")
IDF_DIR = os.path.join(ROOT, "experiments", "retrieval_idf")
DEEP_K = 100

FROZEN_MIN = {"recall@5": 0.865, "recall@1": 0.731, "mrr@10": 0.821}
N3_MIN_R5 = 0.865
N2_MIN_R5 = 0.538
N2_TARGET_R5 = 0.70
LATENCY_FACTOR = 1.25


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
baseline = _load("baseline", os.path.join(HERE, "baseline.py"))
idf_round = _load("idf_round", os.path.join(IDF_DIR, "run_eval.py"))
ten_k = idf_round.ten_k


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def evaluate(search_fn, doc, queries):
    nodes_by_id = {n["id"]: n for n in doc["nodes"]}
    rows = run_eval.stratified_halves(
        run_eval.evaluate(search_fn, doc, queries, nodes_by_id))
    deep, latencies, id_sets = {}, [], {}
    for item in queries:
        hits = search_fn(doc, item["query"], layer="L3", k=DEEP_K)
        ranked = [h["id"] for h in hits]
        deep[item["id"]] = next((i for i, node_id in enumerate(ranked, start=1)
                                 if node_id in item["gold"]), None)
        id_sets[item["id"]] = sorted(ranked)
        for _ in range(5):  # a few samples per query: p95 needs a tail, not one draw
            started = time.perf_counter()
            search_fn(doc, item["query"], layer="L3", k=10)
            latencies.append((time.perf_counter() - started) * 1000)
    groups = {name: run_eval.aggregate(members)
              for name, members in run_eval.group_rows(rows).items()}
    return {
        "nodes": len(doc["nodes"]),
        "groups": groups,
        "gold_rank_by_query": deep,
        "misses_at_5": [r["id"] for r in rows if r["recall@5"] == 0.0],
        "latency_ms": {"p50": round(statistics.median(latencies), 2),
                       "p95": round(percentile(latencies, 0.95), 2),
                       "max": round(max(latencies), 2)},
        "hit_id_sets": id_sets,
    }


def verdicts(result):
    got = result["corpora"]
    frozen = got["control"]["shipped"]["groups"]["overall"]
    out = {
        "C1_frozen": all(frozen[k] >= v for k, v in FROZEN_MIN.items()),
        "C2_n1": all(got["n1"]["shipped"]["groups"]["overall"][k]
                     >= v for k, v in got["n1"]["baseline"]["groups"]["overall"].items()),
        "C3_n3": got["n3"]["shipped"]["groups"]["overall"]["recall@5"] >= N3_MIN_R5,
        "C4_n2": got["n2"]["shipped"]["groups"]["overall"]["recall@5"] >= N2_MIN_R5,
        "C6_hit_sets": True,
    }
    base_p95 = got["n2"]["baseline"]["latency_ms"]["p95"]
    cand_p95 = got["n2"]["shipped"]["latency_ms"]["p95"]
    out["C5_latency"] = cand_p95 <= LATENCY_FACTOR * base_p95
    out["latency_ratio"] = round(cand_p95 / base_p95, 3) if base_p95 else None
    for corpus in ("control", "n1", "n2", "n3"):
        for query_id, ids in got[corpus]["baseline"]["hit_id_sets"].items():
            if got[corpus]["shipped"]["hit_id_sets"][query_id] != ids:
                out["C6_hit_sets"] = False
                out.setdefault("hit_set_changes", []).append(f"{corpus}/{query_id}")
    out["N2_target_met"] = (got["n2"]["shipped"]["groups"]["overall"]["recall@5"]
                            >= N2_TARGET_R5)
    out["ship"] = all(out[k] for k in
                      ("C1_frozen", "C2_n1", "C3_n3", "C4_n2", "C5_latency", "C6_hit_sets"))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    doc, queries = ten_k.load_inputs()
    corpora = {"control": doc, "n1": ten_k.inflate(doc),
               "n2": ten_k.inflate_vocabulary(doc, queries),
               "n3": idf_round.inflate_frequent(doc)}

    result = {
        "inputs": {
            "corpus_sha256": sha256(os.path.join(EVAL_DIR, "corpus.json")),
            "queries_sha256": sha256(os.path.join(EVAL_DIR, "queries.json")),
            "scorers": {"baseline": "v0.18.0 term-level IDF (baseline.py)",
                        "shipped": "v0.19.0 field-specific IDF (src/amg/retrieval.py)"},
        },
        "corpora": {},
        "criteria": {"frozen_min": FROZEN_MIN, "n3_min_r5": N3_MIN_R5,
                     "n2_min_r5": N2_MIN_R5, "n2_target_r5": N2_TARGET_R5,
                     "latency_factor": LATENCY_FACTOR},
    }
    for name, corpus in corpora.items():
        result["corpora"][name] = {
            "baseline": evaluate(baseline.search, corpus, queries),
            "shipped": evaluate(retrieval.search, corpus, queries),
        }
    result["verdicts"] = verdicts(result)

    # Keep result.json small: the full per-query id sets are diagnostics, not output.
    for entry in result["corpora"].values():
        for side in entry.values():
            side.pop("hit_id_sets", None)
    result["per_query"] = {
        name: {"baseline": {q: entry["baseline"]["gold_rank_by_query"][q]
                            for q in entry["baseline"]["gold_rank_by_query"]},
               "shipped": entry["shipped"]["gold_rank_by_query"]}
        for name, entry in [(n, result["corpora"][n]) for n in ("control", "n3", "n2")]
    }

    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"{'corpus':8} {'scorer':8} {'r@1':>6} {'r@5':>6} {'r@10':>6} {'mrr':>6} "
          f"{'p50':>7} {'p95':>7}")
    for name in ("control", "n1", "n2", "n3"):
        for scorer in ("baseline", "shipped"):
            entry = result["corpora"][name][scorer]
            g = entry["groups"]["overall"]
            print(f"{name:8} {scorer:8} {g['recall@1']:>6.3f} {g['recall@5']:>6.3f} "
                  f"{g['recall@10']:>6.3f} {g['mrr@10']:>6.3f} "
                  f"{entry['latency_ms']['p50']:>7.1f} {entry['latency_ms']['p95']:>7.1f}")
    print("\nrank changes (control / n3):")
    for corpus in ("control", "n3"):
        base = result["corpora"][corpus]["baseline"]["gold_rank_by_query"]
        cand = result["corpora"][corpus]["shipped"]["gold_rank_by_query"]
        moved = [f"{q}:{base[q]}->{cand[q]}" for q in sorted(base) if base[q] != cand[q]]
        print(f"  {corpus}: {', '.join(moved) if moved else 'none'}")
    v = result["verdicts"]
    print("\ncriteria:")
    for key in ("C1_frozen", "C2_n1", "C3_n3", "C4_n2", "C5_latency", "C6_hit_sets"):
        print(f"  {key}: {v[key]}")
    print(f"  latency ratio: {v['latency_ratio']}x (budget {LATENCY_FACTOR}x)")
    print(f"  N2 target r@5 >= {N2_TARGET_R5}: {v['N2_target_met']}")
    if v.get("hit_set_changes"):
        print(f"  hit-set changes: {v['hit_set_changes'][:10]}")
    print(f"  ship v0.19.0: {v['ship']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
