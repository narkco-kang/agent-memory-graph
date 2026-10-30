# Retrieval at 10,000 nodes (pre-registered)

`retrieval_eval/` measures the matcher on a frozen 27-node corpus. This directory asks
the next question: **what does scale do to recall**, using the same corpus, the same 26
queries and the same metric functions — only the graph size changes.

- `PREREGISTRATION.md` — the plan, the predictions (two of them wrong), amendment A (a
  second noise model, declared before it ran), and the outcome table.
- `run_eval.py` — the harness. Builds two 10k corpora in memory, runs a same-process
  27-node control, writes `result.json`.
- `result.json` — last run: both noise models, per-bucket and per-query rows, digests.

```bash
PYTHONPATH=src python3 experiments/retrieval_10k/run_eval.py
```

## Two noise models, on purpose

| model | distractors are | question it answers |
|---|---|---|
| **N1** unrelated | `benchmarks/bench.py` generator ("task number N parser queue") | does graph size alone dilute recall? |
| **N2** query-vocabulary | labels/notes sampled from the 26 queries' own tokens (seeded) | does vocabulary overlap dilute recall, as in a real long-lived memory? |

## Measured

| run | nodes | recall@1 | recall@5 | recall@10 | MRR@10 | search p50 |
|---|---|---|---|---|---|---|
| control | 27 | 0.654 | 0.808 | 0.865 | 0.763 | — |
| N1 | 10,000 | 0.654 | 0.808 | 0.865 | 0.763 | 74.3 ms |
| N2 | 10,000 | **0.481** | **0.538** | 0.538 | **0.515** | 92.5 ms |

Two findings:

1. **Size alone costs nothing.** 370× more unrelated nodes left every metric identical.
2. **Vocabulary overlap costs 0.27 recall@5, and the cause is scoring, not matching.**
   Of the 11 misses under N2, **7 are beyond rank 100**: dozens of distractors outscored
   the gold node. The scorer (`WEIGHTS` in `src/amg/retrieval.py`) has no IDF notion, so
   a note repeating common query words is worth as much as the node that answers.

## What this does not establish

- Not a real graph: synthetic English noise on a frozen corpus, one host.
- Not semantic recall; not an IDF result. IDF weighting is the *next* candidate and
  needs its own pre-registration (the current round touched no code, per criterion C4).
- Not a ranking guarantee: recall@10 collapses to recall@5 under N2, i.e. the gold
  answers pushed out are pushed far out, not just to rank 6.
