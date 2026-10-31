# Reranking by query coverage — rejected

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md) (written before the run).
Result: [`result.json`](result.json). Reproduce:

    PYTHONPATH=src python3 experiments/retrieval_beyond_df/run_rerank.py

## What was tried

The shipped scorer (v0.19.0+, IDF weights) leaves query-vocabulary noise at recall@5 **0.538**
against a published 0.70 target (DECISIONS #28). IDF is structurally blind to that corpus: N2
draws distractor tokens uniformly from the queries' own vocabulary, so every query term has the
same `df`. The candidate here is a signal outside the frequency family — **coverage**, the
fraction of query tokens a hit contains — applied as a rerank on the top 100 candidates:

    reranked = shipped_score × coverage(query, hit) ** alpha

`alpha = 0` is the control arm and must reproduce the shipped order exactly; the harness asserts
it (`alpha0_metrics_equal_shipped` in `result.json`, true for all four corpora; order equality is too strict because the returned score is rounded for output, so hits that differ below the rounding can swap inside a tie without moving any metric).

## Result: it makes everything worse

| corpus | shipped | α=0 | α=0.5 | α=1 | α=2 |
|---|---|---|---|---|---|
| control (27) | 0.865 | 0.865 | 0.846 | 0.846 | 0.846 |
| n1 unrelated | 0.865 | 0.865 | 0.808 | 0.808 | 0.808 |
| **n2 query-vocab** | **0.538** | 0.538 | **0.481** | 0.481 | 0.442 |
| n3 frequent-vocab | 0.865 | 0.865 | 0.808 | 0.808 | 0.808 |

Every pre-registered criterion fails (C1 control, C2 the +0.05 N2 gain, C3 n1, C4 n3); the
selected α is 0.5 by the "best N2 arm" rule and its gain is **−0.057**. No ship, no retuning:
per the pre-registration, the direction is recorded as rejected.

## Why it fails — the noise model inverts the signal

Coverage counts **all** query tokens, including the noise tokens N2 injects. Gold nodes match the
original query and contain few of the random additions; a distractor that happens to absorb three
random query tokens scores coverage 3/|q| while a gold node scores lower. So coverage does not
just fail to help on N2 — it is **anti-correlated with the answer there**, which is why the harm
(−0.057) is larger than on the corpora where it merely dilutes (−0.019 on control).

## Predictions, scored

1. "α = 1 is the best N2 arm" — **wrong**: α = 0.5 and α = 1 tie at 0.481, and both lose to α = 0.
2. "coverage buys N2 +0.03 … +0.08" — **wrong in sign**: −0.057.
3. "control r@5 drops ≤ 0.01 at α = 1" — **wrong**: drops 0.019.
4. "n3 stays within 0.01 of 0.865" — **wrong**: drops to 0.808.

All four wrong, recorded rather than rescued. The reusable lesson is the mechanism, not the
verdict: **for a noise model that adds query-vocabulary distractors, any scoring feature computed
over query tokens inherits the noise.** The next candidate must discriminate *source* tokens from
*injected* ones — e.g. proximity of matched terms to each other inside one field, which random
additions do not produce.

## What is still true from #28

- The frozen 27-query baseline with IDF: recall@5 **0.865**, unchanged by this round.
- N2 remains **0.538** against a 0.70 target: **not met, still open**, and this experiment does not
  move it.
