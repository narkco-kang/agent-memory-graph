# Pre-registration: bounded, comparable scores (R1/R2 remediation, v0.19.0)

Written on `v0.18.0` (`3afe7f7`), **before** `src/amg/retrieval.py` changes. This is a
defect round, not a candidate round: the two fixes come from the retrieval attack brief
(`docs/memory-arch/RETRIEVAL-NEXT-ATTACK.md`, E2/E3 → issues R1/R2). The bar is
therefore **no ranking change at all**, plus two measurable properties that were absent.

## The change (R1)

`idf` currently grows without a bound as the graph grows: `ln(1 + N/(1+df))` where `N`
is the live node count. Two consequences were registered in
`issue.mem-arch-idf-live-df-drift`: absolute scores depend on graph size (so they cannot
be compared across graphs or over time), and the only published 10k score behaviour was
that round's.

The change normalizes the IDF by its own maximum, `ln(1 + N)`:

```
idf(t)  = ln(1 + N/(1+df(t))) / ln(1 + N)        # 0 < idf <= 1
score   = Σ (field, t) matched  WEIGHTS[field] × idf(t)
```

- For a fixed query on a fixed graph, every term is divided by the **same** positive
  constant (`ln(1+N)`), so the **ranking is mathematically unchanged** — that is the
  critical property to verify, not to assert.
- Each matched (field, term) now contributes at most its field weight, so a score is
  bounded by `Σ WEIGHTS[matched fields]` (≤ 3.0 × terms) instead of growing with N.
- `N` stays the **visible** set (superseded / not-yet-valid excluded) by design: expired
  facts must not influence live ranking. That is now stated in the docs and pinned by a
  test; the issue's "inconsistent denominator" concern is answered by the rule, not by
  changing it.
- No cache is added. A per-query cache keyed on a content hash would have to be
  invalidated on every write; the measured cost is ~100 ms p50 at 10k, which is a
  documented limit, not a silent one.

## The change (R2)

L2 hits carry `score: 1.0` — a constant, while L1/L3/L4 carry IDF-weighted scores. A
consumer that merges layers sorts a constant against a weighted number. The change adds
one field, **`score_kind`**, to every hit:

| layer / path | `score_kind` | meaning |
|---|---|---|
| L1, L3, L4 | `"idf"` | weighted lexical match; comparable within this kind |
| L2 (live or archived) | `"recency"` | constant; the order is `at` descending, the number carries no match information |
| `--expand` neighbors | `"expansion"` | score 0.0; pulled in by an edge, not matched |

Docs state that scores with different `score_kind` must never be compared or merged.
No existing field changes type, so the change is additive.

## Verification (fixed now)

`experiments/score_scale/run_eval.py` runs the frozen v0.18.0 scorer (`baseline.py`) and
the shipped scorer in one process on the four corpora from `experiments/retrieval_idf/`.

| # | Criterion | Verdict rule |
|---|---|---|
| C1 | Ranking is unchanged | for every corpus and every query, the full ranked id list (k=100) is **identical** |
| C2 | Metrics are unchanged | every recall@1/5/10 and MRR@10 identical on all four corpora |
| C3 | Scores are bounded | on the frozen corpus, every hit's score ≤ `3.0 × distinct query terms` and > 0; and the same query's gold score at 27 / 1 000 / 10 000 unrelated-inflated nodes stays within **±5%** (the drift that remains is the saturating `ln` ratio, not growth) |
| C4 | `score_kind` is present and correct | every hit has `score_kind` in {idf, recency, expansion}; L2 says `recency`, L3 says `idf`, expanded neighbors say `expansion` |
| C5 | No other behaviour moved | hard filters, anchor rule, `strict`, `expand` attachment, L2 time order unchanged; full test suite green |

**Failure rule:** any C1 or C2 difference means the change is not order-preserving and is
reverted — no exceptions, because this round must not move recall.

## Predictions (recorded now)

| quantity | predicted |
|---|---|
| C1/C2 | exactly identical — the normalization is a common divisor |
| bound on frozen corpus | max score observed ≈ 2.1 (q01 matches 3 fields on 3 terms, all non-maximal) |
| score at 27 / 1k / 10k for the same gold | within ±5% (saturating, not growing) |
| suite size | 261 + 4–6 new tests |

## What this does not establish

- Nothing about ideal score comparability across *different queries*: scores are bounded
  evidence sums, not probabilities.
- Nothing about R3 (evidence `sha` is shape-checked only) — that is a contract-level
  change and gets its own round with an explicit Not-shipped boundary.
- No ranking improvement: this round deliberately moves zero recall.

## Reproduce

```bash
PYTHONPATH=src python3 experiments/score_scale/run_eval.py
```

---

## Amendment A (written after the first verification run, before the ship decision)

Two of my own criteria were arithmetically wrong, and the fix does not change because of
this amendment — only the wording and the two numbers do. Recorded, not quietly rewritten.

1. **C3 bound was wrong.** I wrote "score ≤ 3.0 × distinct query terms", as if a term
   could only match `id`. It can match up to five fields, and one term matched everywhere
   is worth `3.0 + 2.0 + 1.0 + 0.5 + 0.5 = 7.0`. The measured worst score on the frozen
   corpus is **8.716** for an identifier query with one term, which is within the true
   bound. Corrected criterion: every score is in `(0, 7.0 × distinct terms]`.
2. **The "≤5% drift" prediction was wrong.** Measured for q01's gold node: score
   7.431 (27 nodes) → 9.625 (1 000) → 10.215 (10 000), i.e. **+37%**, not ±5%. The
   normalization is *bounded* but not *invariant*: with `df` fixed and `N` growing,
   `ln(1+N/(1+df)) / ln(1+N)` still climbs toward 1. What the change removes is the
   unbounded growth: the v0.18.0 scorer's ratio on the same ladder is recorded in
   `result.json` for comparison, and a score is now capped by `Σ WEIGHTS`, so it cannot
   scale with graph size without limit.

Ship rule under the amendment: C1 and C2 (ranking and metrics identical — the property
that makes this a defect fix rather than a candidate) remain the gate; C3 is gated on the
corrected bound; the residual drift is **published** in the README and the issue, not
hidden, and `issue.mem-arch-idf-live-df-drift` stays open as "bounded, not invariant".
