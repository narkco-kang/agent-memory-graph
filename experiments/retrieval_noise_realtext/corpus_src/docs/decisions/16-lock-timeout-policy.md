# Decision #16

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30.*

**The lock timeout is a policy knob, not a constant — and fairness is not the
    fix for bursts.** Measured on the real 15.6 MB graph: a write costs ~147 ms, so
    a 5 s default covers ~34 queued writes; 8 writers × 5 writes (40 writes) hits
    `LockTimeout` even though nothing is broken, because the queue needs ~6 s to
    drain. So `AMG_LOCK_TIMEOUT` was added (clamped to `(0, 3600]`, invalid values
    fall back to 5 s) and the default stays 5 s for interactive single-agent use.
    A FIFO lock would not help this case: the last writer still waits for the whole
    queue. The lever that does help is a cheaper write (history sidecar, priced in
    `WRITE-COST.md`: ~150 ms → ~30 ms, i.e. 34 → ~170 queued writes per 5 s).
    *Signed 2026-10-30.*
