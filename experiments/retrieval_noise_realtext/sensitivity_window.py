#!/usr/bin/env python3
"""Post-hoc sensitivity: does the real-text corpus's difficulty come from the 8-word window?

NOT pre-registered. The pre-registered corpus took an 8-word window of each real paragraph; real
notes are longer (median 37 words in this repository's prose). If the recall number moves a lot with
the window length, then the pre-registered number is a statement about *short* real notes and must be
reported with that qualifier rather than as "realistic noise" in general.

    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/sensitivity_window.py
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_realtext as rt  # noqa: E402

WINDOWS = (8, 20, 0)   # 0 = the whole paragraph


def build(doc, paragraphs, window):
    rng = random.Random(rt.SEED)
    nodes = list(doc["nodes"])
    existing = {n["id"] for n in nodes}
    index = 0
    while len(nodes) < rt.TARGET_NODES:
        words = paragraphs[rng.randrange(len(paragraphs))]
        if window:
            start = rng.randrange(max(1, len(words) - window + 1))
            picked = words[start:start + window]
        else:
            picked = words
        node = rt.bench.make_node(index, with_evidence=False)
        node["label"] = " ".join(picked[:3])
        node["note"] = " ".join(picked[3:])
        node["source"] = "synthetic real-prose distractor"  # same as the pre-registered build
        if node["id"] not in existing:
            nodes.append(node)
            existing.add(node["id"])
        index += 1
    return {"schema": doc.get("schema"), "group": doc.get("group"),
            "nodes": nodes, "edges": [], "changes": []}


def main():
    doc, queries = rt.ten_k.load_inputs()
    paragraphs = rt.prose_pool()
    rows = []
    for window in WINDOWS:
        corpus = build(doc, paragraphs, window)
        share, coverage = rt.competing_share(corpus, queries)
        metrics = rt.evaluate(corpus, queries)
        rows.append({"window": window or "whole paragraph",
                     "median_words": sorted(len(p) for p in paragraphs)[len(paragraphs) // 2]
                     if window == 0 else window,
                     "competing_share_ge_0.25": share,
                     "recall@1": metrics["recall@1"], "recall@5": metrics["recall@5"],
                     "recall@10": metrics["recall@10"], "mrr@10": metrics["mrr@10"],
                     "ceiling": metrics["ceiling"]})
        print(f"window={rows[-1]['window']:>16}  share>=.25={share:.3f}  r@5={metrics['recall@5']:.3f} "
              f"r@1={metrics['recall@1']:.3f} mrr={metrics['mrr@10']:.3f}")
    payload = {"caption": "post-hoc sensitivity on distractor length; the pre-registered run is window=8",
               "rows": rows,
               "corpus": rt.corpus_snapshot(paragraphs),
               "note": ("the pre-registered number is a statement about short real notes; longer "
                        "windows are reported to show how much of the difficulty is length")}
    out_dir = os.environ.get("REALTEXT_OUT_DIR") or HERE
    with open(os.path.join(out_dir, "sensitivity_window.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
