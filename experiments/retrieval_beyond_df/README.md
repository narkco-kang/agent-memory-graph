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

## Why it fails — distribution shape, not anti-correlation

*(Corrected in v0.32.7: the first version of this section said coverage was "anti-correlated with
the answer" on N2. An attack falsified that — see DECISIONS #48 — and the corrected explanation is
below. The wrong version is preserved in #47, which is `amended`.)*

Measured by the attacker, on four arms:

- Rewriting the distractors with 78 **foreign** words of comparable length (same corpus, same
  seed, asserted disjoint from the query vocabulary) gives a loss of **−0.057 — identical to N2's**.
  So the damage does not depend on the distractors being query words.
- Gold coverage averages **0.610** against the distractors' **0.376**: positively associated, not
  anti-correlated.
- The driver is the **shape** of the two distributions. Gold is bimodal — 7 of 22 queries fully
  covered, 8 of 22 at or below 0.33 — while distractors cluster (64% between 0.25 and 0.5). Query
  `q04`: gold `task.windows-lock` matches one content word (coverage 0.12) while a distractor
  matches three *function* words (coverage 0.38); α=1 pushes gold from rank 1 to rank 79. `q26` is
  the same shape (pushed 77 places).
- Restricting coverage to content words returns N2 to **0.615 (+0.077)**, reversals 9 → 3 — but that
  is a selective construction: a candidate for a fresh pre-registration, not a result.

## Predictions, scored

1. "α = 1 is the best N2 arm" — **wrong**: α = 0.5 and α = 1 tie at 0.481, and both lose to α = 0.
2. "coverage buys N2 +0.03 … +0.08" — **wrong in sign**: −0.057.
3. "control r@5 drops ≤ 0.01 at α = 1" — **wrong**: drops 0.019.
4. "n3 stays within 0.01 of 0.865" — **wrong**: drops to 0.808.

All four wrong, recorded rather than rescued. The lesson is narrower than the first version of this
README claimed: **coverage penalises a true answer that matches only part of the query** (usually one
content word) while distractors match a few *function* words, so the loss follows the shape of the
two distributions rather than the identity of the tokens. The next direction is content-word
weighting or stop-word stripping, to be pre-registered before it is measured (DECISIONS #48).

## What is still true from #28

- The frozen 27-query baseline with IDF: recall@5 **0.865**, unchanged by this round.
- N2 remains **0.538** against a 0.70 target: **not met, still open**, and this experiment does not
  move it.
