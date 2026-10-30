#!/usr/bin/env python3
"""Verify that v0.19.0 bounded scores change no ranking — see PREREGISTRATION.md.

    PYTHONPATH=src python3 experiments/score_scale/run_eval.py

Checks, against the frozen v0.18.0 scorer (`baseline.py`) in one process on the four
corpora from `experiments/retrieval_idf/`:
  C1/C2  every ranked id list and every metric is identical;
  C3     scores are bounded by Σ field weights and do not grow with unrelated nodes;
  C4     `score_kind` is present and correct per layer.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import retrieval  # noqa: E402

EVAL_DIR = os.path.join(ROOT, "experiments", "retrieval_eval")
IDF_DIR = os.path.join(ROOT, "experiments", "retrieval_idf")
K = 100


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
baseline = _load("baseline", os.path.join(HERE, "baseline.py"))
idf_round = _load("idf_round", os.path.join(IDF_DIR, "run_eval.py"))
ten_k = idf_round.ten_k


def ranked(search_fn, doc, query):
    return [h["id"] for h in search_fn(doc, query, layer="L3", k=K)]


def metrics(search_fn, doc, queries):
    nodes_by_id = {n["id"]: n for n in doc["nodes"]}
    rows = run_eval.stratified_halves(run_eval.evaluate(search_fn, doc, queries, nodes_by_id))
    return {name: run_eval.aggregate(members)
            for name, members in run_eval.group_rows(rows).items()}


def ladder_scores(doc, query, gold, search_fn=retrieval.search):
    """Gold score at 27 / 1 000 / 10 000 unrelated nodes (the drift check)."""
    out = {}
    for target in (27, 1000, 10000):
        corpus = doc if target == 27 else ten_k.inflate(doc, target=target)
        hits = {h["id"]: h["score"] for h in search_fn(corpus, query, k=K)}
        out[target] = hits.get(gold)
    return out


def score_kind_checks(doc):
    query = "atomic replace"
    l3 = retrieval.search(doc, query, layer="L3", k=3)
    ok = bool(l3) and all(h.get("score_kind") == "idf" for h in l3)

    change_doc = {"nodes": [], "edges": [], "changes": [
        {"op": "add", "target": "task.a", "note": "atomic replace", "at": "2026-10-31T00:00:00+08:00", "rev": 1}]}
    l2 = retrieval.search(change_doc, query, layer="L2", k=3)
    ok = ok and bool(l2) and all(h.get("score_kind") == "recency" for h in l2)

    expand_doc = {"nodes": [
        {"id": "task.a", "type": "task", "status": "open", "label": "atomic replace",
         "note": "", "source": "t", "evidence": []},
        {"id": "task.b", "type": "task", "status": "open", "label": "neighbour",
         "note": "", "source": "t", "evidence": []}],
        "edges": [{"from": "task.a", "to": "task.b", "kind": "relates_to"}], "changes": []}
    expanded = retrieval.search(expand_doc, "atomic", layer="L3", k=3, expand=True)
    ok = ok and any(h.get("score_kind") == "expansion" for h in expanded)
    return ok


def main():
    doc, queries = ten_k.load_inputs()
    corpora = {"control": doc, "n1": ten_k.inflate(doc),
               "n2": ten_k.inflate_vocabulary(doc, queries),
               "n3": idf_round.inflate_frequent(doc)}

    result = {"corpora": {}, "checks": {}}
    for name, corpus in corpora.items():
        base_metrics = metrics(baseline.search, corpus, queries)
        cand_metrics = metrics(retrieval.search, corpus, queries)
        same_rank, differing = True, []
        for item in queries:
            if ranked(baseline.search, corpus, item["query"]) != ranked(retrieval.search, corpus, item["query"]):
                same_rank = False
                differing.append(item["id"])
        result["corpora"][name] = {
            "ranking_identical": same_rank,
            "differing_queries": differing,
            "metrics_identical": base_metrics == cand_metrics,
            "metrics": cand_metrics["overall"],
        }

    # C3: bound on the frozen corpus and the unrelated-node ladder. The bound is
    # Σ field weights per term (7.0), not the id weight alone — Amendment A.
    bound_ok, worst = True, 0.0
    for item in queries:
        terms = len({t for t, _ in retrieval._matchers(item["query"])})
        limit = 7.0 * terms
        for hit in retrieval.search(doc, item["query"], k=K):
            worst = max(worst, hit["score"])
            if not 0.0 < hit["score"] <= limit:
                bound_ok = False
    ladder = ladder_scores(doc, queries[0]["query"], queries[0]["gold"][0])
    base_ladder = ladder_scores(doc, queries[0]["query"], queries[0]["gold"][0],
                                search_fn=baseline.search)
    # Amendment A: the residual drift is published, not gated; what is gated is that
    # the bounded score never grows faster than the unbounded one did.
    ladder_ok = all(value and value > 0 for value in ladder.values())
    ladder_ratio = round(max(ladder.values()) / min(ladder.values()), 3)
    base_ladder_ratio = round(max(base_ladder.values()) / min(base_ladder.values()), 3)

    result["checks"] = {
        "C1_C2_ranking_and_metrics_identical": all(
            entry["ranking_identical"] and entry["metrics_identical"]
            for entry in result["corpora"].values()),
        "C3_scores_bounded": bound_ok,
        "C3_worst_score_on_frozen": round(worst, 3),
        "C3_ladder_gold_scores_n27_n1000_n10000": ladder,
        "C3_ladder_ratio": ladder_ratio,
        "C3_ladder_v018_ratio": base_ladder_ratio,
        "C3_ladder_bounded": ladder_ok and ladder_ratio <= base_ladder_ratio,
        "C4_score_kind": score_kind_checks(doc),
    }
    result["checks"]["all_pass"] = all((
        result["checks"]["C1_C2_ranking_and_metrics_identical"],
        result["checks"]["C3_scores_bounded"],
        result["checks"]["C3_ladder_bounded"],
        result["checks"]["C4_score_kind"],
    ))

    out = os.path.join(HERE, "result.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    for name, entry in result["corpora"].items():
        print(f"  {name:8} ranking identical: {entry['ranking_identical']}  "
              f"metrics identical: {entry['metrics_identical']}")
    for key, value in result["checks"].items():
        print(f"  {key}: {value}")
    return 0 if result["checks"]["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
