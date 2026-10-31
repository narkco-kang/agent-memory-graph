#!/usr/bin/env python3
"""Is N2 the noise a real graph produces? A calibrated noise corpus, measured.

See PREREGISTRATION.md (written before this run; it discloses the two exploratory scans taken
earlier). N2 builds each distractor from six tokens of the queries' own vocabulary, which the lexical
rounds (#49) and the semantic round (#50) both failed to beat. This measures whether that construction
overstates the noise a real graph produces, by building `N2-cal` — same generator, but the number of
query-vocabulary tokens per distractor is drawn from the distribution actually observed on the real
`control` corpus — and running the shipped scorer on it.

    PYTHONPATH=src python3 experiments/retrieval_noise_representativeness/run_calibrated.py

Writes `result.json` next to this file. Nothing in `src/amg/` changes.
"""
import importlib.util
import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import retrieval  # noqa: E402

IDF_DIR = os.path.join(ROOT, "experiments", "retrieval_idf")
EVAL_DIR = os.path.join(ROOT, "experiments", "retrieval_eval")
TEN_K_DIR = os.path.join(ROOT, "experiments", "retrieval_10k")
SEED = 20261031
TARGET_NODES = 10000
DEEP_K = 100
SHIPPED = {"control": 0.865, "n1": 0.865, "n2": 0.538, "n3": 0.865}
CRITERIA = {"n2cal_min_r5": 0.75, "calibration_tolerance": 0.10}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


idf = _load("idf_eval", os.path.join(IDF_DIR, "run_eval.py"))
run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
ten_k = _load("run_10k", os.path.join(TEN_K_DIR, "run_eval.py"))
bench = _load("bench", os.path.join(ROOT, "benchmarks", "bench.py"))


def coverage(query_tokens, node):
    tokens = run_eval.tokens(run_eval.node_text(node))
    return len(query_tokens & tokens) / len(query_tokens) if query_tokens else 0.0


def competing_coverage(corpus, queries, limit=DEEP_K):
    """Coverage of the top-`limit` candidates that are not gold — the noise that actually competes."""
    nodes_by_id = {n["id"]: n for n in corpus["nodes"]}
    values = []
    for item in queries:
        query_tokens = run_eval.tokens(item["query"])
        for hit in retrieval.search(corpus, item["query"], layer="L3", k=limit):
            if hit["id"] in item["gold"]:
                continue
            node = nodes_by_id.get(hit["id"])
            if node is not None:
                values.append(coverage(query_tokens, node))
    return values


def token_counts(values, query_length):
    """Turn fractional coverages back into integer token counts for the pinned query length."""
    counts = [max(0, min(query_length, round(value * query_length))) for value in values]
    return counts


def build_calibrated_mix(doc, queries, mix, filler_pool):
    """Same generator, but the query-token count per node comes from an explicit mix.

    `mix` is a list of (count, weight) pairs; the count is how many tokens of the node come from the
    queries' own vocabulary. N2 is the special case [(6, 1.0)].
    """
    query_pool = sorted({token for item in queries
                         for token in run_eval.TOKEN.findall(item["query"].lower())
                         if len(token) >= 3})
    counts = [count for count, weight in mix for _ in range(max(1, int(round(weight * 1000))))]
    rng = random.Random(SEED)
    nodes = list(doc["nodes"])
    existing = {n["id"] for n in nodes}
    index = 0
    while len(nodes) < TARGET_NODES:
        take = counts[rng.randrange(len(counts))]
        words = [rng.choice(query_pool) for _ in range(take)]
        words += [rng.choice(filler_pool) for _ in range(max(0, 6 - take))]
        node = bench.make_node(index, with_evidence=False)
        node["label"] = " ".join(words[:3])
        node["note"] = "synthetic calibrated-note " + " ".join(words[3:])
        node["source"] = "synthetic calibrated distractor"
        if node["id"] not in existing:
            nodes.append(node)
            existing.add(node["id"])
        index += 1
    return {"schema": doc.get("schema"), "group": doc.get("group"),
            "nodes": nodes, "edges": [], "changes": []}


def build_calibrated(doc, queries, counts, filler_pool):
    """Same shape as N2's generator, but the query-vocabulary token count is drawn from `counts`."""
    query_pool = sorted({token for item in queries
                         for token in run_eval.TOKEN.findall(item["query"].lower())
                         if len(token) >= 3})
    rng = random.Random(SEED)
    nodes = list(doc["nodes"])
    existing = {n["id"] for n in nodes}
    index = 0
    while len(nodes) < TARGET_NODES:
        take = counts[rng.randrange(len(counts))]
        words = [rng.choice(query_pool) for _ in range(take)]
        words += [rng.choice(filler_pool) for _ in range(max(0, 6 - take))]
        node = bench.make_node(index, with_evidence=False)
        node["label"] = " ".join(words[:3])
        node["note"] = "synthetic calibrated-note " + " ".join(words[3:])
        node["source"] = "synthetic calibrated distractor"
        if node["id"] not in existing:
            nodes.append(node)
            existing.add(node["id"])
        index += 1
    return {"schema": doc.get("schema"), "group": doc.get("group"),
            "nodes": nodes, "edges": [], "changes": []}


def evaluate(corpus, queries):
    nodes_by_id = {n["id"]: n for n in corpus["nodes"]}
    buckets = {item["id"]: ("paraphrase"
                            if run_eval.overlap(item["query"],
                                                [nodes_by_id[g] for g in item["gold"]
                                                 if g in nodes_by_id]) < run_eval.PARAPHRASE_OVERLAP
                            else "keyword")
               for item in queries}
    rows = []
    for item in queries:
        gold = [g for g in item["gold"] if g in nodes_by_id]
        hits = retrieval.search(corpus, item["query"], layer="L3", k=max(run_eval.K_VALUES))
        ranked = [hit["id"] for hit in hits]
        row = {"id": item["id"], "split": item["split"], "bucket": buckets[item["id"]],
               "reciprocal_rank": 0.0}
        for k in run_eval.K_VALUES:
            row[f"recall@{k}"] = round(len(set(ranked[:k]) & set(gold)) / len(gold), 4) if gold else 0.0
        for position, node_id in enumerate(ranked, start=1):
            if node_id in gold:
                row["reciprocal_rank"] = 1.0 / position
                break
        rows.append(row)
    return run_eval.aggregate(run_eval.stratified_halves(rows))


def main(argv):
    doc, queries = ten_k.load_inputs()
    lengths = [len(run_eval.tokens(item["query"])) for item in queries]
    typical = int(statistics.median(lengths))
    filler_pool = sorted({token for node in doc["nodes"]
                          for token in run_eval.TOKEN.findall(run_eval.node_text(node).lower())
                          if len(token) >= 3})

    control = doc
    n2 = ten_k.inflate_vocabulary(doc, queries)
    control_values = competing_coverage(control, queries)
    n2_values = competing_coverage(n2, queries)
    counts = token_counts(control_values, typical)
    n2cal = build_calibrated(doc, queries, counts, filler_pool)
    n2cal_values = competing_coverage(n2cal, queries)

    def share(values, threshold=0.25):
        return round(sum(1 for value in values if value >= threshold) / len(values), 4)

    result = {"inputs": {"seed": SEED, "typical_query_tokens": typical,
                         "distractor_token_counts": {str(count): counts.count(count)
                                                     for count in sorted(set(counts))},
                         "filler_pool": len(filler_pool)},
              "criteria": CRITERIA,
              "coverage": {"control": {"n": len(control_values),
                                       "mean": round(statistics.mean(control_values), 4),
                                       "median": round(statistics.median(control_values), 4),
                                       "share_ge_0.25": share(control_values)},
                           "n2": {"n": len(n2_values),
                                  "mean": round(statistics.mean(n2_values), 4),
                                  "median": round(statistics.median(n2_values), 4),
                                  "share_ge_0.25": share(n2_values)},
                           "n2cal": {"n": len(n2cal_values),
                                     "mean": round(statistics.mean(n2cal_values), 4),
                                     "median": round(statistics.median(n2cal_values), 4),
                                     "share_ge_0.25": share(n2cal_values)}},
              "arms": {"control": evaluate(control, queries),
                       "n2": evaluate(n2, queries),
                       "n2cal": evaluate(n2cal, queries),
                       "n1": evaluate(ten_k.inflate(doc), queries),
                       "n3": evaluate(idf.inflate_frequent(doc), queries)}}
    calibrated = abs(result["coverage"]["n2cal"]["share_ge_0.25"]
                     - result["coverage"]["control"]["share_ge_0.25"]) <= CRITERIA["calibration_tolerance"]
    ordering = (result["arms"]["n2"]["recall@5"] <= result["arms"]["n2cal"]["recall@5"]
                <= result["arms"]["control"]["recall@5"])
    result["verdicts"] = {
        "Q1_n2cal_r5_at_least_0.75": result["arms"]["n2cal"]["recall@5"] >= CRITERIA["n2cal_min_r5"],
        "Q2_calibration_within_tolerance": bool(calibrated),
        "Q3_ordering_preserved": bool(ordering),
        "n2_r5": result["arms"]["n2"]["recall@5"],
        "n2cal_r5": result["arms"]["n2cal"]["recall@5"],
        "control_r5": result["arms"]["control"]["recall@5"],
        "n1_r5": result["arms"]["n1"]["recall@5"],
        "n3_r5": result["arms"]["n3"]["recall@5"],
        "gap_closed_fraction": round((result["arms"]["n2cal"]["recall@5"] - SHIPPED["n2"])
                                     / (SHIPPED["control"] - SHIPPED["n2"]), 4),
        "shipped_r5": SHIPPED, "criteria": CRITERIA,
    }
    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
    for name in ("control", "n2", "n2cal", "n1", "n3"):
        print(f"{name:8s} r@5={result['arms'][name]['recall@5']:.3f} "
              f"r@1={result['arms'][name]['recall@1']:.3f} "
              f"mrr={result['arms'][name]['mrr@10']:.3f}")
    for name in ("control", "n2", "n2cal"):
        row = result["coverage"][name]
        print(f"{name:8s} competing coverage mean={row['mean']:.3f} median={row['median']:.3f} "
              f"share>=0.25={row['share_ge_0.25']:.3f} (n={row['n']})")
    print(json.dumps({k: v for k, v in result["verdicts"].items() if k.startswith("Q")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
