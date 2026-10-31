#!/usr/bin/env python3
"""Rerank by query coverage — a signal outside the document-frequency family.

See PREREGISTRATION.md (written before the run). DECISIONS #28 shipped IDF and left
query-vocabulary noise (N2) at recall@5 0.538 against a 0.70 target, because N2 draws its
distractor tokens uniformly from the query vocabulary: every term has the same `df`, so IDF has
nothing to weigh. Coverage — how much of the query a hit actually contains — is not a frequency
statistic, so it is the candidate tested here.

    PYTHONPATH=src python3 experiments/retrieval_beyond_df/run_rerank.py
    PYTHONPATH=src python3 experiments/retrieval_beyond_df/run_rerank.py --json

Only the top 100 candidates the shipped scorer returns are reordered; the reranker cannot
introduce a hit that search did not find. Writes `result.json` next to this file.
"""
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

IDF_DIR = os.path.join(ROOT, "experiments", "retrieval_idf")
EVAL_DIR = os.path.join(ROOT, "experiments", "retrieval_eval")
DEEP_K = 100
ALPHAS = (0.0, 0.5, 1.0, 2.0)   # 0.0 is the shipped scorer: the control arm

# Criteria fixed in PREREGISTRATION.md, repeated so a run cannot "forget" them.
CRITERIA = {"control_min_r5": 0.855, "n2_min_gain_r5": 0.05, "n1_min_r5": 0.855,
            "n3_min_r5": 0.845, "n2_target_r5": 0.70}
SHIPPED = {"control": 0.865, "n1": 0.865, "n2": 0.538, "n3": 0.865}   # from retrieval_idf


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


idf = _load("idf_eval", os.path.join(IDF_DIR, "run_eval.py"))
run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
ten_k = _load("run_10k", os.path.join(ROOT, "experiments", "retrieval_10k", "run_eval.py"))


def coverage(query_tokens, node):
    if not query_tokens:
        return 0.0
    return len(query_tokens & run_eval.tokens(run_eval.node_text(node))) / len(query_tokens)


def ranked_ids(scored):
    return [hit["id"] for hit in scored]


def rerank(hits, query_tokens, nodes_by_id, alpha):
    """Order by score x coverage**alpha, breaking ties by the scorer's own order.

    The tie-break is the shipped position on purpose: the first version of this harness broke
    ties by id, which moved recall on a 10k corpus full of equal scores (n1 r@5 0.865 -> 0.827)
    and made alpha = 0 disagree with the scorer it is supposed to reproduce. A reranker that
    cannot reproduce the baseline at alpha = 0 is measuring its own tie-break, not the signal.
    """
    keyed = []
    for position, hit in enumerate(hits):
        node = nodes_by_id.get(hit["id"], {})
        cov = coverage(query_tokens, node)
        keyed.append((hit["score"] * (cov ** alpha), position, hit["id"], cov))
    keyed.sort(key=lambda row: (-row[0], row[1]))
    return keyed


def score_rows(queries, ordering_by_query, gold_by_query, buckets):
    rows = []
    for item in queries:
        ranked = ordering_by_query[item["id"]]
        gold = gold_by_query[item["id"]]
        row = {"id": item["id"], "split": item["split"], "bucket": buckets[item["id"]],
               "reciprocal_rank": 0.0, "ranked": ranked[:DEEP_K]}
        for k in run_eval.K_VALUES:
            top = set(ranked[:k])
            row[f"recall@{k}"] = round(len(top & set(gold)) / len(gold), 4) if gold else 0.0
        for position, node_id in enumerate(ranked, start=1):
            if node_id in gold:
                row["reciprocal_rank"] = 1.0 / position
                break
        rows.append(row)
    return run_eval.aggregate(run_eval.stratified_halves(rows))


def evaluate_corpus(doc, queries):
    nodes_by_id = {n["id"]: n for n in doc["nodes"]}
    query_tokens = {item["id"]: run_eval.tokens(item["query"]) for item in queries}
    buckets = {item["id"]: ("paraphrase"
                            if run_eval.overlap(item["query"],
                                                [nodes_by_id[g] for g in item["gold"]
                                                 if g in nodes_by_id]) < run_eval.PARAPHRASE_OVERLAP
                            else "keyword")
               for item in queries}
    gold = {item["id"]: [g for g in item["gold"] if g in nodes_by_id] for item in queries}

    hits_by_query, orderings = {}, {alpha: {} for alpha in ALPHAS}
    latencies = []
    for item in queries:
        started = time.perf_counter()
        hits = retrieval.search(doc, item["query"], layer="L3", k=DEEP_K)
        latencies.append((time.perf_counter() - started) * 1000)
        # Recompute coverage lazily: one pass per query, reused by every alpha.
        keyed_cache = {alpha: rerank(hits, query_tokens[item["id"]], nodes_by_id, alpha)
                       for alpha in ALPHAS}
        for alpha in ALPHAS:
            orderings[alpha][item["id"]] = [row[2] for row in keyed_cache[alpha]]
        hits_by_query[item["id"]] = ranked_ids(hits)

    arms = {}
    for alpha in ALPHAS:
        arms[f"{alpha:g}"] = score_rows(queries, orderings[alpha], gold, buckets)
    arms["shipped"] = score_rows(queries, hits_by_query, gold, buckets)
    # alpha = 0 must reproduce the shipped *metrics*. Order equality is too strict: the
    # returned score is rounded for output, so hits that differ only below the rounding can
    # swap inside a tie without changing any metric — and metric equality is what the harness
    # artefact (tie-break by id) actually broke.
    control = arms["0"]
    shipped = arms["shipped"]
    reproduces = all(abs(control[metric] - shipped[metric]) <= 1e-3
                     for metric in ("recall@1", "recall@5", "recall@10", "mrr@10"))
    return {"nodes": len(doc["nodes"]), "arms": arms, "alpha0_metrics_equal_shipped": reproduces,
            "latency_ms": {"p50": round(statistics.median(latencies), 2),
                           "max": round(max(latencies), 2)}}


def verdicts(result):
    def r5(corpus, arm):
        return result["corpora"][corpus]["arms"][arm]["recall@5"]

    best_alpha, best_gain = None, -1.0
    for alpha in ALPHAS:
        if alpha == 0.0:
            continue
        gain = r5("n2", f"{alpha:g}") - SHIPPED["n2"]
        if gain > best_gain:
            best_alpha, best_gain = f"{alpha:g}", gain
    chosen = best_alpha
    return {
        "chosen_alpha": chosen,
        "chosen_on_corpus": "n2 (selection uses the target corpus only)",
        "C1_control_no_regression": r5("control", chosen) >= CRITERIA["control_min_r5"],
        "C2_n2_gain_at_least_0.05": best_gain >= CRITERIA["n2_min_gain_r5"],
        "C3_n1_unchanged": r5("n1", chosen) >= CRITERIA["n1_min_r5"],
        "C4_n3_not_harmed": r5("n3", chosen) >= CRITERIA["n3_min_r5"],
        "N2_target_met": r5("n2", chosen) >= CRITERIA["n2_target_r5"],
        "n2_gain": round(best_gain, 3),
        "shipped_r5": SHIPPED,
        "criteria": CRITERIA,
        "ship": bool(r5("control", chosen) >= CRITERIA["control_min_r5"]
                     and best_gain >= CRITERIA["n2_min_gain_r5"]
                     and r5("n1", chosen) >= CRITERIA["n1_min_r5"]
                     and r5("n3", chosen) >= CRITERIA["n3_min_r5"]),
    }


def main(argv):
    as_json = "--json" in argv
    doc, queries = ten_k.load_inputs()
    corpora = {"control": doc, "n1": ten_k.inflate(doc),
               "n2": ten_k.inflate_vocabulary(doc, queries),
               "n3": idf.inflate_frequent(doc)}
    result = {"inputs": {"corpora": {name: len(corpus["nodes"]) for name, corpus in corpora.items()},
                         "deep_k": DEEP_K, "alphas": list(ALPHAS),
                         "shipped_scorer": "v0.19.0+ IDF weights, src/amg/retrieval.py"},
              "criteria": CRITERIA, "corpora": {}}
    for name, corpus in corpora.items():
        result["corpora"][name] = evaluate_corpus(corpus, queries)
        if not as_json:
            row = result["corpora"][name]["arms"]
            print(f"{name:8s} n={result['corpora'][name]['nodes']:5d}  "
                  + "  ".join(f"a{a}:r@5={row[a]['recall@5']:.3f}" for a in
                              ("shipped", "0", "0.5", "1", "2")))
    result["verdicts"] = verdicts(result)
    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
    if as_json:
        print(json.dumps(result["verdicts"], ensure_ascii=False))
    else:
        v = result["verdicts"]
        print(f"chosen alpha={v['chosen_alpha']} (N2 gain {v['n2_gain']:+.3f}); "
              f"C1={v['C1_control_no_regression']} C2={v['C2_n2_gain_at_least_0.05']} "
              f"C3={v['C3_n1_unchanged']} C4={v['C4_n3_not_harmed']}; "
              f"N2 target 0.70 met={v['N2_target_met']}; ship={v['ship']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
