# Decision #25

[← decision log](../DECISIONS.md) · status: amended (#28) · *Signed 2026-10-31; `tests/test_search_precision.py`, `experiments/retrieval_precision/`.*

**Lexical matching is word-aware; the recall it costs is recorded, not hidden.**
    The substring matcher answered queries that cannot distinguish anything: on the
    real 1,289-node graph, `a`, `e`, `i` and `x` each returned the full `k=10`, and an
    identifier for a node that does not exist (`task.a`) returned ten unrelated
    `task.*` ids. The fix is word-boundary matching plus a 14-entry English inflection
    table (`rank`/`ranking`), identifier queries treated as lookups, and one-character
    ASCII tokens dropped. Measured (`experiments/retrieval_precision/`): single-letter
    queries 10 → **0** hits, nonexistent identifiers 10 → **0**, identifier lookups
    **20/20** top-1, kw recall@5 0.938 → **0.969**, MRR 0.744 → **0.763**. The cost is
    real and is published: overall recall@5 0.865 → **0.808** on the frozen eval,
    because two of 26 queries had been reached only through substrings *inside* other
    words (`i` in `high-risk`, `one` in `gone`); recall@1 is unchanged at 0.654. The
    pre-registration failed C4 (recall must not drop) and C5 (no pinned numbers may
    move) — both failures are recorded in its outcome section with the per-query
    analysis, and this decision overrides them on the evidence, because raising
    `k`-many answers to "anything with this letter" is not a retrieval feature.
    `tests/test_retrieval_eval.py` pins the **new** numbers and keeps the old ones in
    its comment for audit.
    *Signed 2026-10-31; `tests/test_search_precision.py`, `experiments/retrieval_precision/`.*
