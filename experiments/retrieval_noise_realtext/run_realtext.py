#!/usr/bin/env python3
"""A noise corpus whose distractors are real prose, not token soup.

See PREREGISTRATION.md (written before the run) and DECISIONS #51, which rejected the previous
calibration attempt because the top-100 is selected by the quantity being calibrated.

Distractor text = a seeded 8-word window of a real paragraph from this repository's own
documentation. Nothing is drawn from a vocabulary list, so function words and co-occurrence are the
documentation's own. The calibration check (competing share) is reported before the recall number.

    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/run_realtext.py

Writes `result.json` next to this file. `src/amg/` is untouched.
"""
import importlib.util
import json
import os
import pathlib
import random
import re
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
WINDOW = 8
SHIPPED = {"control": 0.865, "n1": 0.865, "n2": 0.538, "n3": 0.865}
N2_COMPETING_SHARE = 0.918


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


idf = _load("idf_eval", os.path.join(IDF_DIR, "run_eval.py"))
run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
ten_k = _load("run_10k", os.path.join(TEN_K_DIR, "run_eval.py"))
bench = _load("bench", os.path.join(ROOT, "benchmarks", "bench.py"))


def prose_pool():
    """Every paragraph of six or more words in the repository's own shipped prose."""
    paths = [pathlib.Path(ROOT, "README.md")]
    paths += sorted(pathlib.Path(ROOT, "docs").glob("*.md"))
    paths += sorted(pathlib.Path(ROOT, "docs", "decisions").glob("*.md"))
    paragraphs = []
    for path in paths:
        for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            words = " ".join(block.split()).split()
            if len(words) >= 6:
                paragraphs.append(words)
    return paragraphs


def build_realtext(doc, paragraphs):
    rng = random.Random(SEED)
    nodes = list(doc["nodes"])
    existing = {n["id"] for n in nodes}
    index = 0
    while len(nodes) < TARGET_NODES:
        words = paragraphs[rng.randrange(len(paragraphs))]
        start = rng.randrange(max(1, len(words) - WINDOW + 1))
        window = words[start:start + WINDOW]
        node = bench.make_node(index, with_evidence=False)
        node["label"] = " ".join(window[:3])
        node["note"] = " ".join(window[3:])
        node["source"] = "synthetic real-prose distractor"
        if node["id"] not in existing:
            nodes.append(node)
            existing.add(node["id"])
        index += 1
    return {"schema": doc.get("schema"), "group": doc.get("group"),
            "nodes": nodes, "edges": [], "changes": []}


def competing_share(corpus, queries):
    nodes_by_id = {n["id"]: n for n in corpus["nodes"]}
    values = []
    for item in queries:
        query_tokens = run_eval.tokens(item["query"])
        for hit in retrieval.search(corpus, item["query"], layer="L3", k=DEEP_K):
            if hit["id"] in item["gold"]:
                continue
            node = nodes_by_id.get(hit["id"])
            if node is not None:
                tokens = run_eval.tokens(run_eval.node_text(node))
                values.append(len(query_tokens & tokens) / len(query_tokens) if query_tokens else 0.0)
    share = round(sum(1 for value in values if value >= 0.25) / len(values), 4)
    return share, {"pairs": len(values), "mean": round(sum(values) / len(values), 4),
                   "median": round(sorted(values)[len(values) // 2], 4), "share_ge_0.25": share}


def evaluate(corpus, queries):
    nodes_by_id = {n["id"]: n for n in corpus["nodes"]}
    buckets = {item["id"]: ("paraphrase"
                            if run_eval.overlap(item["query"],
                                                [nodes_by_id[g] for g in item["gold"]
                                                 if g in nodes_by_id]) < run_eval.PARAPHRASE_OVERLAP
                            else "keyword")
               for item in queries}
    rows = []
    ceiling = 0
    for item in queries:
        gold = [g for g in item["gold"] if g in nodes_by_id]
        hits = retrieval.search(corpus, item["query"], layer="L3", k=DEEP_K)
        ranked = [hit["id"] for hit in hits]
        if set(ranked) & set(gold):
            ceiling += 1
        row = {"id": item["id"], "split": item["split"], "bucket": buckets[item["id"]],
               "reciprocal_rank": 0.0}
        for k in run_eval.K_VALUES:
            row[f"recall@{k}"] = round(len(set(ranked[:k]) & set(gold)) / len(gold), 4) if gold else 0.0
        for position, node_id in enumerate(ranked, start=1):
            if node_id in gold:
                row["reciprocal_rank"] = 1.0 / position
                break
        rows.append(row)
    result = run_eval.aggregate(run_eval.stratified_halves(rows))
    result["ceiling"] = round(ceiling / len(queries), 4)
    return result


def main(argv):
    doc, queries = ten_k.load_inputs()
    paragraphs = prose_pool()
    realtext = build_realtext(doc, paragraphs)
    share, coverage = competing_share(realtext, queries)
    corpora = {"control": doc, "n1": ten_k.inflate(doc), "n2": ten_k.inflate_vocabulary(doc, queries),
               "n3": idf.inflate_frequent(doc), "realtext": realtext}
    result = {"inputs": {"seed": SEED, "window_words": WINDOW, "paragraphs": len(paragraphs),
                         "nodes": len(realtext["nodes"]), "deep_k": DEEP_K},
              "coverage": {"realtext": coverage, "n2_reference_share_ge_0.25": N2_COMPETING_SHARE},
              "arms": {name: evaluate(corpus, queries) for name, corpus in corpora.items()}}
    verdicts = {
        "Q2_calibration_below_n2": share < N2_COMPETING_SHARE,
        "Q1_recall_at_least_0.75": result["arms"]["realtext"]["recall@5"] >= 0.75,
        "Q3_ordering_n2_lt_realtext_lt_control": (result["arms"]["n2"]["recall@5"]
                                                  < result["arms"]["realtext"]["recall@5"]
                                                  < result["arms"]["control"]["recall@5"]),
        "Q4_target_stays_attached_to_n2_unmet": True,
        "n2_r5": result["arms"]["n2"]["recall@5"],
        "realtext_r5": result["arms"]["realtext"]["recall@5"],
        "control_r5": result["arms"]["control"]["recall@5"],
        "realtext_share_ge_0.25": share,
        "shipped_r5": SHIPPED,
    }
    result["verdicts"] = verdicts
    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print("Q2' competing share >= 0.25 on real-text corpus:", share, f"(N2 reference {N2_COMPETING_SHARE})")
    for name in ("control", "n1", "n2", "n3", "realtext"):
        block = result["arms"][name]
        print(f"{name:9s} r@5={block['recall@5']:.3f} r@1={block['recall@1']:.3f} "
              f"r@10={block['recall@10']:.3f} mrr={block['mrr@10']:.3f} ceiling={block['ceiling']:.3f}")
    print(json.dumps({k: v for k, v in verdicts.items() if k.startswith("Q")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
