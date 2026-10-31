#!/usr/bin/env python3
"""Which queries did the semantic arms actually fix, if any?

NOT pre-registered — added after the run. The three arms scored the same recall@5 on N2 (0.577),
which could mean they fixed the same single query or that something is degenerate. This prints the
per-query gold rank for every arm, so the difference (or its absence) is visible per query instead
of aggregated away.

    PYTHONPATH=src python3 experiments/retrieval_semantic/diagnose_moved_queries.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_semantic as rs  # noqa: E402

CAPTION = "post-hoc: not part of the pre-registered criteria"


def gold_rank(ranked, gold):
    for position, node_id in enumerate(ranked, start=1):
        if node_id in gold:
            return position
    return None


def main():
    doc, queries = rs.ten_k.load_inputs()
    corpus = rs.ten_k.inflate_vocabulary(doc, queries)
    nodes_by_id = {n["id"]: n for n in corpus["nodes"]}
    for node in nodes_by_id.values():
        node["_digest"] = None
    embedder = rs.Embedder()
    texts = [rs.run_eval.node_text(node) for node in nodes_by_id.values()]
    texts += [item["query"] for item in queries]
    vectors = embedder.ensure(texts)
    for node in nodes_by_id.values():
        node["_digest"] = embedder.digest(rs.run_eval.node_text(node))

    rows = []
    for item in queries:
        gold = set(item["gold"]) & set(nodes_by_id)
        hits = rs.retrieval.search(corpus, item["query"], layer="L3", k=rs.DEEP_K)
        lexical = [hit["id"] for hit in hits]
        query_vector = vectors[embedder.digest(item["query"])]
        rerank, semantic, hybrid = rs.order_by(lexical, None, vectors, query_vector, nodes_by_id)
        rows.append({"id": item["id"], "bucket": ("paraphrase"
                                                  if rs.run_eval.overlap(
                                                      item["query"],
                                                      [nodes_by_id[g] for g in gold])
                                                  < rs.run_eval.PARAPHRASE_OVERLAP else "keyword"),
                     "shipped": gold_rank(lexical, gold),
                     "A_rerank": gold_rank(rerank, gold),
                     "B_semantic": gold_rank(semantic, gold),
                     "C_hybrid": gold_rank(hybrid, gold)})

    def top5(rank):
        return bool(rank) and rank <= 5

    moved = [row for row in rows
             if any(top5(row[arm]) != top5(row["shipped"])
                    for arm in ("A_rerank", "B_semantic", "C_hybrid"))]
    summary = {"caption": CAPTION, "queries": len(rows),
               "shipped_top5": sum(1 for row in rows if top5(row["shipped"])),
               "per_arm_top5": {arm: sum(1 for row in rows if top5(row[arm]))
                                for arm in ("A_rerank", "B_semantic", "C_hybrid")},
               "moved_across_top5": [row["id"] for row in moved],
               "rows": rows}
    with open(os.path.join(HERE, "diagnostic_moved_queries.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"{CAPTION}")
    print(f"{'q':4s} {'bucket':11s} {'shipped':>8s} {'A':>6s} {'B':>6s} {'C':>6s}")
    for row in rows:
        cells = " ".join(f"{str(row[arm]):>6s}" for arm in ("A_rerank", "B_semantic", "C_hybrid"))
        print(f"{row['id']:4s} {row['bucket']:11s} {str(row['shipped']):>8s} {cells}")
    print()
    print(f"top-5 counts: shipped {summary['shipped_top5']} | {summary['per_arm_top5']}")
    print(f"queries that moved across the top-5 boundary: {summary['moved_across_top5']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
