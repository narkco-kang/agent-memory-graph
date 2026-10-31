# Decision #26

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; `docs/CONCURRENCY.md` §"At 10,000 nodes", `result-10k*.{json,txt}`.*

**The 5 s lock timeout stays; the 10k burst is documented, not papered over.**
    Pre-registered run (`experiments/concurrency/PREREGISTRATION-10k.md`): 8 writers ×
    25 writes on a 10,000-node graph, default timeout. It **failed** with
    `LockTimeout after 5.0s` — and the arithmetic says it had to: a write at 10k costs
    **86.2 ms**, so 200 writes are ~17 s of serialised work (measured burst window
    17.95 s), and the last writer waits ~13.5 s (measured) before it gets the lock.
    With an adequate timeout the invariant held exactly (200/200 nodes, 0 duplicates,
    0 missing, 200 change records, `check` clean, 11.1 writes/s contended vs 11.3/s
    serial). Two pre-registered predictions were wrong and are recorded as wrong:
    contended p50 did not inflate (1.0× serial), and the worst wait was not < 5 s.
    Decision: keep the 5 s default. An interactive CLI that silently blocks for 30 s
    is worse than a fast, explicit `LockTimeout` that names `AMG_LOCK_TIMEOUT`; and a
    larger default would hide the real finding, which is that the *write cost* is the
    limit, not the lock (`WRITE-COST.md`). Burst users are told the safe sizing rule:
    timeout ≥ writers × writes × per-write cost.
    *Signed 2026-10-31; `docs/CONCURRENCY.md` §"At 10,000 nodes", `result-10k*.{json,txt}`.*
