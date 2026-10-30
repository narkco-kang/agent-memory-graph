#!/usr/bin/env python3
"""Retrieval evaluation harness. Compares retrievers on a frozen corpus.

The lexical baseline is the shipped `amg.retrieval.search`. Any candidate is
expected to expose the same signature (`search(doc, query, layer, k, ...) -> list
of dicts with an "id" key`), so this file does not import the candidate.

Usage:
    PYTHONPATH=src python3 experiments/retrieval_eval/run_eval.py            # baseline only
    PYTHONPATH=src python3 experiments/retrieval_eval/run_eval.py --json     # machine-readable

Bucketing is measured, not intended: see PREREGISTRATION.md.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import retrieval  # noqa: E402

K_VALUES = (1, 5, 10)
PARAPHRASE_OVERLAP = 0.34   # below this the query shares too few words to match literally
TOKEN = re.compile(r"[a-z0-9]+")
FIELD_TEXT = ("id", "label", "note", "source", "owner", "type")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def tokens(text):
    return {t for t in TOKEN.findall(str(text).lower()) if len(t) >= 3}


def node_text(node):
    return " ".join(str(node.get(f) or "") for f in FIELD_TEXT)


def overlap(query, gold_nodes):
    q = tokens(query)
    if not q:
        return 0.0
    gold = set()
    for node in gold_nodes:
        gold |= tokens(node_text(node))
    return len(q & gold) / len(q)


def evaluate(search_fn, doc, queries, nodes_by_id):
    rows = []
    for item in queries:
        gold = [g for g in item["gold"] if g in nodes_by_id]
        hits = search_fn(doc, item["query"], layer="L3", k=max(K_VALUES))
        ranked = [h["id"] for h in hits]
        row = {
            "id": item["id"], "split": item["split"], "query": item["query"],
            "gold": gold,
            "overlap": round(overlap(item["query"], [nodes_by_id[g] for g in gold]), 3),
            "ranked": ranked[:max(K_VALUES)],
            "reciprocal_rank": 0.0,
        }
        row["bucket"] = ("paraphrase" if row["overlap"] < PARAPHRASE_OVERLAP else "keyword")
        for k in K_VALUES:
            top = set(ranked[:k])
            row[f"recall@{k}"] = len(top & set(gold)) / len(gold) if gold else 0.0
        for position, node_id in enumerate(ranked, start=1):
            if node_id in gold:
                row["reciprocal_rank"] = 1.0 / position
                break
        rows.append(row)
    return rows


def stratified_halves(rows):
    """Deal each measured bucket into H1/H2 by index over id-sorted queries.

    Mechanical on purpose: the A/B field in queries.json was authored before
    bucketing and came out unbalanced, so halves are derived here instead
    (PREREGISTRATION.md, amendment v2).
    """
    for bucket in ("paraphrase", "keyword"):
        members = sorted((r for r in rows if r["bucket"] == bucket), key=lambda r: r["id"])
        for index, row in enumerate(members):
            row["half"] = f"{bucket}-H{index % 2 + 1}"
    return rows


def aggregate(rows):
    if not rows:
        return {"n": 0}
    out = {"n": len(rows), "mrr@10": round(sum(r["reciprocal_rank"] for r in rows) / len(rows), 3)}
    for k in K_VALUES:
        out[f"recall@{k}"] = round(sum(r[f"recall@{k}"] for r in rows) / len(rows), 3)
    return out


def report(rows):
    groups = {
        "overall": rows,
        "keyword": [r for r in rows if r["bucket"] == "keyword"],
        "paraphrase": [r for r in rows if r["bucket"] == "paraphrase"],
        "paraphrase-H1": [r for r in rows if r.get("half") == "paraphrase-H1"],
        "paraphrase-H2": [r for r in rows if r.get("half") == "paraphrase-H2"],
        "keyword-H1": [r for r in rows if r.get("half") == "keyword-H1"],
        "keyword-H2": [r for r in rows if r.get("half") == "keyword-H2"],
        # Kept for the record: the authored split, which is why amendment v2 exists.
        "authored-split-A": [r for r in rows if r["split"] == "A"],
        "authored-split-B": [r for r in rows if r["split"] == "B"],
    }
    for label, subset in groups.items():
        print(label)
        if not subset:
            print("  (none)")
            continue
        for r in subset if label.startswith(("keyword-H", "paraphrase-H")) else []:
            print(f"  {r['id']} overlap={r['overlap']} r@5={r['recall@5']} "
                  f"rr={r['reciprocal_rank']:.2f} {r['query']!r}")
            if r["recall@5"] < 1.0:
                print(f"      gold={r['gold']} top5={r['ranked'][:5]}")
        agg = aggregate(subset)
        print(f"  n={agg['n']} recall@1={agg['recall@1']} recall@5={agg['recall@5']} "
              f"recall@10={agg['recall@10']} mrr@10={agg['mrr@10']}")
    return {k: aggregate(v) for k, v in groups.items()}


def main(argv):
    corpus_path = os.path.join(HERE, "corpus.json")
    queries_path = os.path.join(HERE, "queries.json")
    with open(corpus_path, encoding="utf-8") as fh:
        doc = json.load(fh)
    with open(queries_path, encoding="utf-8") as fh:
        queries = json.load(fh)["queries"]
    nodes_by_id = {n["id"]: n for n in doc["nodes"]}

    baseline_rows = stratified_halves(evaluate(retrieval.search, doc, queries, nodes_by_id))
    print(f"corpus: {len(doc['nodes'])} nodes | queries: {len(queries)}")
    print("retriever: lexical baseline (amg.retrieval.search)\n")
    summary = report(baseline_rows)

    result = {
        "retriever": "lexical-baseline",
        "corpus_sha256": sha256(corpus_path),
        "queries_sha256": sha256(queries_path),
        "paraphrase_overlap_threshold": PARAPHRASE_OVERLAP,
        "k_values": list(K_VALUES),
        "git_rev": subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                                  capture_output=True, text=True).stdout.strip() or None,
        "summary": summary,
        "rows": baseline_rows,
    }
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    out_path = os.path.join(HERE, "result.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"\nwrote {os.path.relpath(out_path, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
