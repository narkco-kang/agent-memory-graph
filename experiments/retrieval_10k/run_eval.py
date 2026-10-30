#!/usr/bin/env python3
"""Retrieval recall at 10,000 nodes — see PREREGISTRATION.md.

    PYTHONPATH=src python3 experiments/retrieval_10k/run_eval.py
    PYTHONPATH=src python3 experiments/retrieval_10k/run_eval.py --json

Loads the frozen 27-node corpus and its 26 queries, adds 9,973 deterministic
distractors from the same generator the write benchmarks use, and runs the same
metric functions as `retrieval_eval/` — so the comparison is like-for-like.

Writes `result.json` next to this file (never into `retrieval_eval/`, whose numbers
stay frozen).
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
TARGET_NODES = 10000
DEEP_K = 100


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
bench = _load("bench", os.path.join(ROOT, "benchmarks", "bench.py"))


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def corpus_digest(nodes):
    payload = json.dumps(sorted(nodes, key=lambda n: n["id"]), sort_keys=True,
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_inputs():
    with open(os.path.join(EVAL_DIR, "corpus.json"), encoding="utf-8") as fh:
        doc = json.load(fh)
    with open(os.path.join(EVAL_DIR, "queries.json"), encoding="utf-8") as fh:
        queries = json.load(fh)["queries"]
    return doc, queries


def inflate(doc, target=TARGET_NODES):
    """Noise model N1: frozen corpus + distractors from the write-benchmark generator."""
    nodes = list(doc["nodes"])
    existing = {n["id"] for n in nodes}
    index = 0
    while len(nodes) < target:
        node = bench.make_node(index, with_evidence=False)
        node["source"] = "synthetic distractor"
        if node["id"] not in existing:
            nodes.append(node)
            existing.add(node["id"])
        index += 1
    return {"schema": doc.get("schema"), "group": doc.get("group"),
            "nodes": nodes, "edges": [], "changes": []}


def inflate_vocabulary(doc, queries, target=TARGET_NODES):
    """Noise model N2: distractors built from the queries' own tokens (deterministic).

    This is the realistic noise for a long-lived memory graph: most notes discuss what
    people have already asked about, so they compete on the same words. Seed is fixed so
    the corpus is reproducible byte-for-byte.
    """
    import random
    pool = sorted({token for item in queries
                   for token in run_eval.TOKEN.findall(item["query"].lower())
                   if len(token) >= 3})
    rng = random.Random(20261031)
    nodes = list(doc["nodes"])
    existing = {n["id"] for n in nodes}
    index = 0
    while len(nodes) < target:
        words = [rng.choice(pool) for _ in range(6)]
        node = bench.make_node(index, with_evidence=False)
        node["label"] = " ".join(words[:3])
        node["note"] = "synthetic note " + " ".join(words[3:])
        node["source"] = "synthetic query-vocabulary distractor"
        if node["id"] not in existing:
            nodes.append(node)
            existing.add(node["id"])
        index += 1
    return {"schema": doc.get("schema"), "group": doc.get("group"),
            "nodes": nodes, "edges": [], "changes": []}


def metrics(rows):
    groups = {}
    for name, members in run_eval.group_rows(rows).items():
        groups[name] = run_eval.aggregate(members)
    return groups


def run(doc, queries):
    nodes_by_id = {n["id"]: n for n in doc["nodes"]}
    rows = run_eval.stratified_halves(
        run_eval.evaluate(retrieval.search, doc, queries, nodes_by_id))

    # Deep ranking for the diagnostic: is a miss unmatched, or matched but diluted?
    deep = {}
    for item in queries:
        hits = retrieval.search(doc, item["query"], layer="L3", k=DEEP_K)
        ranked = [h["id"] for h in hits]
        rank = next((i for i, node_id in enumerate(ranked, start=1)
                     if node_id in item["gold"]), None)
        deep[item["id"]] = rank

    latencies = []
    for item in queries:
        started = time.perf_counter()
        retrieval.search(doc, item["query"], layer="L3", k=10)
        latencies.append((time.perf_counter() - started) * 1000)

    misses = [r for r in rows if r["recall@5"] == 0.0]
    diluted = sum(1 for r in misses if deep.get(r["id"]) and deep[r["id"]] > 10)
    unmatched = len(misses) - diluted

    return {
        "nodes": len(doc["nodes"]),
        "corpus_sha256": corpus_digest(doc["nodes"]),
        "groups": metrics(rows),
        "diagnostic": {
            "misses_at_5": len(misses),
            "matched_but_ranked_11_100": diluted,
            "unmatched_or_beyond_100": unmatched,
            "gold_rank_by_query": deep,
        },
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2),
            "max": round(max(latencies), 2),
        },
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    doc, queries = load_inputs()
    inputs = {
        "corpus_sha256": sha256(os.path.join(EVAL_DIR, "corpus.json")),
        "queries_sha256": sha256(os.path.join(EVAL_DIR, "queries.json")),
    }
    frozen = None
    try:
        with open(os.path.join(EVAL_DIR, "result.json"), encoding="utf-8") as fh:
            frozen = json.load(fh)
    except OSError:
        pass

    control = run(doc, queries)
    n1 = run(inflate(doc), queries)
    n2 = run(inflate_vocabulary(doc, queries), queries)
    scaled = n2  # the harder, more realistic model is the headline; N1 is the control

    result = {
        "control_27": {"nodes": control["nodes"], "group": control["groups"],
                       "latency_ms": control["latency_ms"],
                       "corpus_sha256": control["corpus_sha256"]},
        "at_10k_n1_unrelated": {"nodes": n1["nodes"], "group": n1["groups"],
                                "latency_ms": n1["latency_ms"],
                                "corpus_sha256": n1["corpus_sha256"]},
        "at_10k_n2_query_vocabulary": {"nodes": scaled["nodes"], "group": scaled["groups"],
                                       "latency_ms": scaled["latency_ms"],
                                       "corpus_sha256": scaled["corpus_sha256"]},
        "diagnostic": scaled["diagnostic"],
        "inputs": inputs,
        "frozen_baseline": ({"corpus_sha256": frozen.get("corpus_sha256"),
                             "queries_sha256": frozen.get("queries_sha256"),
                             "overall": frozen.get("summary", {}).get("overall")}
                            if frozen else None),
        "rows": scaled["rows"],
    }
    result["inputs_match_frozen"] = bool(
        frozen
        and frozen.get("corpus_sha256") == inputs["corpus_sha256"]
        and frozen.get("queries_sha256") == inputs["queries_sha256"])

    out_path = os.path.join(HERE, "result.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != "rows"},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"corpus {result['control_27']['nodes']} -> "
              f"{result['at_10k_n2_query_vocabulary']['nodes']} nodes "
              f"(inputs match frozen: {result['inputs_match_frozen']})")
        for label, key in (("control 27", "control_27"),
                           ("N1 unrelated 10k", "at_10k_n1_unrelated"),
                           ("N2 query-vocab 10k", "at_10k_n2_query_vocabulary")):
            g = result[key]["group"]["overall"]
            print(f"  {label}: recall@1 {g['recall@1']}  recall@5 {g['recall@5']}  "
                  f"recall@10 {g['recall@10']}  mrr@10 {g['mrr@10']}")
        for label, key in (("N1", "at_10k_n1_unrelated"),
                           ("N2", "at_10k_n2_query_vocabulary")):
            print(f"  {label} latency p50 {result[key]['latency_ms']['p50']} ms, "
                  f"max {result[key]['latency_ms']['max']} ms")
        d = result["diagnostic"]
        print(f"  misses@5 {d['misses_at_5']}: ranked 11-100 {d['matched_but_ranked_11_100']}, "
              f"unmatched/beyond 100 {d['unmatched_or_beyond_100']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
