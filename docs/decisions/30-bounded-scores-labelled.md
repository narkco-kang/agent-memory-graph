# Decision #30

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; `experiments/score_scale/`; v0.19.0.*

**Scores are bounded and labelled; the normalization changes no rank.** Defect round
    for R1 (`idf-live-df-drift`) and R2 (`l2-fixed-score`), pre-registered in
    `experiments/score_scale/` with Amendment A for two of my own arithmetic errors.
    R1: IDF divided by `ln(1 + N)` bounds a score at `Σ WEIGHTS = 7.0` per matched term
    instead of growing with graph size; verified that **every ranked id list and every
    metric on all four corpora is identical** to v0.18.0 (common divisor), residual
    27→10k drift published as 1.375× against 3.799×, so the issue stays open as
    "bounded, not invariant". R2: hits carry **`score_kind`** — `idf` (L1/L3/L4),
    `recency` (L2; the 1.0 is not a match score), `expansion` (0.0) — and docs forbid
    comparing across kinds; no field changed type. Amendment A: my bound used `3.0`
    where five fields can match (7.0), and I predicted ≤5% drift where measurement is
    +37%; both recorded as wrong, not rescued in code. No cache: 100 ms p50 at 10k is a
    documented limit. *Signed 2026-10-31; `experiments/score_scale/`; v0.19.0.*
