#!/usr/bin/env python3
"""Post-hoc diagnostic: where the signal is, and where it is needed.

NOT pre-registered — added after the run to explain the pooled AUC. The pre-registration's D1
reports one mean AUC per signal per corpus, which can hide the only thing that matters: the mean is
dominated by queries the shipped scorer already solves. This splits the same top-100 candidates by
whether the shipped ranking already put the gold in the top 5.

    PYTHONPATH=src python3 experiments/retrieval_lexical_ceiling/diagnose_by_solved.py
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_lexical as lc  # noqa: E402

CAPTION = "post-hoc: not part of the pre-registered criteria"


def main():
    doc, queries = lc.ten_k.load_inputs()
    corpus = lc.ten_k.inflate_vocabulary(doc, queries)
    nodes_by_id = {n["id"]: n for n in corpus["nodes"]}
    rows = []
    for item in queries:
        query_tokens = lc.run_eval.tokens(item["query"])
        content = lc.content_tokens(item["query"])
        gold = set(item["gold"]) & set(nodes_by_id)
        hits = lc.retrieval.search(corpus, item["query"], layer="L3", k=lc.DEEP_K)
        labels = [1 if hit["id"] in gold else 0 for hit in hits]
        features = {signal: {} for signal in lc.ARM_SIGNALS}
        for hit in hits:
            values = lc.signals(query_tokens, content, nodes_by_id.get(hit["id"], {}))
            for signal in lc.ARM_SIGNALS:
                features[signal][hit["id"]] = values[signal]
        rank = next((position for position, hit in enumerate(hits, start=1)
                     if hit["id"] in gold), None)
        row = {"id": item["id"], "gold_rank": rank}
        for signal in lc.ARM_SIGNALS:
            row[f"auc_{signal}"] = lc.auc([features[signal][hit["id"]] for hit in hits], labels)
        rows.append(row)

    solved = [row for row in rows if row["gold_rank"] and row["gold_rank"] <= 5]
    failing = [row for row in rows if not row["gold_rank"] or row["gold_rank"] > 5]

    def mean(group, key):
        values = [row[key] for row in group if row[key] is not None]
        return round(statistics.mean(values), 4) if values else None

    summary = {"caption": CAPTION, "queries": len(rows),
               "solved_gold_in_top5": len(solved), "failing_gold_outside_top5": len(failing),
               "gold_beyond_top100": sum(1 for row in rows if row["gold_rank"] is None),
               "mean_auc_solved": {signal: mean(solved, f"auc_{signal}")
                                   for signal in lc.ARM_SIGNALS},
               "mean_auc_failing": {signal: mean(failing, f"auc_{signal}")
                                    for signal in lc.ARM_SIGNALS},
               "rows": rows}
    with open(os.path.join(HERE, "diagnostic_by_solved.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"{CAPTION}")
    print(f"{'q':4s} {'gold_rank':>9s} " + " ".join(f"{s:>12s}" for s in lc.ARM_SIGNALS))
    for row in sorted(rows, key=lambda r: (r["gold_rank"] is None, r["gold_rank"] or 999)):
        cells = " ".join(f"{(row[f'auc_{s}'] if row[f'auc_{s}'] is not None else float('nan')):12.3f}"
                         for s in lc.ARM_SIGNALS)
        print(f"{row['id']:4s} {str(row['gold_rank']):>9s} {cells}")
    print()
    print(f"solved (gold in top 5): {len(solved)}  mean AUC {summary['mean_auc_solved']}")
    print(f"failing (gold outside 5): {len(failing)}  mean AUC {summary['mean_auc_failing']}")
    print(f"gold beyond top 100 (unreachable by any rerank): {summary['gold_beyond_top100']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
