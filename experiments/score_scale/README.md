# Bounded, comparable scores — verified (v0.19.0)

Pre-registration (with Amendment A): [`PREREGISTRATION.md`](PREREGISTRATION.md).
Defect round for the attack brief's E3/`R1` and `R2`: absolute scores grew with the
graph, and L2's constant `score: 1.0` was indistinguishable from a weighted L3 score.

## What changed

- **R1** — `idf(t) = ln(1 + N/(1+df)) / ln(1 + N)`, so each matched (field, term)
  contributes at most its field weight: a score is in `(0, 7.0 × matched terms]`
  instead of growing with `N`.
- **R2** — every hit carries `score_kind`: `idf` (L1/L3/L4), `recency` (L2, where the
  order is `at` descending and the number carries no match information), `expansion`
  (`--expand` neighbours, 0.0). Docs forbid comparing across kinds. Additive: no field
  changed type.

## Verified (`result.json`)

| check | result |
|---|---|
| C1/C2 — every ranked id list and every metric identical to v0.18.0, all four corpora | **pass** (control, N1, N2, N3: ranking identical, metrics identical) |
| C3 — bounded | **pass**; worst frozen score 8.716, bound `7.0 × terms` |
| C3 — drift, 27 → 1 000 → 10 000 unrelated nodes (q01 gold) | 7.431 → 9.625 → 10.215, ratio **1.375×**; v0.18.0's ratio on the same ladder **3.799×** |
| C4 — `score_kind` correct per layer/expansion/archive | **pass** |
| suite | 268 tests (261 + 7), 1 environment skip |

The critical property is C1: because the divisor `ln(1 + N)` is common to one query,
the normalization cannot move a rank — and the run proves it rather than asserting it.
The residual 1.375× drift is published, not hidden: scores are *bounded*, not
*size-invariant*, and `issue.mem-arch-idf-live-df-drift` stays open with that wording.

## Predictions that were wrong (kept as wrong; Amendment A)

| prediction | measured |
|---|---|
| bound `3.0 × terms` | **wrong**: a term can match five fields, so the bound is `7.0 × terms` |
| score drift within ±5% across 27/1k/10k | **wrong**: +37% (bounded and saturating, but not flat) |

## Not in this round

- No cache: 100 ms p50 at 10k is a documented limit.
- No ranking change at all — the round was measured to be behaviour-preserving.
- R3 (evidence `sha` only shape-checked) untouched: contract-level, needs its own round.
