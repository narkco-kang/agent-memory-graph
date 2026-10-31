#!/usr/bin/env python3
"""Is there any lexical signal left for N2? Three rerankers, plus a separability diagnostic.

See PREREGISTRATION.md (written before the run). DECISIONS #48 left the next direction as
content-word weighting / stopword stripping; this asks whether *any* lexical rerank of the shipped
top-100 can move N2 by the +0.05 increment, and — via a per-query AUC — whether a signal exists at
all rather than merely being mistuned.

    PYTHONPATH=src python3 experiments/retrieval_lexical_ceiling/run_lexical.py
    PYTHONPATH=src python3 experiments/retrieval_lexical_ceiling/run_lexical.py --json

Only the top 100 candidates the shipped scorer returns are reordered; a reranker cannot introduce a
hit that search did not find. Writes `result.json` next to this file.
"""
import importlib.util
import json
import math
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
ARM_SIGNALS = ("s1_content", "s2_title", "s3_compact")

# Criteria fixed in PREREGISTRATION.md, repeated so a run cannot "forget" them.
CRITERIA = {"control_min_r5": 0.855, "n2_min_gain_r5": 0.05, "n1_min_r5": 0.855,
            "n3_min_r5": 0.845, "n2_target_r5": 0.70}
SHIPPED = {"control": 0.865, "n1": 0.865, "n2": 0.538, "n3": 0.865}   # from retrieval_idf

# Fixed before the run: standard closed-class English stopwords (>= 3 characters, matching the
# tokenizer's length floor). Not fitted to the 26 queries — see PREREGISTRATION.md.
STOPWORDS = frozenset("""
the and for are but not you all can her was one our out day get has him his how its may new now
old see two way who boy did she use also any are been both come could did does each even ever
every few from had has have here him his how into its just like made make many more most much
must near need next none nor now off once only onto other ought ours over own per put said same
say see shall she should since some such than that them then there these they this those through
too under until upon very want was way well were what when where which while who whom why will
with within without would yet your
""".split())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


idf = _load("idf_eval", os.path.join(IDF_DIR, "run_eval.py"))
run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
ten_k = _load("run_10k", os.path.join(ROOT, "experiments", "retrieval_10k", "run_eval.py"))


def content_tokens(query):
    return run_eval.tokens(query) - STOPWORDS


def signals(query_tokens, content, node):
    """The three candidate signals, all in [0, 1] so alpha tuning cannot be scale-dependent."""
    node_text = run_eval.node_text(node)
    node_tokens = run_eval.tokens(node_text)
    title_tokens = run_eval.tokens(node.get("label") or "")
    content_cov = (len(content & node_tokens) / len(content)) if content else 1.0
    full_cov = (len(query_tokens & node_tokens) / len(query_tokens)) if query_tokens else 1.0
    title_cov = (len(query_tokens & title_tokens) / len(query_tokens)) if query_tokens else 1.0
    compact = full_cov / (1.0 + math.log1p(len(node_tokens)))
    return {"s1_content": content_cov, "s2_title": title_cov, "s3_compact": compact}


def rerank(hits, features, alpha):
    """Order by score x signal**alpha, breaking ties by the scorer's own order.

    The tie-break is the shipped position on purpose: breaking ties by id moved recall on a 10k
    corpus full of equal scores and made alpha = 0 disagree with the scorer it reproduces.
    """
    keyed = []
    for position, hit in enumerate(hits):
        value = features[hit["id"]]
        keyed.append((hit["score"] * (value ** alpha), position, hit["id"]))
    keyed.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in keyed]


def auc(values, labels):
    """Rank-sum AUC of `values` separating label 1 from label 0. None when a group is empty."""
    positives = sum(1 for flag in labels if flag)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        stop = index
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
            stop += 1
        average = (index + stop) / 2.0 + 1.0          # average rank, 1-based
        for position in range(index, stop + 1):
            ranks[order[position]] = average
        index = stop + 1
    positive_rank_sum = sum(rank for rank, label in zip(ranks, labels) if label)
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


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
    content = {item["id"]: content_tokens(item["query"]) for item in queries}
    buckets = {item["id"]: ("paraphrase"
                            if run_eval.overlap(item["query"],
                                                [nodes_by_id[g] for g in item["gold"]
                                                 if g in nodes_by_id]) < run_eval.PARAPHRASE_OVERLAP
                            else "keyword")
               for item in queries}
    gold = {item["id"]: [g for g in item["gold"] if g in nodes_by_id] for item in queries}

    hits_by_query = {}
    orderings = {(signal, alpha): {} for signal in ARM_SIGNALS for alpha in ALPHAS}
    auc_by_signal = {signal: [] for signal in ARM_SIGNALS}
    gold_in_top_k = 0
    latencies = []
    for item in queries:
        started = time.perf_counter()
        hits = retrieval.search(doc, item["query"], layer="L3", k=DEEP_K)
        latencies.append((time.perf_counter() - started) * 1000)
        hits_by_query[item["id"]] = [hit["id"] for hit in hits]
        hit_gold = set(gold[item["id"]])
        if any(hit["id"] in hit_gold for hit in hits):
            gold_in_top_k += 1
        features = {signal: {} for signal in ARM_SIGNALS}
        for hit in hits:
            values = signals(query_tokens[item["id"]], content[item["id"]],
                             nodes_by_id.get(hit["id"], {}))
            for signal in ARM_SIGNALS:
                features[signal][hit["id"]] = values[signal]
        labels = [1 if hit["id"] in hit_gold else 0 for hit in hits]
        for signal in ARM_SIGNALS:
            value = auc([features[signal][hit["id"]] for hit in hits], labels)
            if value is not None:
                auc_by_signal[signal].append(value)
        for signal in ARM_SIGNALS:
            for alpha in ALPHAS:
                # alpha = 0 must be signal-independent: every arm reproduces the shipped order.
                orderings[(signal, alpha)][item["id"]] = (
                    list(hits_by_query[item["id"]]) if alpha == 0.0
                    else rerank(hits, features[signal], alpha))

    arms = {}
    for alpha in ALPHAS:
        arms[f"{alpha:g}"] = score_rows(queries, orderings[(ARM_SIGNALS[0], alpha)], gold, buckets)
    for signal in ARM_SIGNALS:
        for alpha in ALPHAS:
            if alpha == 0.0:
                continue
            arms[f"{signal}@{alpha:g}"] = score_rows(queries, orderings[(signal, alpha)],
                                                     gold, buckets)
    arms["shipped"] = score_rows(queries, hits_by_query, gold, buckets)
    control = arms["0"]
    shipped = arms["shipped"]
    reproduces = all(abs(control[metric] - shipped[metric]) <= 1e-3
                     for metric in ("recall@1", "recall@5", "recall@10", "mrr@10"))
    return {"nodes": len(doc["nodes"]), "arms": arms, "alpha0_metrics_equal_shipped": reproduces,
            "diagnostics": {"mean_auc": {signal: round(statistics.mean(values), 4)
                                         for signal, values in auc_by_signal.items() if values},
                            "queries_with_auc": {signal: len(values)
                                                 for signal, values in auc_by_signal.items()},
                            "candidate_ceiling": round(gold_in_top_k / len(queries), 4)},
            "latency_ms": {"p50": round(statistics.median(latencies), 2),
                           "max": round(max(latencies), 2)}}


def verdicts(result):
    def r5(corpus, arm):
        return result["corpora"][corpus]["arms"][arm]["recall@5"]

    best = {"arm": None, "alpha": None, "gain": -1.0}
    for alpha in ALPHAS:
        if alpha == 0.0:
            continue
        for signal in ARM_SIGNALS:
            arm = f"{signal}@{alpha:g}"
            gain = r5("n2", arm) - SHIPPED["n2"]
            if gain > best["gain"]:
                best = {"arm": signal, "alpha": f"{alpha:g}", "gain": gain}
    handpicked = f"{best['arm']}@{best['alpha']}"
    gates = {"C1_control_no_regression": r5("control", handpicked) >= CRITERIA["control_min_r5"],
             "C2_n2_gain_at_least_0.05": best["gain"] >= CRITERIA["n2_min_gain_r5"],
             "C3_n1_unchanged": r5("n1", handpicked) >= CRITERIA["n1_min_r5"],
             "C4_n3_not_harmed": r5("n3", handpicked) >= CRITERIA["n3_min_r5"]}
    return {"selected": {"arm": best["arm"], "alpha": best["alpha"]},
            **gates,
            "N2_target_met": r5("n2", handpicked) >= CRITERIA["n2_target_r5"],
            "n2_gain": round(best["gain"], 3),
            "all_arms_fail_C2": all(r5("n2", f"{s}@{a:g}") - SHIPPED["n2"] < 0.05
                                    for s in ARM_SIGNALS for a in ALPHAS if a),
            "max_mean_auc": max(result["corpora"]["n2"]["diagnostics"]["mean_auc"].values()),
            "candidate_ceiling": result["corpora"]["n2"]["diagnostics"]["candidate_ceiling"],
            "shipped_r5": SHIPPED,
            "criteria": CRITERIA,
            "ship": bool(all(gates.values()))}


def main(argv):
    as_json = "--json" in argv
    doc, queries = ten_k.load_inputs()
    corpora = {"control": doc, "n1": ten_k.inflate(doc),
               "n2": ten_k.inflate_vocabulary(doc, queries),
               "n3": idf.inflate_frequent(doc)}
    result = {"inputs": {"corpora": {name: len(corpus["nodes"]) for name, corpus in corpora.items()},
                         "deep_k": DEEP_K, "alphas": list(ALPHAS),
                         "signals": list(ARM_SIGNALS),
                         "stopwords": len(STOPWORDS),
                         "shipped_scorer": "v0.19.0+ IDF weights, src/amg/retrieval.py"},
              "criteria": CRITERIA, "corpora": {}}
    for name, corpus in corpora.items():
        result["corpora"][name] = evaluate_corpus(corpus, queries)
        if not as_json:
            diag = result["corpora"][name]["diagnostics"]
            print(f"{name:8s} n={result['corpora'][name]['nodes']:5d}  "
                  + "  ".join(f"{s}@{a:g}:r@5={result['corpora'][name]['arms'][f'{s}@{a:g}']['recall@5']:.3f}"
                              for s in ARM_SIGNALS for a in (0.5, 1, 2))
                  + f"   AUC={diag['mean_auc']} ceiling={diag['candidate_ceiling']:.2f}")
    result["verdicts"] = verdicts(result)
    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
    if as_json:
        print(json.dumps(result["verdicts"], ensure_ascii=False))
    else:
        v = result["verdicts"]
        print(f"best {v['selected']['arm']}@{v['selected']['alpha']} (N2 {v['n2_gain']:+.3f}); "
              f"C1={v['C1_control_no_regression']} C2={v['C2_n2_gain_at_least_0.05']} "
              f"C3={v['C3_n1_unchanged']} C4={v['C4_n3_not_harmed']}; "
              f"all fail C2={v['all_arms_fail_C2']}; max AUC={v['max_mean_auc']:.3f}; "
              f"ceiling={v['candidate_ceiling']:.2f}; ship={v['ship']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
