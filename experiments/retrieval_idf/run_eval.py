#!/usr/bin/env python3
"""IDF-weighted scoring vs the frozen v0.17.0 scorer — see PREREGISTRATION.md.

    PYTHONPATH=src python3 experiments/retrieval_idf/run_eval.py
    PYTHONPATH=src python3 experiments/retrieval_idf/run_eval.py --json

Four corpora (control 27, N1 unrelated 10k, N2 query-vocabulary 10k, N3
frequent-vocabulary 10k) × two scorers (baseline = v0.17.0 constant weights,
shipped = IDF), all in one process with the same frozen queries and gold. Metrics
come from `experiments/retrieval_eval/run_eval.py`, so the numbers stay comparable
with every earlier retrieval measurement.

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
TEN_K_DIR = os.path.join(ROOT, "experiments", "retrieval_10k")
TARGET_NODES = 10000
DEEP_K = 100

# Criteria fixed in PREREGISTRATION.md, repeated here so a run cannot "forget" them.
FROZEN_MIN_R5 = 0.808
FROZEN_MIN_R1 = 0.654
N1_MIN = {"recall@1": 0.654, "recall@5": 0.808, "recall@10": 0.865, "mrr@10": 0.763}
N2_MIN = {"recall@1": 0.481, "recall@5": 0.538}
N3_MIN_GAIN = 0.05
N2_TARGET_R5 = 0.70   # target from the task node, published, not a ship gate


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
bench = _load("bench", os.path.join(ROOT, "benchmarks", "bench.py"))
baseline = _load("baseline", os.path.join(HERE, "baseline.py"))
ten_k = _load("run_10k", os.path.join(TEN_K_DIR, "run_eval.py"))


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def corpus_digest(nodes):
    payload = json.dumps(sorted(nodes, key=lambda n: n["id"]), sort_keys=True,
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def frequent_vocabulary_tokens(doc, top=12, min_len=3):
    """The 12 words this corpus uses most (≥ 3 chars), with their document frequency.

    Derived from the corpus itself, not from a hand-written stopword list: the point
    is that a long-lived graph keeps writing about the same things.
    """
    df = {}
    for node in doc["nodes"]:
        text = " ".join(str(node.get(f) or "") for f in
                        ("id", "label", "note", "source", "owner")).lower()
        for token in set(run_eval.TOKEN.findall(text)):
            if len(token) >= min_len:
                df[token] = df.get(token, 0) + 1
    ranked = sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    return ranked


def inflate_frequent(doc, target=TARGET_NODES):
    """N3: distractors written in the corpus's own most frequent words (seeded)."""
    import random
    words = frequent_vocabulary_tokens(doc)
    vocabulary = [w for w, _ in words]
    weights = [count for _, count in words]
    rng = random.Random(20261031)
    nodes = list(doc["nodes"])
    existing = {n["id"] for n in nodes}
    index = 0
    while len(nodes) < target:
        picked = rng.choices(vocabulary, weights=weights, k=6)
        node = bench.make_node(index, with_evidence=False)
        node["label"] = " ".join(picked[:3])
        node["note"] = "synthetic note " + " ".join(picked[3:])
        node["source"] = "synthetic frequent-vocabulary distractor"
        if node["id"] not in existing:
            nodes.append(node)
            existing.add(node["id"])
        index += 1
    return {"schema": doc.get("schema"), "group": doc.get("group"),
            "nodes": nodes, "edges": [], "changes": []}


def evaluate(search_fn, doc, queries):
    nodes_by_id = {n["id"]: n for n in doc["nodes"]}
    rows = run_eval.stratified_halves(
        run_eval.evaluate(search_fn, doc, queries, nodes_by_id))
    deep, latencies = {}, []
    for item in queries:
        hits = search_fn(doc, item["query"], layer="L3", k=DEEP_K)
        rank = next((i for i, hit in enumerate(hits, start=1)
                     if hit["id"] in item["gold"]), None)
        deep[item["id"]] = rank
        started = time.perf_counter()
        search_fn(doc, item["query"], layer="L3", k=10)
        latencies.append((time.perf_counter() - started) * 1000)
    groups = {name: run_eval.aggregate(members)
              for name, members in run_eval.group_rows(rows).items()}
    return {
        "nodes": len(doc["nodes"]),
        "corpus_sha256": corpus_digest(doc["nodes"]),
        "groups": groups,
        "gold_rank_by_query": deep,
        "misses_at_5": [r["id"] for r in rows if r["recall@5"] == 0.0],
        "latency_ms": {"p50": round(statistics.median(latencies), 2),
                       "max": round(max(latencies), 2)},
    }


def verdicts(result):
    scores = {}
    shipped = {name: entry["shipped"] for name, entry in result["corpora"].items()}
    base = {name: entry["baseline"] for name, entry in result["corpora"].items()}
    c1 = (shipped["control"]["groups"]["overall"]["recall@5"] >= FROZEN_MIN_R5
          and shipped["control"]["groups"]["overall"]["recall@1"] >= FROZEN_MIN_R1)
    scores["C1_frozen_no_regression"] = bool(c1)
    scores["C2_n1_no_regression"] = all(
        shipped["n1"]["groups"]["overall"][k] >= v for k, v in N1_MIN.items())
    scores["C3_n2_no_regression"] = all(
        shipped["n2"]["groups"]["overall"][k] >= v for k, v in N2_MIN.items())
    gain = (shipped["n3"]["groups"]["overall"]["recall@5"]
            - base["n3"]["groups"]["overall"]["recall@5"])
    scores["C4_n3_gain"] = round(gain, 4)
    scores["C4_pass"] = bool(gain >= N3_MIN_GAIN)
    scores["N2_target_met"] = (shipped["n2"]["groups"]["overall"]["recall@5"]
                               >= N2_TARGET_R5)
    scores["ship"] = bool(scores["C1_frozen_no_regression"]
                          and scores["C2_n1_no_regression"]
                          and scores["C3_n2_no_regression"]
                          and scores["C4_pass"])
    return scores


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    doc, queries = ten_k.load_inputs()
    corpora = {
        "control": doc,
        "n1": ten_k.inflate(doc),
        "n2": ten_k.inflate_vocabulary(doc, queries),
        "n3": inflate_frequent(doc),
    }

    result = {
        "inputs": {
            "corpus_sha256": sha256(os.path.join(EVAL_DIR, "corpus.json")),
            "queries_sha256": sha256(os.path.join(EVAL_DIR, "queries.json")),
            "frozen_result_sha256": sha256(os.path.join(EVAL_DIR, "result.json")),
            "scorers": {"baseline": "v0.17.0 constant weights (baseline.py)",
                        "shipped": "v0.18.0 IDF weights (src/amg/retrieval.py)"},
        },
        "n3_vocabulary": [{"token": w, "df": c}
                          for w, c in frequent_vocabulary_tokens(doc)],
        "corpora": {},
        "criteria": {"frozen_min_r5": FROZEN_MIN_R5, "frozen_min_r1": FROZEN_MIN_R1,
                     "n1_min": N1_MIN, "n2_min": N2_MIN,
                     "n3_min_gain": N3_MIN_GAIN, "n2_target_r5": N2_TARGET_R5},
    }
    for name, corpus in corpora.items():
        result["corpora"][name] = {}

    # Interleave per corpus so both scorers see the same machine state.
    for name, corpus in corpora.items():
        result["corpora"][name] = {
            "baseline": evaluate(baseline.search, corpus, queries),
            "shipped": evaluate(retrieval.search, corpus, queries),
            "nodes": len(corpus["nodes"]),
        }
    result["verdicts"] = verdicts(result)

    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print("N3 vocabulary:", ", ".join(f"{w}({c})"
                                      for w, c in frequent_vocabulary_tokens(doc)))
    print(f"{'corpus':8} {'scorer':8} {'r@1':>6} {'r@5':>6} {'r@10':>6} {'mrr':>6} "
          f"{'p50ms':>7}")
    for name in ("control", "n1", "n2", "n3"):
        for scorer in ("baseline", "shipped"):
            entry = result["corpora"][name][scorer]
            g = entry["groups"]["overall"]
            print(f"{name:8} {scorer:8} {g['recall@1']:>6.3f} {g['recall@5']:>6.3f} "
                  f"{g['recall@10']:>6.3f} {g['mrr@10']:>6.3f} "
                  f"{entry['latency_ms']['p50']:>7.1f}")
    v = result["verdicts"]
    print("\ncriteria:")
    print(f"  C1 frozen no regression: {v['C1_frozen_no_regression']}")
    print(f"  C2 N1 no regression:     {v['C2_n1_no_regression']}")
    print(f"  C3 N2 no regression:     {v['C3_n2_no_regression']}")
    print(f"  C4 N3 r@5 gain:          {v['C4_n3_gain']:+.3f} "
          f"({'pass' if v['C4_pass'] else 'FAIL'}, needs +{N3_MIN_GAIN})")
    print(f"  N2 target r@5 >= {N2_TARGET_R5}: {v['N2_target_met']}")
    print(f"  ship v0.18.0: {v['ship']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
