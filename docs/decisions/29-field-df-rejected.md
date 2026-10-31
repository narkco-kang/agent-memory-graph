# Decision #29

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; experiment README + `result.json`.*

**Field-specific document frequency is rejected: the noise gain is paid for by
    note-only queries.** Pre-registered in `experiments/retrieval_field_df/`; one
    variable (df counted per (field, term)). Measured against the frozen v0.18.0 scorer
    in one process: N2 query-vocabulary noise **0.538 → 0.596**, N3 held 0.865, p95
    0.991× — but the frozen 26-query recall@5 **0.865 → 0.827**, because exactly one
    query moved (q18 `3 → 6`, a note-only match paying note's lower IDF). C1/C2 failed;
    the pre-registered rule (frozen drop >0.01 kills the direction) was honoured: **no
    release, `src/amg/retrieval.py` reverted** to v0.18.0, no tuning. C6 ("hit sets
    unchanged") failed **as written** and is recorded as my pre-registration error (at
    10k it compared top-100 membership, which any reordering moves; no match is
    dropped). Two predictions recorded wrong. Open policy question, pre-registered
    before any future round may act on it: is `frozen −0.038` a fair price for
    `N2 +0.058`? *Signed 2026-10-31; experiment README + `result.json`.*
